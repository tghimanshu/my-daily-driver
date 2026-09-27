import hashlib
import os
import secrets
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for

from github_integration import GitHubIntegration
from leetcode_integration import LeetCodeIntegration

WEAK_SECRET_KEYS = {"change_me", "my-daily-driver-dev-secret", "secret", ""}
MIN_SECRET_KEY_LENGTH = 32


def load_env_file(path=None):
    """
    Read ``KEY=VALUE`` pairs from a .env file into ``os.environ``.

    Real environment variables always win, so ``GITHUB_TOKEN=... python app.py``
    still overrides the file. Parsed inline instead of pulling in python-dotenv:
    the dashboard is a single local process and this avoids an extra dependency
    for one file format.
    """
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(path):
        return False

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            key, _, value = line.partition("=")
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")
    return True


load_env_file()


def resolve_secret_key():
    """
    Pick a session signing key, replacing one that could be guessed.

    The key signs the session cookie that names the server-side credential store,
    so a known or short value lets anyone mint a cookie for an arbitrary session
    id. A placeholder or short key is replaced with a random one and reported,
    which costs a re-login but is better than a guessable key.
    """
    configured = (os.environ.get("SECRET_KEY") or "").strip()
    if configured and configured not in WEAK_SECRET_KEYS and len(configured) >= MIN_SECRET_KEY_LENGTH:
        return configured, None

    reason = (
        "still set to the placeholder from .env.example"
        if configured in WEAK_SECRET_KEYS and configured
        else "too short"
        if configured
        else "not set"
    )
    warning = (
        "SECRET_KEY is %s, so it was replaced with a random key for this run. "
        "Set a random value in .env to keep sessions across restarts: "
        'python -c "import secrets; print(secrets.token_hex(32))"' % reason
    )
    return secrets.token_hex(32), warning


app = Flask(__name__)
app.secret_key, _secret_key_warning = resolve_secret_key()

# Defence in depth for the session cookie: it now carries only a store id, but
# it is still worth being explicit about the flags.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_NAME="my_daily_driver",
)

if _secret_key_warning:
    print("[warning] %s" % _secret_key_warning, file=sys.stderr)

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
OAUTH_STATE_KEY = "github_oauth_state"
CSRF_SESSION_KEY = "form_csrf_token"
SID_SESSION_KEY = "sid"

# Everything the integration classes raise for a bad credential, a dead endpoint
# or a changed upstream schema. A provider that fails this way is reported as
# disconnected instead of taking the whole dashboard down with it.
INTEGRATION_ERRORS = (ValueError, RuntimeError, requests.RequestException)

# Authenticated integrations are reused across requests so the payload cache in
# each integration class (CACHE_TTL_SECONDS) can actually do its job.
_INTEGRATIONS = {}
MAX_INTEGRATION_INSTANCES = 8

# Access tokens are held here rather than in the session cookie, which is signed
# but not encrypted and therefore readable by anything that can see the cookie.
# The cookie carries only a random store id, matching the design note that the
# tokens are kept in the backend server. This is in-process, so restarting the
# server disconnects every browser until it reconnects.
_CREDENTIAL_STORE = {}
CREDENTIAL_TTL_SECONDS = 60 * 60 * 24 * 30
MAX_CREDENTIAL_SESSIONS = 32

HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>My Daily Driver</title>
    <style>
      :root {
        --bg: #0b1020;
        --bg-soft: #141b2d;
        --panel: rgba(17, 24, 39, 0.86);
        --panel-border: rgba(148, 163, 184, 0.18);
        --text: #e5eefb;
        --muted: #9aa8bd;
        --accent: #7dd3fc;
        --accent-strong: #38bdf8;
        --green: #34d399;
        --amber: #fbbf24;
        --red: #fb7185;
        --shadow: 0 18px 40px rgba(15, 23, 42, 0.45);
      }
      * { box-sizing: border-box; }
      html, body { margin: 0; min-height: 100%; background: radial-gradient(circle at top, #111a2e 0%, #0a1020 35%, #050b14 100%); color: var(--text); font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
      body { display: flex; justify-content: center; padding: 32px 18px 54px; }
      .shell { width: min(1180px, 100%); }
      .topbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 18px 20px; border: 1px solid var(--panel-border); background: rgba(15, 23, 42, 0.7); backdrop-filter: blur(18px); border-radius: 22px; box-shadow: var(--shadow); }
      .eyebrow { margin: 0; color: var(--muted); font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase; }
      h1 { margin: 4px 0 0; font-size: clamp(1.8rem, 2.5vw, 2.8rem); letter-spacing: -0.05em; }
      .timebox { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; background: rgba(15, 23, 42, 0.9); border: 1px solid var(--panel-border); padding: 12px 16px; border-radius: 16px; }
      #time { font-size: clamp(1.1rem, 2vw, 1.8rem); font-weight: 600; }
      #date { font-size: 0.8rem; color: var(--muted); }
      .signout { margin-top: 6px; font-size: 0.72rem; color: var(--muted); text-decoration: none; border-bottom: 1px solid rgba(148, 163, 184, 0.35); }
      .signout:hover { color: var(--text); }
      .overview { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; margin-top: 22px; }
      .card { background: rgba(15, 23, 42, 0.82); border: 1px solid var(--panel-border); border-radius: 24px; padding: 18px 20px; box-shadow: var(--shadow); }
      .card h2 { margin: 0 0 10px; font-size: 0.78rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }
      .metric { font-size: clamp(2rem, 3vw, 2.7rem); margin: 0; font-weight: 700; letter-spacing: -0.06em; }
      .thumb { font-size: 0.94rem; color: var(--muted); margin-top: 8px; }
      .focus { background: linear-gradient(135deg, rgba(56,189,248,0.16), rgba(125,211,252,0.04)); }
      .widgets { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; margin-top: 24px; }
      .widget { min-height: 260px; }
      .cta { margin-top: 12px; display: inline-flex; align-items: center; justify-content: center; width: 100%; padding: 12px 14px; background: rgba(56,189,248,0.14); color: var(--text); border: 1px solid rgba(125,211,252,0.3); border-radius: 12px; text-decoration: none; font-weight: 600; }
      .cta.secondary { background: rgba(52, 211, 153, 0.12); border-color: rgba(52, 211, 153, 0.32); }
      ul { padding-left: 18px; margin: 10px 0 0; color: var(--muted); }
      li + li { margin-top: 8px; }
      .status-pill { display: inline-flex; align-items: center; gap: 8px; border-radius: 999px; background: rgba(52,211,153,0.12); border: 1px solid rgba(52,211,153,0.32); color: #d7fff3; padding: 8px 10px; font-size: 0.8rem; }
      .status-pill.warn { background: rgba(251, 191, 36, 0.12); border-color: rgba(251,191,36,0.32); color: #ffe7a8; }
      .status-pill.alert { background: rgba(251, 113, 133, 0.12); border-color: rgba(251,113,133,0.32); color: #ffcad4; }
      .muted { color: var(--muted); }
      @media (max-width: 900px) {
        .overview, .widgets { grid-template-columns: 1fr; }
        .topbar { display: block; }
        .timebox { align-items: flex-start; margin-top: 16px; }
      }
    </style>
  </head>
  <body>
    <div class="shell">
      <header class="topbar">
        <div>
          <p class="eyebrow" id="greeting-label">Good evening</p>
          <h1>Daily Driver</h1>
        </div>
        <div class="timebox">
          <span id="time">--:--</span>
          <span id="date">--</span>
          <a class="signout" href="/logout">Disconnect accounts</a>
        </div>
      </header>

      <section class="overview">
        <article class="card focus">
          <h2>Today</h2>
          <p id="today-status" class="metric">Loading</p>
          <div id="today-pill" class="status-pill">Syncing</div>
        </article>
        <article class="card">
          <h2>GitHub</h2>
          <p id="github-count" class="metric">0</p>
          <div id="github-meta" class="thumb">Waiting for OAuth</div>
        </article>
        <article class="card">
          <h2>LeetCode</h2>
          <p id="leetcode-count" class="metric">0</p>
          <div id="leetcode-meta" class="thumb">Waiting for OAuth</div>
        </article>
      </section>

      <section class="widgets">
        <article class="card widget">
          <h2>GitHub</h2>
          <div id="github-widget-body">
            <p class="muted">Your recent activity will appear here after auth.</p>
          </div>
          <a id="github-auth-link" class="cta" href="/auth/github">Connect GitHub</a>
        </article>
        <article class="card widget">
          <h2>LeetCode</h2>
          <div id="leetcode-widget-body">
            <p class="muted">Your daily solves will appear here after auth.</p>
          </div>
          <a id="leetcode-auth-link" class="cta secondary" href="/auth/leetcode">Connect LeetCode</a>
        </article>
        <article class="card widget">
          <h2>Focus</h2>
          <div id="focus-body">
            <ul>
              <li>Review your GitHub activity.</li>
              <li>Target one algorithm challenge.</li>
              <li>Ship one meaningful update.</li>
            </ul>
          </div>
        </article>
      </section>
    </div>

    <script>
      function formatDateTime(value) {
        const date = new Date(value);
        const time = date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
        const calendar = date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
        return { time, calendar };
      }

      function renderDashboard(data) {
        const greetingLabel = document.getElementById('greeting-label');
        greetingLabel.textContent = data.greeting || 'Hello';

        const timeEl = document.getElementById('time');
        const dateEl = document.getElementById('date');
        const formatted = formatDateTime(data.time || new Date().toISOString());
        timeEl.textContent = formatted.time;
        dateEl.textContent = formatted.calendar;

        const statusEl = document.getElementById('today-status');
        const pillEl = document.getElementById('today-pill');
        const daily = data.daily_summary || {};
        if (daily.commit_today || daily.solved_today) {
          statusEl.textContent = daily.summary || 'You are on track.';
          pillEl.textContent = daily.commit_today && daily.solved_today ? 'Green day' : 'Progress made';
          pillEl.className = 'status-pill';
        } else {
          statusEl.textContent = 'No action yet';
          pillEl.textContent = 'No progress today';
          pillEl.className = 'status-pill alert';
        }

        const github = data.github || {};
        const leetcode = data.leetcode || {};

        document.getElementById('github-count').textContent = github.activity_count || 0;
        document.getElementById('leetcode-count').textContent = leetcode.today_solved_count || 0;
        document.getElementById('github-meta').textContent = github.connected ? `${github.username || 'GitHub'} · ${github.commit_today ? 'pushed today' : 'quiet day'}` : 'Connect GitHub to enable live data';
        document.getElementById('leetcode-meta').textContent = leetcode.connected ? `${leetcode.username || 'LeetCode'} · ${leetcode.today_solved_count ? 'solved today' : 'no solve today'}` : 'Connect LeetCode to enable live data';

        const githubWidget = document.getElementById('github-widget-body');
        const leetcodeWidget = document.getElementById('leetcode-widget-body');
        const focusBody = document.getElementById('focus-body');

        if (github.connected) {
          githubWidget.innerHTML = `
            <p><strong>${github.username || 'GitHub'}</strong></p>
            <ul>
              <li>Activity in the last 30 days: ${github.activity_count || 0}</li>
              <li>Commit today: ${github.commit_today ? 'Yes' : 'No'}</li>
              <li>Current streak: ${github.current_streak || 0} days</li>
              <li>Top repo: ${github.top_repo || 'No public repos yet'}</li>
            </ul>
          `;
          document.getElementById('github-auth-link').textContent = 'Reconnect GitHub';
        } else {
          githubWidget.innerHTML = '<p class="muted">Your recent activity will appear here after auth.</p>';
        }

        if (leetcode.connected) {
          leetcodeWidget.innerHTML = `
            <p><strong>${leetcode.username || 'LeetCode'}</strong></p>
            <ul>
              <li>Solved today: ${leetcode.today_solved_count || 0}</li>
              <li>Current streak: ${leetcode.current_streak || 0} days</li>
              <li>Acceptance: ${leetcode.acceptance_rate || 0}%</li>
            </ul>
          `;
          document.getElementById('leetcode-auth-link').textContent = 'Reconnect LeetCode';
        } else {
          leetcodeWidget.innerHTML = '<p class="muted">Your daily solves will appear here after auth.</p>';
        }

        focusBody.innerHTML = `
          <ul>
            <li>${daily.status || 'Keep building with momentum.'}</li>
            <li>${github.connected ? 'GitHub is connected and active.' : 'Connect GitHub for commit tracking.'}</li>
            <li>${leetcode.connected ? 'LeetCode is connected and active.' : 'Connect LeetCode for solved tracking.'}</li>
          </ul>
        `;
      }

      fetch('/api/dashboard')
        .then((response) => response.json())
        .then((data) => renderDashboard(data))
        .catch((error) => {
          document.getElementById('today-status').textContent = 'Unable to load';
          document.getElementById('today-pill').textContent = 'Retry later';
          document.getElementById('today-pill').className = 'status-pill warn';
          console.error(error);
        });
    </script>
  </body>
</html>
"""


LEETCODE_LOGIN_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Connect LeetCode</title>
    <style>
      :root { --bg-soft: #141b2d; --panel-border: rgba(148, 163, 184, 0.18); --text: #e5eefb; --muted: #9aa8bd; --green: #34d399; --red: #fb7185; }
      * { box-sizing: border-box; }
      body { margin: 0; min-height: 100%; padding: 48px 18px; display: flex; justify-content: center; background: radial-gradient(circle at top, #111a2e 0%, #0a1020 35%, #050b14 100%); color: var(--text); font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
      .card { width: min(560px, 100%); background: rgba(15, 23, 42, 0.82); border: 1px solid var(--panel-border); border-radius: 24px; padding: 28px; box-shadow: 0 18px 40px rgba(15, 23, 42, 0.45); }
      h1 { margin: 0 0 6px; font-size: 1.7rem; letter-spacing: -0.04em; }
      p { line-height: 1.55; }
      .muted { color: var(--muted); }
      .note { background: rgba(56,189,248,0.1); border: 1px solid rgba(125,211,252,0.28); border-radius: 14px; padding: 12px 14px; font-size: 0.86rem; color: var(--muted); }
      .error { background: rgba(251,113,133,0.1); border: 1px solid rgba(251,113,133,0.34); border-radius: 14px; padding: 12px 14px; color: #ffcad4; }
      label { display: block; margin-top: 16px; font-size: 0.8rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
      input { width: 100%; margin-top: 8px; padding: 12px 14px; background: #0b1020; color: var(--text); border: 1px solid var(--panel-border); border-radius: 12px; font-family: inherit; font-size: 0.95rem; }
      input:focus { outline: 2px solid rgba(125,211,252,0.5); outline-offset: 1px; }
      .actions { display: flex; gap: 12px; align-items: center; margin-top: 24px; }
      .cta { display: inline-flex; align-items: center; justify-content: center; padding: 12px 20px; background: rgba(52, 211, 153, 0.14); border: 1px solid rgba(52, 211, 153, 0.34); border-radius: 12px; color: var(--text); text-decoration: none; font-weight: 600; cursor: pointer; font-family: inherit; font-size: 1rem; }
      .ghost { background: none; border-color: var(--panel-border); color: var(--muted); font-weight: 500; }
      code { background: #0b1020; border-radius: 6px; padding: 2px 6px; }
    </style>
  </head>
  <body>
    <main class="card">
      <h1>Connect LeetCode</h1>
      <p class="muted">LeetCode does not offer an OAuth app for third-party dashboards, so
      the dashboard authenticates with the same <code>LEETCODE_SESSION</code> cookie your
      browser already uses.</p>

      {% if error %}<p class="error">{{ error }}</p>{% endif %}

      <p class="note">
        Sign in at <strong>leetcode.com</strong>, open DevTools &rarr; Application (or Storage) &rarr;
        Cookies, then copy the value of <code>LEETCODE_SESSION</code>. The optional
        <code>csrftoken</code> cookie is only needed for write requests. Both expire
        every few weeks, so you will reconnect occasionally.
      </p>

      <form method="post" action="{{ url_for('leetcode_auth') }}">
        <input type="hidden" name="csrf_token" value="{{ csrf }}" />
        <label for="session_token">LEETCODE_SESSION cookie</label>
        <input id="session_token" name="session_token" value="{{ session_token or '' }}" autocomplete="off" spellcheck="false" required />

        <label for="csrftoken">csrftoken cookie (optional)</label>
        <input id="csrftoken" name="csrftoken" value="{{ csrftoken or '' }}" autocomplete="off" spellcheck="false" />

        <label for="username">Username (optional)</label>
        <input id="username" name="username" value="{{ username or '' }}" placeholder="Detected automatically when you are signed in" autocomplete="off" spellcheck="false" />

        <div class="actions">
          <button class="cta" type="submit">Connect LeetCode</button>
          <a class="cta ghost" href="/">Cancel</a>
        </div>
      </form>
    </main>
  </body>
</html>
"""


def get_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


def session_id():
    """Random id naming this browser session's entry in the credential store."""
    sid = session.get(SID_SESSION_KEY)
    if not sid:
        sid = secrets.token_urlsafe(24)
        session[SID_SESSION_KEY] = sid
    return sid


def credential_entry(create=False):
    """This session's store entry, marked as just used."""
    sid = session_id()
    entry = _CREDENTIAL_STORE.get(sid)
    if entry is None and create:
        entry = {"touched": datetime.now(timezone.utc), "providers": {}}
        _CREDENTIAL_STORE[sid] = entry
    if entry is not None:
        entry["touched"] = datetime.now(timezone.utc)
    return entry


def stored_credentials(provider):
    """Credentials held server side for the current session, if any."""
    entry = credential_entry()
    return dict((entry or {}).get("providers", {}).get(provider) or {})


def store_credentials(provider, values):
    """Remember credentials for this session and refresh its expiry."""
    entry = credential_entry(create=True)
    entry["providers"][provider] = {**(entry["providers"].get(provider) or {}), **values}
    prune_credential_store()
    return entry["providers"][provider]


def forget_credentials(provider=None):
    """
    Drop stored credentials for this session.

    Called on logout and whenever a provider reconnects, so a rotated token never
    lingers behind the one that replaced it.
    """
    sid = session_id()
    entry = _CREDENTIAL_STORE.get(sid)
    if entry is None:
        return
    if provider is None:
        _CREDENTIAL_STORE.pop(sid, None)
        return

    entry["providers"].pop(provider, None)
    if not entry["providers"]:
        _CREDENTIAL_STORE.pop(sid, None)


def prune_credential_store():
    """
    Evict sessions that have gone quiet, and cap how many are held.

    Without this the store would keep every token ever issued for the lifetime of
    the process. Least recently used goes first.
    """
    now = datetime.now(timezone.utc)
    for sid, entry in list(_CREDENTIAL_STORE.items()):
        if (now - entry["touched"]).total_seconds() > CREDENTIAL_TTL_SECONDS:
            _CREDENTIAL_STORE.pop(sid, None)

    overflow = len(_CREDENTIAL_STORE) - MAX_CREDENTIAL_SESSIONS
    if overflow > 0:
        least_recent = sorted(_CREDENTIAL_STORE.items(), key=lambda item: item[1]["touched"])
        for sid, _ in least_recent[:overflow]:
            _CREDENTIAL_STORE.pop(sid, None)


def prune_integrations():
    """
    Keep the instance cache from growing for the life of the process.

    Entries are only ever added when a credential changes, which is rare, but a
    long-running process should not be the thing that decides when a token is
    forgotten. Least recently used goes first.
    """
    overflow = len(_INTEGRATIONS) - MAX_INTEGRATION_INSTANCES
    if overflow <= 0:
        return
    for key, _ in list(_INTEGRATIONS.items())[:overflow]:
        _INTEGRATIONS.pop(key, None)


def auth_disabled(provider):
    """
    Whether this browser session explicitly disconnected a provider.

    Credentials in .env apply to every session, which would make the logout
    button look broken: the next request would silently reconnect. Remembering
    the choice keeps the disconnect honest until the user connects again.
    """
    return provider in (session.get("auth_disabled") or [])


def set_auth_disabled(provider, disabled):
    providers = [name for name in (session.get("auth_disabled") or []) if name != provider]
    if disabled:
        providers.append(provider)
    session["auth_disabled"] = providers


def github_integration():
    """
    Return an authenticated GitHubIntegration, or None when GitHub is unavailable.
    """
    if auth_disabled("github"):
        return None
    stored = stored_credentials("github")
    token = stored.get("token") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    username = stored.get("username") or os.environ.get("GITHUB_USERNAME")
    return _integration_for(GitHubIntegration, token, {"username": username} if username else None)


def leetcode_integration():
    """
    Return an authenticated LeetCodeIntegration, or None when it is unavailable.
    """
    if auth_disabled("leetcode"):
        return None
    stored = stored_credentials("leetcode")
    token = stored.get("token") or os.environ.get("LEETCODE_SESSION")
    if not token:
        return None
    credentials = {
        "session_token": token,
        "csrftoken": stored.get("csrftoken") or os.environ.get("LEETCODE_CSRF_TOKEN"),
    }
    username = stored.get("username") or os.environ.get("LEETCODE_USERNAME")
    if username:
        credentials["username"] = username
    return _integration_for(LeetCodeIntegration, token, credentials)


def _integration_for(factory, token, credentials):
    """
    Build and cache one integration instance per credential.

    The classes only cache their API payload per instance, so a fresh instance
    per request would refetch everything on every page load. A rejected token is
    evicted instead of cached, so a reconnected account is picked up immediately.
    """
    key = (factory, hashlib.sha256(token.encode("utf-8")).hexdigest())
    integration = _INTEGRATIONS.get(key)
    if integration is not None and integration.is_authenticated:
        return integration

    integration = factory()
    try:
        integration.authenticate(credentials if credentials is not None else token)
    except INTEGRATION_ERRORS:
        _INTEGRATIONS.pop(key, None)
        return None

    _INTEGRATIONS[key] = integration
    prune_integrations()
    return integration


def provider_status():
    return {
        "github_connected": github_integration() is not None,
        "leetcode_connected": leetcode_integration() is not None,
    }


def github_disconnected():
    return {
        "connected": False,
        "username": "Not connected",
        "activity_count": 0,
        "commit_today": False,
        "today_commit_count": 0,
        "top_repo": "N/A",
    }


def leetcode_disconnected(username=None):
    return {
        "connected": False,
        "username": username or "Not connected",
        "today_solved_count": 0,
        "solved_today": False,
        "current_streak": 0,
        "acceptance_rate": 0,
    }


def last_day_count(series):
    """Count for the most recent day of a ``[{"count": ...}, ...]`` series."""
    days = (series or {}).get("days") or []
    return days[-1].get("count", 0) if days else 0


def fetch_github_data():
    integration = github_integration()
    if integration is None:
        return github_disconnected()

    try:
        payload = integration.core_functionality()
    except INTEGRATION_ERRORS:
        return github_disconnected()

    user = payload.get("user") or {}
    contributions = payload.get("contributions") or {}
    repositories = payload.get("repositories") or []
    today_count = last_day_count(contributions)

    return {
        "connected": True,
        "username": user.get("login"),
        "activity_count": contributions.get("total", 0),
        "commit_today": today_count > 0,
        "today_commit_count": today_count,
        "current_streak": contributions.get("current_streak", 0),
        "top_repo": repositories[0].get("name") if repositories else "No public repos yet",
        "public_repos": user.get("public_repos", 0),
    }


def fetch_leetcode_data():
    fallback_username = stored_credentials("leetcode").get("username") or os.environ.get("LEETCODE_USERNAME")
    integration = leetcode_integration()
    if integration is None:
        return leetcode_disconnected(fallback_username)

    try:
        payload = integration.core_functionality()
    except INTEGRATION_ERRORS:
        return leetcode_disconnected(fallback_username)

    user = payload.get("user") or {}
    streak = payload.get("streak") or {}
    today_count = last_day_count(streak) if streak.get("available") else 0
    if not streak.get("available"):
        # The heatmap endpoint is bot protected, so fall back to the timestamped
        # submission list before reporting an empty day.
        today = datetime.now(timezone.utc).date()
        for solution in payload.get("recent_solutions") or []:
            if is_today(solution.get("solved_at"), today):
                today_count += 1

    return {
        "connected": True,
        "username": user.get("username") or fallback_username,
        "today_solved_count": today_count,
        "solved_today": today_count > 0,
        "current_streak": streak.get("current_streak", 0) if streak.get("available") else 0,
        "acceptance_rate": user.get("acceptance_rate", 0),
    }


def is_today(epoch_seconds, today=None):
    """Whether a LeetCode submission timestamp falls on the current UTC day."""
    if not epoch_seconds:
        return False
    try:
        stamp = datetime.fromtimestamp(float(epoch_seconds), tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return False
    return stamp.date() == (today or datetime.now(timezone.utc).date())


def build_dashboard_payload():
    github = fetch_github_data()
    leetcode = fetch_leetcode_data()

    commit_today = bool(github.get("commit_today"))
    solved_today = bool(leetcode.get("solved_today"))
    if commit_today and solved_today:
        status = "You shipped code and solved a problem today."
    elif commit_today:
        status = "You pushed code today. Keep the streak alive."
    elif solved_today:
        status = "You solved a problem today. Strong momentum."
    else:
        status = "No commit or LeetCode solve yet today."

    payload = {
        "greeting": get_greeting(),
        "time": datetime.now().isoformat(),
        "github": {
            **github,
            "activity_count": github.get("activity_count", 0),
            "connected": github.get("connected", False),
        },
        "leetcode": {
            **leetcode,
            "connected": leetcode.get("connected", False),
        },
        "daily_summary": {
            "commit_today": commit_today,
            "solved_today": solved_today,
            "status": status,
            "summary": status,
        },
    }
    return payload


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/dashboard")
def dashboard_api():
    payload = build_dashboard_payload()
    return jsonify(payload)


@app.route("/api/auth/status")
def auth_status():
    return jsonify(provider_status())


def github_redirect_uri():
    """
    The callback URL registered on the GitHub OAuth app.

    Falls back to the current request so a fresh checkout works without
    configuring it; set GITHUB_REDIRECT_URI when the app is reached on another
    hostname or port.
    """
    return os.environ.get("GITHUB_REDIRECT_URI") or url_for("github_callback", _external=True)


def issue_oauth_state():
    """Store a CSRF nonce for the GitHub authorize round trip."""
    state = secrets.token_urlsafe(24)
    session[OAUTH_STATE_KEY] = state
    return state


def consume_oauth_state(received):
    """
    Verify and clear the CSRF nonce.

    GitHub echoes the state it was given, so a mismatch means the callback did
    not come from the authorize request this browser session started.
    """
    expected = session.pop(OAUTH_STATE_KEY, None)
    if not expected or not received:
        return False
    return secrets.compare_digest(expected, received)


@app.route("/auth/github")
def github_auth():
    client_id = os.environ.get("GITHUB_CLIENT_ID")
    client_secret = os.environ.get("GITHUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        return jsonify({
            "error": "GitHub OAuth is not configured. Set GITHUB_CLIENT_ID and "
            "GITHUB_CLIENT_SECRET in .env, or provide GITHUB_TOKEN for a "
            "personal access token."
        }), 400

    params = {
        "client_id": client_id,
        "redirect_uri": github_redirect_uri(),
        "scope": "read:user",
        "state": issue_oauth_state(),
    }
    return redirect(GITHUB_AUTHORIZE_URL + "?" + urlencode(params))


@app.route("/oauth/github/callback")
def github_callback():
    if request.args.get("error"):
        return jsonify({
            "error": "GitHub denied the authorization request.",
            "details": request.args.get("error_description") or request.args.get("error"),
        }), 400

    if not consume_oauth_state(request.args.get("state")):
        return jsonify({"error": "GitHub OAuth state mismatch. Start the login again from the dashboard."}), 400

    code = request.args.get("code")
    if not code:
        return jsonify({"error": "GitHub OAuth code missing."}), 400

    integration = GitHubIntegration()
    try:
        user = integration.authenticate({
            "client_id": os.environ.get("GITHUB_CLIENT_ID"),
            "client_secret": os.environ.get("GITHUB_CLIENT_SECRET"),
            "code": code,
            "redirect_uri": github_redirect_uri(),
        })
    except INTEGRATION_ERRORS as exc:
        return jsonify({"error": "GitHub authentication failed.", "details": str(exc)}), 400

    store_credentials("github", {"token": integration.get_access_token(), "username": user.get("login")})
    _INTEGRATIONS.clear()
    set_auth_disabled("github", False)
    return redirect("/")


def csrf_token():
    """Stable per-session token embedded in the LeetCode form."""
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(24)
        session[CSRF_SESSION_KEY] = token
    return token


def csrf_valid(submitted):
    """
    Check a submitted form token.

    The form writes a credential into the session, so without this a third party
    could point someone's dashboard at their own account. The token is kept in
    the session rather than consumed, so a rejected submission can be retried.
    """
    expected = session.get(CSRF_SESSION_KEY)
    if not expected or not submitted:
        return False
    return secrets.compare_digest(expected, submitted)


def render_leetcode_login(error=None, status=200, **values):
    values.setdefault("csrf", csrf_token())
    return render_template_string(
        LEETCODE_LOGIN_TEMPLATE, error=error, **values
    ), status


@app.route("/auth/leetcode", methods=["GET", "POST"])
def leetcode_auth():
    """
    Connect LeetCode with the session cookie from a signed-in browser.

    LeetCode publishes no OAuth app for third parties, so the authorize and token
    endpoints are not available to this dashboard. The private GraphQL endpoint
    the website itself uses only checks the LEETCODE_SESSION cookie.
    """
    if request.method == "GET":
        stored = stored_credentials("leetcode")
        return render_leetcode_login(
            session_token=stored.get("token", ""),
            csrftoken=stored.get("csrftoken", ""),
            username=stored.get("username", ""),
            csrf=csrf_token(),
        )

    submitted_token = (request.form.get("session_token") or "").strip()
    if not csrf_valid(request.form.get("csrf_token")):
        return render_leetcode_login(
            error="This form expired. Reload the page and try again.", status=400
        )

    session_token = submitted_token
    csrftoken = (request.form.get("csrftoken") or "").strip()
    username = (request.form.get("username") or "").strip()
    values = {
        "session_token": session_token,
        "csrftoken": csrftoken,
        "username": username,
    }

    if not session_token:
        return render_leetcode_login(
            error="Paste the LEETCODE_SESSION cookie value from leetcode.com.", status=400, **values
        )

    integration = LeetCodeIntegration()
    credentials = {"session_token": session_token, "csrftoken": csrftoken}
    if username:
        credentials["username"] = username
    try:
        authenticated_user = integration.authenticate(credentials)
    except requests.RequestException as exc:
        return render_leetcode_login(
            error="Could not reach leetcode.com: %s" % exc, status=502, **values
        )
    except (ValueError, RuntimeError) as exc:
        # ValueError is a rejected cookie, RuntimeError is a GraphQL failure such
        # as LeetCode changing the shape of the query.
        return render_leetcode_login(error=str(exc), status=400, **values)

    store_credentials("leetcode", {
        "token": session_token,
        "csrftoken": csrftoken,
        "username": authenticated_user or username,
    })
    _INTEGRATIONS.clear()
    set_auth_disabled("leetcode", False)
    return redirect("/")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    forget_credentials()
    session.clear()
    _INTEGRATIONS.clear()
    # The .env credentials would otherwise reconnect both providers on the very
    # next request, so the disconnect is recorded instead of silently undone.
    set_auth_disabled("github", True)
    set_auth_disabled("leetcode", True)
    return redirect("/")


def env_flag(name, default=False):
    """Read a boolean from the environment, so 1/true/yes/on all mean true."""
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def main():
    """
    Run the development server.

    The Werkzeug debugger that comes with debug mode is a remote shell for anyone
    who can reach it, so the debugger is off unless asked for and the server binds
    to loopback unless asked otherwise.
    """
    host = os.environ.get("HOST") or "127.0.0.1"
    # An empty or non-numeric PORT is an easy mistake to make in .env, and
    # int("") would otherwise crash with a bare ValueError.
    try:
        port = int(os.environ.get("PORT") or 5000)
    except ValueError:
        print(
            "[warning] PORT=%r is not a number, falling back to 5000"
            % os.environ.get("PORT"),
            file=sys.stderr,
        )
        port = 5000
    debug = env_flag("FLASK_DEBUG", default=env_flag("DEBUG"))

    if debug and host not in ("127.0.0.1", "localhost", "::1"):
        print(
            "[warning] FLASK_DEBUG is on while binding to %s, which exposes the "
            "Werkzeug debugger to the network. Set HOST=127.0.0.1 to keep it local."
            % host,
            file=sys.stderr,
        )

    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
