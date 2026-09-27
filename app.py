import hashlib
import os
import secrets
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

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

# Why the most recent authenticate() call failed, per provider, so the dashboard
# can say what went wrong instead of just reporting "not connected".
_LAST_ERROR = {}

# Access tokens are held here rather than in the session cookie, which is signed
# but not encrypted and therefore readable by anything that can see the cookie.
# The cookie carries only a random store id, matching the design note that the
# tokens are kept in the backend server. This is in-process, so restarting the
# server disconnects every browser until it reconnects.
_CREDENTIAL_STORE = {}
CREDENTIAL_TTL_SECONDS = 60 * 60 * 24 * 30
MAX_CREDENTIAL_SESSIONS = 32

HTML_TEMPLATE = r"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="color-scheme" content="dark" />
    <title>Daily Driver</title>
    <style>
      :root {
        --bg: #070b16;
        --bg-glow-1: rgba(56, 189, 248, 0.16);
        --bg-glow-2: rgba(167, 139, 250, 0.14);
        --panel: rgba(16, 24, 43, 0.72);
        --panel-solid: #101a2e;
        --border: rgba(148, 163, 184, 0.16);
        --border-strong: rgba(148, 163, 184, 0.3);
        --text: #eaf1fb;
        --muted: #97a6bf;
        --faint: #6b7c96;
        --good: #34d399;
        --warn: #fbbf24;
        --bad: #fb7185;
        --github: #a78bfa;
        --leetcode: #fbbf24;
        --radius: 20px;
        --shadow: 0 22px 48px rgba(3, 7, 18, 0.55);
        --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
      }

      * { box-sizing: border-box; }

      html, body { height: 100%; }

      body {
        margin: 0;
        background:
          radial-gradient(1100px 620px at 12% -10%, var(--bg-glow-1), transparent 60%),
          radial-gradient(900px 520px at 92% 4%, var(--bg-glow-2), transparent 62%),
          var(--bg);
        background-attachment: fixed;
        color: var(--text);
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 16px;
        line-height: 1.5;
        -webkit-font-smoothing: antialiased;
      }

      .shell { max-width: 1180px; margin: 0 auto; padding: 34px 22px 40px; }

      /* ---------- header ---------- */

      .topbar {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 26px;
        flex-wrap: wrap;
      }

      .eyebrow {
        margin: 0;
        font-size: 0.74rem;
        font-weight: 600;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: var(--faint);
      }

      h1 {
        margin: 6px 0 0;
        font-size: clamp(1.7rem, 3.4vw, 2.5rem);
        font-weight: 700;
        letter-spacing: -0.035em;
        line-height: 1.12;
      }

      .sub { margin: 10px 0 0; color: var(--muted); max-width: 46ch; }

      .clock { text-align: right; margin-left: auto; }

      .clock .time {
        margin: 0;
        font-size: clamp(2.4rem, 6vw, 3.4rem);
        font-weight: 700;
        letter-spacing: -0.05em;
        font-variant-numeric: tabular-nums;
        line-height: 1;
      }

      .clock .time .secs {
        font-size: 0.4em;
        font-weight: 600;
        color: var(--faint);
        margin-left: 4px;
        letter-spacing: 0;
      }

      .clock .date {
        margin: 8px 0 0;
        color: var(--muted);
        font-size: 0.88rem;
        letter-spacing: 0.01em;
      }

      /* ---------- pulse row ---------- */

      .pulse {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
        margin-top: 30px;
      }

      .pulse-item {
        position: relative;
        overflow: hidden;
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 17px 18px;
        box-shadow: var(--shadow);
        backdrop-filter: blur(14px);
      }

      .pulse-item::after {
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 3px;
        background: var(--accent, var(--muted));
        opacity: 0.85;
      }

      .pulse-item .label {
        margin: 0;
        font-size: 0.73rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--faint);
      }

      .pulse-item .value {
        margin: 6px 0 0;
        font-size: 2.35rem;
        font-weight: 700;
        letter-spacing: -0.05em;
        font-variant-numeric: tabular-nums;
        line-height: 1;
      }

      .pulse-item .value .unit { font-size: 0.42em; font-weight: 600; color: var(--muted); margin-left: 5px; letter-spacing: 0; }

      .pulse-item .note { margin: 7px 0 0; font-size: 0.82rem; color: var(--muted); }

      /* ---------- provider grid ---------- */

      .grid {
        display: grid;
        grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
        gap: 18px;
        margin-top: 18px;
      }

      .card {
        display: flex;
        flex-direction: column;
        min-width: 0;
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 22px;
        box-shadow: var(--shadow);
        backdrop-filter: blur(14px);
      }

      .card-head { display: flex; align-items: center; gap: 13px; }

      .avatar {
        width: 46px;
        height: 46px;
        flex: none;
        border-radius: 14px;
        background: linear-gradient(140deg, var(--accent), rgba(255, 255, 255, 0.06));
        color: #0b1020;
        display: grid;
        place-items: center;
        font-weight: 700;
        font-size: 1.05rem;
        overflow: hidden;
      }

      .avatar img { width: 100%; height: 100%; object-fit: cover; }

      .card-head .who { min-width: 0; flex: 1 1 auto; }

      .card-head .who .handle {
        margin: 0;
        font-weight: 650;
        font-size: 1.02rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .card-head .who .brand {
        margin: 1px 0 0;
        font-size: 0.73rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--accent);
      }

      .head-actions { margin-left: auto; display: flex; gap: 8px; flex: 0 0 auto; }

      .btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 7px 12px;
        border-radius: 999px;
        border: 1px solid var(--border-strong);
        background: rgba(148, 163, 184, 0.08);
        color: var(--text);
        font-size: 0.8rem;
        font-weight: 600;
        text-decoration: none;
        white-space: nowrap;
        cursor: pointer;
        transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
      }

      .btn:hover { background: rgba(148, 163, 184, 0.18); transform: translateY(-1px); }
      .btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
      .btn.ghost { background: transparent; }

      .stats {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        margin-top: 20px;
      }

      .stat {
        min-width: 0;
        background: rgba(8, 14, 28, 0.5);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 12px 13px;
      }

      .stat .k {
        margin: 0;
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--faint);
      }

      .stat .v {
        margin: 5px 0 0;
        font-size: 1.45rem;
        font-weight: 700;
        letter-spacing: -0.035em;
        font-variant-numeric: tabular-nums;
        line-height: 1.1;
      }

      .stat .v.ok { color: var(--good); }
      .stat .v.idle { color: var(--faint); }

      /* ---------- activity strip ---------- */

      .block { margin-top: 20px; }

      .block-title {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 10px;
        margin: 0 0 9px;
        font-size: 0.71rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--faint);
      }

      /* A grid of equal columns, not flex: 30 flex children with a min-width
         overflowed their container on narrow viewports. */
      .strip {
        display: grid;
        grid-auto-flow: column;
        grid-auto-columns: minmax(2px, 1fr);
        align-items: end;
        gap: 3px;
        height: 62px;
        padding: 8px 10px;
        background: rgba(8, 14, 28, 0.5);
        border: 1px solid var(--border);
        border-radius: 14px;
      }

      .strip .bar {
        width: 100%;
        border-radius: 2px;
        background: var(--accent);
        opacity: 0.28;
        min-height: 3px;
        transition: opacity 0.15s ease;
      }

      .strip .bar[data-level="1"] { opacity: 0.5; }
      .strip .bar[data-level="2"] { opacity: 0.74; }
      .strip .bar[data-level="3"] { opacity: 1; }
      .strip .bar[data-level="4"] { opacity: 1; box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.5); }
      .strip .bar.empty { background: var(--faint); opacity: 0.16; }
      .strip .bar:hover { opacity: 1; }

      /* ---------- difficulty bar ---------- */

      .meter {
        display: flex;
        height: 10px;
        border-radius: 999px;
        overflow: hidden;
        background: rgba(8, 14, 28, 0.6);
        border: 1px solid var(--border);
      }

      .meter span { display: block; height: 100%; }
      .meter .e { background: var(--good); }
      .meter .m { background: var(--warn); }
      .meter .h { background: var(--bad); }

      .legend { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 10px; }

      .legend div { display: flex; align-items: center; gap: 7px; min-width: 0; font-size: 0.82rem; color: var(--muted); }
      .legend i { width: 8px; height: 8px; border-radius: 3px; display: block; }
      .legend b { color: var(--text); font-variant-numeric: tabular-nums; }

      /* ---------- disconnected ---------- */

      .empty {
        margin-top: 20px;
        padding: 18px;
        border: 1px dashed var(--border-strong);
        border-radius: 14px;
        background: rgba(8, 14, 28, 0.4);
      }

      .empty p { margin: 0; color: var(--muted); font-size: 0.9rem; }

      .empty .cta { margin-top: 14px; width: fit-content; }

      /* ---------- footer ---------- */

      .footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 14px;
        flex-wrap: wrap;
        margin-top: 26px;
        padding-top: 16px;
        border-top: 1px solid var(--border);
        color: var(--faint);
        font-size: 0.8rem;
      }

      .footer a { color: var(--muted); text-decoration: none; border-bottom: 1px solid var(--border-strong); }
      .footer a:hover { color: var(--text); }

      .dot {
        display: inline-block;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--good);
        margin-right: 7px;
        vertical-align: 1px;
      }

      .dot.stale { background: var(--warn); }
      .dot.down { background: var(--bad); }

      .tick { animation: tick 0.42s ease-out; }

      @keyframes tick {
        0% { transform: translateY(-0.14em); opacity: 0.55; }
        100% { transform: none; opacity: 1; }
      }

      .skeleton {
        background: linear-gradient(90deg, rgba(148, 163, 184, 0.1), rgba(148, 163, 184, 0.2), rgba(148, 163, 184, 0.1));
        background-size: 200% 100%;
        animation: sweep 1.3s linear infinite;
        border-radius: 8px;
        color: transparent;
      }

      @keyframes sweep {
        from { background-position: 200% 0; }
        to { background-position: -200% 0; }
      }

      @media (max-width: 940px) {
        .grid { grid-template-columns: minmax(0, 1fr); }
      }

      @media (max-width: 620px) {
        .shell { padding: 24px 16px 32px; }
        .pulse { grid-template-columns: 1fr; }
        .topbar { align-items: flex-start; }
        .clock { text-align: left; margin-left: 0; }
        .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .card-head { flex-wrap: wrap; }
        .head-actions { margin-left: 0; width: 100%; }
      }

      @media (prefers-reduced-motion: reduce) {
        * { animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }
      }
    </style>
  </head>
  <body>
    <div class="shell">
      <header class="topbar">
        <div class="hello">
          <p class="eyebrow" id="greeting">Loading</p>
          <h1 id="headline">Daily Driver</h1>
          <p class="sub" id="today-status" aria-live="polite">Reading your accounts…</p>
        </div>
        <div class="clock">
          <p class="time"><span id="clock-time">--:--</span><span class="secs" id="clock-secs"></span></p>
          <p class="date" id="clock-date">&nbsp;</p>
        </div>
      </header>

      <section class="pulse" aria-label="Today at a glance">
        <div class="pulse-item" style="--accent: var(--github)">
          <p class="label">Commits today</p>
          <p class="value" id="pulse-commits"><span class="skeleton">&nbsp;</span></p>
          <p class="note" id="pulse-commits-note">Waiting for GitHub</p>
        </div>
        <div class="pulse-item" style="--accent: var(--leetcode)">
          <p class="label">Solved today</p>
          <p class="value" id="pulse-solves"><span class="skeleton">&nbsp;</span></p>
          <p class="note" id="pulse-solves-note">Waiting for LeetCode</p>
        </div>
        <div class="pulse-item" style="--accent: var(--good)">
          <p class="label">Best streak</p>
          <p class="value" id="pulse-streak"><span class="skeleton">&nbsp;</span></p>
          <p class="note" id="pulse-streak-note">Days in a row</p>
        </div>
      </section>

      <main class="grid">
        <section class="card" id="github-card" style="--accent: var(--github)" aria-labelledby="github-brand">
          <div class="card-head">
            <div class="avatar" id="github-avatar" aria-hidden="true"></div>
            <div class="who">
              <p class="handle" id="github-user">GitHub</p>
              <p class="brand" id="github-brand">GitHub</p>
            </div>
            <div class="head-actions">
              <a class="btn ghost" id="github-profile" target="_blank" rel="noopener" hidden>Profile</a>
              <a class="btn" id="github-link" href="/auth/github" hidden>Connect</a>
            </div>
          </div>

          <div id="github-connected">
            <div class="stats">
              <div class="stat">
                <p class="k">30d activity</p>
                <p class="v" id="gh-activity">0</p>
              </div>
              <div class="stat">
                <p class="k">Streak</p>
                <p class="v" id="gh-streak">0</p>
              </div>
              <div class="stat">
                <p class="k">Repos</p>
                <p class="v" id="gh-repos">0</p>
              </div>
            </div>

            <div class="block">
              <p class="block-title"><span>Last 30 days</span><span id="gh-today">nothing yet</span></p>
              <div class="strip" id="gh-strip" role="img" aria-label="Daily public activity for the last 30 days"></div>
            </div>

            <div class="block">
              <p class="block-title"><span>Top repository</span></p>
              <p class="v" id="gh-top-repo" style="margin: 0; font-size: 1.1rem; letter-spacing: -0.02em;">—</p>
            </div>
          </div>

          <div class="empty" id="github-empty" hidden>
            <p id="github-reason">Not connected.</p>
            <a class="btn" id="github-reconnect" href="/auth/github">Connect GitHub</a>
          </div>
        </section>

        <section class="card" id="leetcode-card" style="--accent: var(--leetcode)" aria-labelledby="leetcode-brand">
          <div class="card-head">
            <div class="avatar" id="leetcode-avatar" aria-hidden="true"></div>
            <div class="who">
              <p class="handle" id="leetcode-user">LeetCode</p>
              <p class="brand" id="leetcode-brand">LeetCode</p>
            </div>
            <div class="head-actions">
              <a class="btn ghost" id="leetcode-profile" target="_blank" rel="noopener" hidden>Profile</a>
              <a class="btn" id="leetcode-link" href="/leetcode/login" hidden>Connect</a>
            </div>
          </div>

          <div id="leetcode-connected">
            <div class="stats">
              <div class="stat">
                <p class="k">Solved today</p>
                <p class="v" id="lc-today">0</p>
              </div>
              <div class="stat">
                <p class="k">Streak</p>
                <p class="v" id="lc-streak">0</p>
              </div>
              <div class="stat">
                <p class="k">Acceptance</p>
                <p class="v" id="lc-acceptance">0%</p>
              </div>
            </div>

            <div class="block">
              <p class="block-title"><span>Solved by difficulty</span><span id="lc-total">0 total</span></p>
              <div class="meter" id="lc-meter" role="img" aria-label="Problems solved by difficulty">
                <span class="e" id="lc-e" style="width: 0%"></span>
                <span class="m" id="lc-m" style="width: 0%"></span>
                <span class="h" id="lc-h" style="width: 0%"></span>
              </div>
              <div class="legend">
                <div><i style="background: var(--good)"></i>Easy <b id="lc-easy">0</b></div>
                <div><i style="background: var(--warn)"></i>Medium <b id="lc-medium">0</b></div>
                <div><i style="background: var(--bad)"></i>Hard <b id="lc-hard">0</b></div>
              </div>
            </div>

            <div class="block">
              <p class="block-title"><span>Global ranking</span></p>
              <p class="v" id="lc-ranking" style="margin: 0; font-size: 1.1rem; letter-spacing: -0.02em;">—</p>
            </div>
          </div>

          <div class="empty" id="leetcode-empty" hidden>
            <p id="leetcode-reason">Not connected.</p>
            <a class="btn" id="leetcode-reconnect" href="/leetcode/login">Connect LeetCode</a>
          </div>
        </section>
      </main>

      <footer class="footer">
        <p style="margin: 0"><span class="dot" id="health"></span><span id="updated">Loading…</span></p>
        <p style="margin: 0"><a href="/logout">Sign out</a> · refreshes every minute</p>
      </footer>
    </div>

    <noscript>
      <p style="max-width: 1180px; margin: 0 auto; padding: 0 22px 30px; color: #97a6bf;">
        This dashboard needs JavaScript to read your accounts. The API is still available at
        <a href="/api/dashboard" style="color: #eaf1fb;">/api/dashboard</a>.
      </p>
    </noscript>

    <script>
      const REFRESH_MS = 60000;
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      let lastPayload = null;
      let loadedAt = null;

      const byId = (id) => document.getElementById(id);

      function setText(id, value) {
        const el = byId(id);
        if (el) el.textContent = value;
      }

      function plural(count, word) {
        return count + ' ' + word + (count === 1 ? '' : 's');
      }

      function initials(name) {
        const clean = String(name || '').replace(/[^a-zA-Z0-9 ]/g, ' ').trim();
        if (!clean) return '·';
        return clean.split(/\s+/).slice(0, 2).map((part) => part[0].toUpperCase()).join('');
      }

      function paintAvatar(nodeId, url, name) {
        const box = byId(nodeId);
        if (!box) return;
        box.textContent = initials(name);
        box.dataset.fallback = '1';
        if (!url) return;
        const img = document.createElement('img');
        img.alt = '';
        img.referrerPolicy = 'no-referrer';
        img.addEventListener('load', () => {
          box.dataset.fallback = '0';
          box.textContent = '';
          box.appendChild(img);
        });
        img.src = url;
      }

      function showProfile(linkId, url) {
        const link = byId(linkId);
        if (!link) return;
        if (url) {
          link.href = url;
          link.hidden = false;
        } else {
          link.hidden = true;
        }
      }

      // The number is written once, correctly, and the animation is decoration
      // layered on top. Animating the text itself would show a wrong value
      // whenever the frame loop is throttled, such as in a background tab.
      function setNumber(id, value, suffix) {
        const el = byId(id);
        if (!el) return;
        const target = Number(value) || 0;
        const text = target + (suffix || '');
        const previous = el.dataset.value;
        el.dataset.value = String(target);
        el.textContent = text;
        if (reduced || previous === undefined || previous === String(target)) return;
        el.classList.remove('tick');
        void el.offsetWidth;
        el.classList.add('tick');
      }

      function toneFor(done, count) {
        if (done) return 'ok';
        return count > 0 ? '' : 'idle';
      }

      function drawStrip(days) {
        const strip = byId('gh-strip');
        if (!strip) return;
        strip.textContent = '';
        if (!days || !days.length) {
          for (let i = 0; i < 30; i += 1) {
            const filler = document.createElement('div');
            filler.className = 'bar empty';
            filler.style.height = '100%';
            strip.appendChild(filler);
          }
          return;
        }
        const peak = days.reduce((best, day) => Math.max(best, day.count || 0), 0) || 1;
        days.forEach((day, index) => {
          const count = day.count || 0;
          const bar = document.createElement('div');
          const ratio = count / peak;
          let level = 0;
          if (count > 0) {
            if (ratio <= 0.25) level = 1;
            else if (ratio <= 0.5) level = 2;
            else if (ratio < 1) level = 3;
            else level = 4;
          }
          bar.className = count > 0 ? 'bar' : 'bar empty';
          bar.dataset.level = String(level);
          bar.style.height = count > 0 ? Math.max(12, Math.round(ratio * 100)) + '%' : '100%';
          const when = new Date(day.date + 'T00:00:00');
          const label = when.toLocaleDateString([], { month: 'short', day: 'numeric' });
          bar.title = label + ': ' + plural(count, 'event');
          if (index === days.length - 1) bar.style.outline = '1px solid rgba(255,255,255,0.55)';
          strip.appendChild(bar);
        });
      }

      function renderGithub(github) {
        const connected = Boolean(github.connected);
        byId('github-connected').hidden = !connected;
        byId('github-empty').hidden = connected;
        byId('github-link').hidden = connected;
        if (!connected) {
          showProfile('github-profile', '');
          setText('github-reason', github.reason || 'Not connected.');
          return;
        }
        showProfile('github-profile', github.url);
        setText('github-user', github.name || github.username || 'GitHub');
        paintAvatar('github-avatar', github.avatar, github.name || github.username);
        setNumber('gh-activity', github.activity_count);
        setNumber('gh-streak', github.current_streak, github.current_streak === 1 ? ' day' : ' days');
        setNumber('gh-repos', github.public_repos);
        setText('gh-today', github.today_commit_count > 0
          ? plural(github.today_commit_count, 'event') + ' today'
          : 'quiet today');
        drawStrip(github.days);
        setText('gh-top-repo', github.top_repo || '—');
      }

      function renderLeetcode(leetcode) {
        const connected = Boolean(leetcode.connected);
        byId('leetcode-connected').hidden = !connected;
        byId('leetcode-empty').hidden = connected;
        byId('leetcode-link').hidden = connected;
        if (!connected) {
          showProfile('leetcode-profile', '');
          setText('leetcode-reason', leetcode.reason || 'Not connected.');
          return;
        }
        showProfile('leetcode-profile', leetcode.username
          ? 'https://leetcode.com/u/' + encodeURIComponent(leetcode.username) + '/'
          : '');
        setText('leetcode-user', leetcode.name || leetcode.username || 'LeetCode');
        paintAvatar('leetcode-avatar', leetcode.avatar, leetcode.name || leetcode.username);
        setNumber('lc-today', leetcode.today_solved_count);
        setNumber('lc-streak', leetcode.current_streak, leetcode.current_streak === 1 ? ' day' : ' days');
        setText('lc-acceptance', Number(leetcode.acceptance_rate || 0).toFixed(1) + '%');

        const easy = Number(leetcode.easy) || 0;
        const medium = Number(leetcode.medium) || 0;
        const hard = Number(leetcode.hard) || 0;
        const total = easy + medium + hard;
        setText('lc-easy', easy);
        setText('lc-medium', medium);
        setText('lc-hard', hard);
        setText('lc-total', plural(total, 'problem') + ' solved');
        const pct = (value) => (total > 0 ? (value / total) * 100 : 0) + '%';
        byId('lc-e').style.width = pct(easy);
        byId('lc-m').style.width = pct(medium);
        byId('lc-h').style.width = pct(hard);
        setText('lc-ranking', leetcode.ranking ? '#' + Number(leetcode.ranking).toLocaleString() : 'Unranked');
      }

      function renderPulse(github, leetcode) {
        const commits = Number(github.today_commit_count) || 0;
        const solves = Number(leetcode.today_solved_count) || 0;
        const streaks = [github.current_streak, leetcode.current_streak].filter((n) => Number(n) > 0);

        setNumber('pulse-commits', commits);
        setNumber('pulse-solves', solves);
        const best = streaks.length ? Math.max.apply(null, streaks) : 0;
        setNumber('pulse-streak', best, best === 1 ? ' day' : (best > 0 ? ' days' : ''));

        setText('pulse-commits-note', github.connected
          ? (commits > 0 ? 'Shipped today' : 'Nothing pushed yet')
          : 'GitHub not connected');
        setText('pulse-solves-note', leetcode.connected
          ? (solves > 0 ? 'Keep the run going' : 'No solves yet today')
          : 'LeetCode not connected');
        setText('pulse-streak-note', streaks.length
          ? 'Longest active run'
          : 'No active streak');
      }

      function renderHeadline(github, leetcode) {
        const who = github.name || leetcode.name || '';
        setText('greeting', 'Daily driver');
        setText('headline', who ? who + "'s dashboard" : 'Daily Driver');
      }

      function render(data) {
        lastPayload = data;
        loadedAt = Date.now();

        const github = data.github || {};
        const leetcode = data.leetcode || {};
        const daily = data.daily_summary || {};

        renderHeadline(github, leetcode);
        renderPulse(github, leetcode);
        renderGithub(github);
        renderLeetcode(leetcode);
        setText('today-status', daily.summary || daily.status || 'Here is where your day stands.');

        if (data.time) {
          const stamp = new Date(data.time);
          if (!Number.isNaN(stamp.getTime())) {
            setText('greeting', (data.greeting || 'Hello') + ', ' +
              stamp.toLocaleDateString([], { weekday: 'long' }));
          }
        }
        markHealthy();
      }

      function markHealthy() {
        const dot = byId('health');
        if (dot) dot.className = 'dot';
        tickUpdated();
      }

      function markStale(reason) {
        const dot = byId('health');
        if (dot) dot.className = 'dot down';
        setText('updated', reason);
      }

      function tickUpdated() {
        if (!loadedAt) return;
        const seconds = Math.round((Date.now() - loadedAt) / 1000);
        const label = seconds < 5 ? 'just now'
          : seconds < 60 ? seconds + 's ago'
          : Math.round(seconds / 60) + 'm ago';
        setText('updated', 'Updated ' + label);
      }

      function runClock() {
        const now = new Date();
        setText('clock-time', now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        setText('clock-secs', now.toLocaleTimeString([], { second: '2-digit' }));
        setText('clock-date', now.toLocaleDateString([], {
          weekday: 'long', month: 'long', day: 'numeric'
        }));
      }

      function load() {
        return fetch('/api/dashboard', { headers: { Accept: 'application/json' } })
          .then((response) => {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
          })
          .then(render)
          .catch((error) => {
            if (lastPayload) {
              const dot = byId('health');
              if (dot) dot.className = 'dot stale';
              setText('updated', 'Showing last known data');
            } else {
              markStale('Could not reach the server');
            }
            console.error(error);
          });
      }

      runClock();
      setInterval(runClock, 1000);
      setInterval(tickUpdated, 1000);
      load();
      setInterval(load, REFRESH_MS);
    </script>
  </body>
</html>
"""


AUTH_ERROR_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{{ heading }}</title>
    <style>
      :root { --panel-border: rgba(148, 163, 184, 0.18); --text: #e5eefb; --muted: #9aa8bd; --amber: #fbbf24; }
      * { box-sizing: border-box; }
      body { margin: 0; min-height: 100%; padding: 48px 18px; display: flex; justify-content: center; background: radial-gradient(circle at top, #111a2e 0%, #0a1020 35%, #050b14 100%); color: var(--text); font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
      .card { width: min(620px, 100%); background: rgba(15, 23, 42, 0.82); border: 1px solid var(--panel-border); border-radius: 24px; padding: 28px; box-shadow: 0 18px 40px rgba(15, 23, 42, 0.45); }
      h1 { margin: 0 0 6px; font-size: 1.6rem; letter-spacing: -0.04em; }
      p { line-height: 1.55; }
      .muted { color: var(--muted); }
      .banner { background: rgba(251, 191, 36, 0.1); border: 1px solid rgba(251, 191, 36, 0.34); border-radius: 14px; padding: 12px 14px; color: #ffe7a8; }
      .detail { background: rgba(15, 23, 42, 0.9); border: 1px solid var(--panel-border); border-radius: 12px; padding: 12px 14px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.84rem; color: var(--muted); overflow-wrap: anywhere; }
      h3 { margin: 24px 0 0; font-size: 0.78rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }
      ol { padding-left: 20px; color: var(--muted); }
      li { margin-top: 10px; line-height: 1.5; }
      code { background: #0b1020; border-radius: 6px; padding: 2px 6px; }
      .cta { display: inline-flex; margin-top: 22px; padding: 12px 20px; background: rgba(56,189,248,0.14); border: 1px solid rgba(125,211,252,0.34); border-radius: 12px; color: var(--text); text-decoration: none; font-weight: 600; }
    </style>
  </head>
  <body>
    <main class="card">
      <h1>{{ heading }}</h1>
      <p class="muted">{{ message }}</p>
      {% if detail %}<p class="detail">{{ detail }}</p>{% endif %}
      {% if hint %}<p class="banner">{{ hint }}</p>{% endif %}
      {% if steps %}
      <h3>What to check</h3>
      <ol>{% for step in steps %}<li>{{ step }}</li>{% endfor %}</ol>
      {% endif %}
      <a class="cta" href="/">Back to the dashboard</a>
    </main>
  </body>
</html>
"""


def render_auth_error(heading, message, detail=None, hint=None, steps=None, status=400):
    return (
        render_template_string(
            AUTH_ERROR_TEMPLATE,
            heading=heading,
            message=message,
            detail=detail,
            hint=hint,
            steps=steps or [],
        ),
        status,
    )


def github_state_hint():
    """
    Explain the most common reason the state cookie is missing on the callback.

    The state lives in a session cookie, so it only survives if the callback
    returns to the same host the login started on. GitHub sends the browser to
    the exact URL registered on the OAuth app, so a dashboard opened on
    127.0.0.1 while the app is registered for localhost loses the cookie.
    """
    configured = os.environ.get("GITHUB_REDIRECT_URI")
    if not configured or not request.host:
        return ""
    registered = urlparse(configured)
    if not registered.netloc or registered.netloc == request.host:
        return ""
    return (
        "This callback arrived without its session cookie, which happens when the "
        "dashboard is opened on a different host than the one registered on the "
        "GitHub OAuth app. You are on %s, but GitHub is configured to return to "
        "%s. Open the dashboard at %s and try again."
        % (request.host, registered.netloc, registered.scheme + "://" + registered.netloc)
    )


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
    return _integration_for(
        "github",
        GitHubIntegration,
        token,
        settings={"username": username} if username else None,
    )


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
    return _integration_for("leetcode", LeetCodeIntegration, token, credentials)


def _integration_for(provider, factory, token, credentials=None, settings=None):
    """
    Build and cache one integration instance per credential.

    The classes only cache their API payload per instance, so a fresh instance
    per request would refetch everything on every page load. A rejected token is
    evicted instead of cached, so a reconnected account is picked up immediately.

    ``settings`` (such as a username) is kept apart from ``credentials`` on
    purpose. A credentials mapping without a token reads as an OAuth code
    exchange to GitHubIntegration, so the token must never be left out of it.
    """
    key = (factory, hashlib.sha256(token.encode("utf-8")).hexdigest())
    integration = _INTEGRATIONS.get(key)
    if integration is not None and integration.is_authenticated:
        _LAST_ERROR.pop(provider, None)
        return integration

    integration = factory(settings=settings)
    try:
        integration.authenticate(credentials if credentials is not None else token)
    except INTEGRATION_ERRORS as exc:
        _INTEGRATIONS.pop(key, None)
        log_provider_failure(provider, exc, "authenticate")
        _LAST_ERROR[provider] = describe_error(exc)
        return None

    _LAST_ERROR.pop(provider, None)
    _INTEGRATIONS[key] = integration
    prune_integrations()
    return integration


def provider_status():
    return {
        "github_connected": github_integration() is not None,
        "leetcode_connected": leetcode_integration() is not None,
    }


def github_disconnected(reason=None):
    return {
        "connected": False,
        "username": "Not connected",
        "name": None,
        "avatar": None,
        "url": None,
        "activity_count": 0,
        "commit_today": False,
        "today_commit_count": 0,
        "current_streak": 0,
        "longest_streak": 0,
        "days": [],
        "top_repo": "N/A",
        "public_repos": 0,
        "reason": reason,
    }


def leetcode_disconnected(username=None, reason=None):
    return {
        "connected": False,
        "username": username or "Not connected",
        "name": None,
        "avatar": None,
        "today_solved_count": 0,
        "solved_today": False,
        "current_streak": 0,
        "acceptance_rate": 0,
        "total_solved": 0,
        "easy": 0,
        "medium": 0,
        "hard": 0,
        "ranking": None,
        "reason": reason,
    }


def no_credential_reason(provider):
    if auth_disabled(provider):
        return "Disconnected in this browser. Use Connect %s to reconnect." % provider.capitalize()

    last_error = _LAST_ERROR.get(provider)
    if last_error:
        return "Connected but the token was rejected: %s" % last_error

    if provider == "github":
        if os.environ.get("GITHUB_TOKEN"):
            return "The GITHUB_TOKEN in .env was rejected"
        return "No GitHub token. Use Connect GitHub, or set GITHUB_TOKEN in .env"
    if os.environ.get("LEETCODE_SESSION"):
        return "The LEETCODE_SESSION cookie in .env was rejected or has expired"
    return "No LeetCode session. Use Connect LeetCode, or set LEETCODE_SESSION in .env"


def no_github_credential_reason():
    return no_credential_reason("github")


def describe_error(exc):
    """A short, human-readable reason a provider could not be used."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status == 401:
        return "GitHub rejected the token as invalid or expired"
    if status == 403:
        return (
            "GitHub refused the request. This is usually the API rate limit, or "
            "SAML SSO enforcement on the account or organization"
        )
    if status == 404:
        return "GitHub returned 404. Check the username"
    if status == 429:
        return "GitHub rate limit hit; wait a few minutes and reload"
    if isinstance(exc, requests.RequestException):
        return "Could not reach the provider: %s" % exc
    return str(exc)


def log_provider_failure(provider, exc, where=""):
    """
    Record a provider failure in the server log.

    Silently degrading to "not connected" is what made an authentication problem
    indistinguishable from a quiet account, so every failure is reported here.
    """
    status = getattr(getattr(exc, "response", None), "status_code", None)
    app.logger.warning(
        "%s%s failed: %s: %s",
        provider,
        " %s" % where if where else "",
        describe_error(exc),
        exc,
    )
    return status


def last_day_count(series):
    """Count for the most recent day of a ``[{"count": ...}, ...]`` series."""
    days = (series or {}).get("days") or []
    return days[-1].get("count", 0) if days else 0


def fetch_github_data():
    integration = github_integration()
    if integration is None:
        return github_disconnected(reason=no_github_credential_reason())

    try:
        payload = integration.core_functionality()
    except INTEGRATION_ERRORS as exc:
        log_provider_failure("github", exc, "dashboard")
        return github_disconnected(reason=describe_error(exc))

    user = payload.get("user") or {}
    contributions = payload.get("contributions") or {}
    repositories = payload.get("repositories") or []
    today_count = last_day_count(contributions)

    return {
        "connected": True,
        "username": user.get("login"),
        "name": user.get("name"),
        "avatar": user.get("avatar_url"),
        "url": user.get("html_url"),
        "activity_count": contributions.get("total", 0),
        "commit_today": today_count > 0,
        "today_commit_count": today_count,
        "current_streak": contributions.get("current_streak", 0),
        "longest_streak": contributions.get("longest_streak", 0),
        "days": contributions.get("days", []),
        "top_repo": repositories[0].get("name") if repositories else "No public repos yet",
        "public_repos": user.get("public_repos", 0),
    }


def fetch_leetcode_data():
    fallback_username = stored_credentials("leetcode").get("username") or os.environ.get("LEETCODE_USERNAME")
    integration = leetcode_integration()
    if integration is None:
        return leetcode_disconnected(fallback_username, reason=no_credential_reason("leetcode"))

    try:
        payload = integration.core_functionality()
    except INTEGRATION_ERRORS as exc:
        log_provider_failure("leetcode", exc, "dashboard")
        return leetcode_disconnected(fallback_username, reason=describe_error(exc))

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

    solved = user.get("solved") or {}
    return {
        "connected": True,
        "username": user.get("username") or fallback_username,
        "name": user.get("name"),
        "avatar": user.get("avatar"),
        "today_solved_count": today_count,
        "solved_today": today_count > 0,
        "current_streak": streak.get("current_streak", 0) if streak.get("available") else 0,
        "acceptance_rate": user.get("acceptance_rate", 0),
        "total_solved": solved.get("all", 0),
        "easy": solved.get("easy", 0),
        "medium": solved.get("medium", 0),
        "hard": solved.get("hard", 0),
        "ranking": user.get("ranking"),
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


GITHUB_REDIRECT_STEPS = [
    "The callback URL on your GitHub OAuth app must match GITHUB_REDIRECT_URI "
    "exactly, including the port. GitHub only allows one callback URL per app, "
    "and anything else fails with <code>redirect_uri_mismatch</code>.",
    "Open the dashboard on the same host that is registered. A login started on "
    "<code>127.0.0.1:5000</code> and returned to <code>localhost:5000</code> loses "
    "the session cookie that carries the login state.",
    "If the app belongs to an organisation, it may be restricted or pending "
    "approval, which blocks the consent step.",
    "Check the <code>GITHUB_CLIENT_ID</code> and <code>GITHUB_CLIENT_SECRET</code> in "
    ".env belong to the same OAuth app.",
]


@app.route("/oauth/github/callback")
def github_callback():
    if request.args.get("error"):
        return render_auth_error(
            "GitHub declined the request",
            "The authorization was not completed.",
            detail="%s: %s" % (
                request.args.get("error"),
                request.args.get("error_description") or "no description",
            ),
            steps=GITHUB_REDIRECT_STEPS,
        )

    if not consume_oauth_state(request.args.get("state")):
        return render_auth_error(
            "Login could not be verified",
            "The one-time login state was missing or had already been used, so the "
            "callback was not accepted. This is a security check against forged "
            "callbacks, and it is not something to work around.",
            hint=github_state_hint(),
            steps=GITHUB_REDIRECT_STEPS,
        )

    code = request.args.get("code")
    if not code:
        return render_auth_error(
            "GitHub sent no authorization code",
            "The callback arrived without the code needed to exchange it for a token.",
            steps=GITHUB_REDIRECT_STEPS,
        )

    integration = GitHubIntegration()
    try:
        user = integration.authenticate({
            "client_id": os.environ.get("GITHUB_CLIENT_ID"),
            "client_secret": os.environ.get("GITHUB_CLIENT_SECRET"),
            "code": code,
            "redirect_uri": github_redirect_uri(),
        })
    except INTEGRATION_ERRORS as exc:
        return render_auth_error(
            "GitHub rejected the login",
            "The authorization code could not be exchanged for a token.",
            detail=str(exc),
            steps=GITHUB_REDIRECT_STEPS,
        )

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
