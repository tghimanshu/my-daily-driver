import math
import os
import threading
import time
from datetime import datetime, timezone

# The pomodoro cycle. A focus round is followed by a break: a short one, unless
# the round just finished was the last of its group, in which case a long one.
FOCUS = "focus"
SHORT_BREAK = "short_break"
LONG_BREAK = "long_break"

BREAKS = (SHORT_BREAK, LONG_BREAK)
MODE_LABELS = {FOCUS: "Focus", SHORT_BREAK: "Short break", LONG_BREAK: "Long break"}

# Which setting gives each part of the cycle its length.
SETTING_FOR = {
    FOCUS: "work_minutes",
    SHORT_BREAK: "short_break_minutes",
    LONG_BREAK: "long_break_minutes",
}

# Wide ranges on purpose: the point of the widget is that the lengths are the
# user's call, not that the defaults are the only option. A break may be set to
# nothing, which is how someone says "skip straight to the next round", but a
# focus round may not, since a round of no length would never end.
LIMITS = {
    "work_minutes": (1, 180),
    "short_break_minutes": (0, 60),
    "long_break_minutes": (0, 90),
    "rounds": (1, 12),
    "daily_goal": (0, 24),
}

DEFAULTS = {
    "work_minutes": 25,
    "short_break_minutes": 5,
    "long_break_minutes": 15,
    "rounds": 4,
    "daily_goal": 8,
}

# POMODORO_* sets the length of each part of the cycle, POMODORO_ROUNDS how many
# focus rounds make a group, and POMODORO_GOAL how many a day is aiming for. The
# values come from .env, so a plain number is all that is expected of them.
ENV_KEYS = {
    "work_minutes": "POMODORO_WORK_MINUTES",
    "short_break_minutes": "POMODORO_SHORT_BREAK_MINUTES",
    "long_break_minutes": "POMODORO_LONG_BREAK_MINUTES",
    "rounds": "POMODORO_ROUNDS",
    "daily_goal": "POMODORO_GOAL",
}

HISTORY_DAYS = 7


def _clamp(name, value):
    """Hold a setting inside its range, so a bad number cannot wedge the timer."""
    low, high = LIMITS[name]
    return max(low, min(high, int(value)))


def _clamp_seconds(value, mode):
    """
    Clamp a duration to its range and convert it to whole seconds.

    Stored in seconds rather than minutes so a short break can be set to less
    than a minute, and so nothing is lost to rounding when a break is a minute
    and a half.
    """
    return _clamp(SETTING_FOR[mode], value) * 60


def clean_settings(settings):
    """
    A complete, in-range settings dict, whatever the caller passed in.

    An unknown key is dropped and a missing one falls back to the default, so a
    partial update or a stale stored blob can never leave the timer without a
    duration. A value that is not a number falls back too: refusing the whole
    update would be worse than ignoring one field.
    """
    settings = settings if isinstance(settings, dict) else {}
    cleaned = {}
    for name, default in DEFAULTS.items():
        raw = settings.get(name, default)
        try:
            cleaned[name] = _clamp(name, int(round(float(raw))))
        except (TypeError, ValueError):
            cleaned[name] = default
    return cleaned


def settings_from_env(env=None):
    """
    The defaults from .env, falling back to DEFAULTS per field.

    Read per field rather than all at once, so one blank line in .env does not
    discard the durations next to it.
    """
    source = os.environ if env is None else env
    return clean_settings({
        name: source.get(key, DEFAULTS[name])
        for name, key in ENV_KEYS.items()
    })


class Pomodoro:
    """
    The state of one browser's pomodoro timer.

    Like ``SiteStatus`` this is deliberately not an ``Integration``: there is no
    provider to authenticate against and no upstream payload to cache. What it
    does have is per-session state, which the app holds for it.

    The timer is kept server side so a reload, a closed tab or a second tab
    cannot make it lose track, and so the completed rounds are still there in the
    morning. It is not persisted to disk: the container runs on a read-only root
    filesystem, and a restart resets the day, which is a small enough loss for a
    timer to be worth keeping the deployment simple.

    A running round is stored as the moment it ends rather than as a countdown,
    so the remaining time is recomputed from the clock on every read. That also
    means a browser that slept through a round is not trusted to report the
    transition: the read that finds the round over credits it and moves the cycle
    on, one round per read, so a long gap cannot come back as a queue of breaks
    and notifications.
    """

    def __init__(self, settings=None, now=None):
        self.lock = threading.RLock()
        now = self._now(now)
        self.settings = clean_settings(settings if settings is not None else settings_from_env())
        self.mode = FOCUS
        self.round = 0
        self.running = False
        self.remaining = self._duration(FOCUS)
        self.deadline = None
        self.rounds_today = 0
        self.focus_seconds_today = 0
        self.history = []
        self.date = self._today(now)
        self.notice = None

    # ---------- state as the browser sees it ----------

    def snapshot(self, now=None):
        """
        Everything the widget needs, in one payload.

        ``remaining_at`` is the server's reading of the same countdown, so a
        widget can correct itself after a tab was throttled or asleep. The browser
        ticks locally between reads and does not call this every second.
        """
        with self.lock:
            now = self._now(now)
            remaining, ended = self._remaining(now)
            if ended:
                # Reading the timer is also where an unattended round ends. The
                # widget is looking at a clock that ran out, so it should be
                # offered the next one rather than a dead zero. One round per read,
                # so a laptop that slept through a whole afternoon does not come
                # back with a queue of breaks to run.
                self._advance(now)
                remaining = self.remaining
            # After crediting, not before: a round that ran past midnight belongs
            # to the day it was worked, not to the one it ended on.
            self._roll_day(now)
            return self._payload(now, remaining)

    def _payload(self, now, remaining):
        return {
            "mode": self.mode,
            "label": MODE_LABELS[self.mode],
            "is_break": self.mode in BREAKS,
            "running": self.running,
            "remaining": remaining,
            "remaining_at": now,
            "total": self._duration(self.mode),
            "rounds_today": self.rounds_today,
            "focus_seconds_today": self.focus_seconds_today,
            "focused_minutes_today": self.focus_seconds_today // 60,
            "round": self.round,
            "cycle_length": self.settings["rounds"],
            "daily_goal": self.settings["daily_goal"],
            "goal_met": self.rounds_today >= self.settings["daily_goal"] > 0,
            "history": self.history,
            "date": self.date,
            "settings": dict(self.settings),
            "notice": self.notice,
        }

    # ---------- controls ----------

    def start(self, now=None):
        """
        Run the current round, or pick up a paused one where it stopped.
        """
        with self.lock:
            now = self._now(now)
            self.notice = None
            remaining, ended = self._remaining(now)
            if ended:
                # The round ran out while paused, which happens when a tab is
                # closed across the boundary. Move on rather than counting down
                # from zero.
                self._advance(now)
                remaining = self.remaining
            if remaining <= 0:
                remaining = self._duration(self.mode)
            self.remaining = remaining
            self.running = True
            self.deadline = now + remaining
            return self.snapshot(now)

    def pause(self, now=None):
        with self.lock:
            now = self._now(now)
            remaining, ended = self._remaining(now)
            if ended:
                # Nothing left to pause. The round is over, so this reports the
                # next one, waiting to be started.
                self._advance(now)
                remaining = self.remaining
            self.notice = None
            self.remaining = max(0, remaining)
            self.running = False
            self.deadline = None
            return self.snapshot(now)

    def reset(self, now=None):
        """
        Put the current round back to its full length, stopped.

        A round that ran out on its own is treated as done and the cycle moves
        on: that is the "I was not watching but the timer was" case. A round
        stopped early just restarts.
        """
        with self.lock:
            now = self._now(now)
            self.notice = None
            if self._remaining(now)[1]:
                self._advance(now)
            self.running = False
            self.deadline = None
            self.remaining = self._duration(self.mode)
            return self.snapshot(now)

    def skip(self, now=None):
        """
        End the current round and move to the next, without counting it.

        The other way to leave a round you did not use, and the one for a
        distraction that should not make the day's total honest-looking.
        """
        with self.lock:
            now = self._now(now)
            self.notice = None
            self._advance(now)
            return self.snapshot(now)

    def update_settings(self, settings, now=None):
        """
        Apply new lengths or a new goal, and rebuild the current round from them.

        A round in progress is not rescaled partway through: it either finishes on
        the length it started with or is stopped and restarted. Half a pomodoro
        and half of something else is not a duration anyone asked for.
        """
        with self.lock:
            now = self._now(now)
            self.settings = clean_settings(settings)
            self.notice = None
            if self._remaining(now)[1]:
                self._advance(now)
            self.running = False
            self.deadline = None
            self.remaining = self._duration(self.mode)
            return self.snapshot(now)

    def clear_today(self, now=None):
        """
        Zero the day's counters without touching the cycle.

        For a fresh count after a bad morning, or for reaching a goal in one go. A
        round that ran out on its own is credited first, so clearing never quietly
        eats a finished round.
        """
        with self.lock:
            now = self._now(now)
            if self._remaining(now)[1]:
                self._advance(now)
            self.rounds_today = 0
            self.focus_seconds_today = 0
            self.notice = None
            return self.snapshot(now)

    # ---------- internals ----------

    def _now(self, now=None):
        return float(now) if now is not None else time.time()

    @staticmethod
    def _today(now):
        return datetime.fromtimestamp(now, timezone.utc).date().isoformat()

    def _duration(self, mode):
        return _clamp_seconds(self.settings[SETTING_FOR[mode]], mode)

    def _remaining(self, now):
        """
        Seconds left in the current round, and whether it ran out since the last
        read.

        A running round is measured against its deadline rather than decremented,
        which is what makes a reload or a sleeping laptop harmless.
        """
        if self.running and self.deadline is not None:
            left = math.ceil(self.deadline - now)
            if left <= 0:
                return 0, True
            return left, False
        return max(0, int(self.remaining)), False

    def _next_mode(self):
        if self.mode != FOCUS:
            return FOCUS
        if self.round % self.settings["rounds"] == 0:
            return LONG_BREAK
        return SHORT_BREAK

    def _advance(self, now):
        """Credit a finished round, move to the next part of the cycle, stop."""
        if self.mode == FOCUS:
            self.round += 1
            self.rounds_today += 1
            self.focus_seconds_today += self._duration(FOCUS)
            following = self._next_mode()
            self.notice = "Focus round %d done. %s" % (
                self.round, "Time for a long break." if following == LONG_BREAK
                else "Time for a short break."
            )
        else:
            self.notice = "Break over. Time to focus."

        self.mode = self._next_mode()
        self.remaining = self._duration(self.mode)
        self.running = False
        self.deadline = None
        self._roll_day(now)

    def _roll_day(self, now):
        """
        Start a new day when the date moves on.

        The finished day is kept in the history, so the widget can still show a
        week of focus after midnight instead of the counter silently resetting.
        """
        today = self._today(now)
        if today == self.date:
            return
        self.history.append({"date": self.date, "rounds": self.rounds_today})
        self.history = self._clean_history(self.history)
        self.date = today
        self.rounds_today = 0
        self.focus_seconds_today = 0

    @staticmethod
    def _clean_history(history):
        """
        The last week of finished days, oldest first and without duplicates.

        Keyed by date rather than appended to, so a clock that steps backwards
        and forwards again cannot show the same day twice in the strip.
        """
        by_date = {day["date"]: dict(day) for day in history}
        return [by_date[key] for key in sorted(by_date)[-HISTORY_DAYS:]]
