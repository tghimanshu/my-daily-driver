# Daily Driver

This is a project to create a daily driver dashboard.
It uses integrations to work with various services that tailor to your needs.
It allows you the customizability to make it your own and make it fit your needs.
From tracking your fitness goals, leetcode progress, github contributions, to
calendar events, tasks, and more, this dashboard is designed to be your sole
place to bring all your information together and make it easily accessible.

## Features

- **Customizable Dashboard**: Tailor the dashboard to your preferences with
  widgets and integrations that suit your needs.
- **Integration with Services**: Connect with various services
- **Themes**: Choose from a variety of themes to personalize the look and feel
  of your dashboard.
- **Responsive Design**: Access your dashboard from any device, whether as
  a website or a PWA (Progressive Web App).
- **Real-time Updates**: Get real-time updates from your connected services.
- **Task Management**: Keep track of your tasks and to-dos in one place.
- **Focus Timer**: A pomodoro timer with your own round and break lengths.
- **Keyboard Friendly**: To all our keyboard warriors, navigate and interact with your dashboard using keyboard shortcuts for a seamless experience.

## Current Integrations
- **GitHub**: Track your contributions, streaks and repositories.
- **LeetCode**: Monitor your coding progress and recent activity.
- **Self-hosted sites**: Watch the uptime of anything you host yourself.

## Monitoring your own sites

List what you host in `.env` as comma separated `name=url` pairs. The name is
what the widget shows, and a bare url works too if the host is a good enough
label:

```sh
SELF_HOSTED_SITES=blog=https://blog.example.com,immich=http://10.0.0.4:2283,vault=https://vault.example.com|healthy
```

Any 2xx or 3xx counts as up. Append `|keyword` to also require a string in the
response body, which catches a service that answers `200` while actually
broken, such as a reverse proxy serving its own error page. Checks run
concurrently with a timeout, so an unreachable host never holds up the healthy
ones, and results are cached for a minute. The widget has its own *Check now*
button and refreshes independently of the rest of the dashboard, because a site
that hangs should not delay anything else.

Failures are reported with the reason rather than a bare red dot:
`connection refused`, `host not found`, `timed out after 8.0s`, `HTTP 502`, or
`responded without 'healthy'`. TLS certificates are verified, so a self-signed
certificate is reported as a TLS problem instead of being silently accepted.

## Focus timer

The pomodoro widget counts focus rounds and the breaks between them, and puts the
day's total up in the pulse row next to your commits and solves. The lengths are
yours to set, in the widget or in `.env`:

```sh
POMODORO_WORK_MINUTES=25
POMODORO_SHORT_BREAK_MINUTES=5
POMODORO_LONG_BREAK_MINUTES=15
POMODORO_ROUNDS=4        # focus rounds before a long break
POMODORO_GOAL=8          # focus rounds a day is aiming for
```

`.env` sets the default for a browser that has not touched the settings yet.
Saving in the widget overrides it for that browser only, because how long your
rounds are is a personal preference rather than a deployment setting. A blank or
mistyped value falls back to the built-in default instead of stopping the timer,
and anything past the sensible range is clamped, so a stray zero cannot leave you
with a focus round of no length at all.

The timer runs on the server rather than in the page, which is what lets it
survive a reload, a closed tab or a second tab: the remaining time is recomputed
from the clock on every read, so a laptop that slept through a round does not lose
it. The browser only ticks the display and rings a short chime when a round ends,
then asks the server what comes next. That request is also where an unattended
round is credited, and only one round advances per read, so coming back after the
afternoon does not hand you a queue of breaks.

A round in progress is never rescaled under you: changing a length stops the
current round so the next one starts at the new length. *Skip* ends a round early
and counts it, *Reset* puts the current one back to the start, and *Clear today*
zeroes the day's numbers without touching the cycle. Focus time is credited when
a round ends, not while it runs, so the total is made of rounds you finished.

The counters are in memory, like the credentials, so restarting the server starts
a new day. The week strip under the ring is the same: it fills in as days pass
rather than being read from anywhere.

## Running it

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill it in
python app.py          # http://127.0.0.1:5000
```

The backend serves both the API and the frontend from the same port, and reads
`.env` on startup. Real environment variables override the file, so
`GITHUB_TOKEN=... python app.py` works without editing it.

By default the server binds to `127.0.0.1` with the debugger off, because the
Werkzeug debugger is a remote shell for anyone who can reach it. `HOST` and
`FLASK_DEBUG` in `.env` change that, and setting `FLASK_DEBUG=1` alongside a
non-loopback `HOST` prints a warning.

`python -m unittest test_dashboard` runs the test suite.

## Running it with Docker

Two compose files, for two jobs. `docker-compose.home-server.yml` is the one you
actually want; `docker-compose.yml` is for running the dashboard on its own,
outside the stack.

### As part of the home server stack

The home server compose file pulls in
`docker-compose.home-server.yml` with an `include`, so the dashboard is a
service of that project rather than a stack of its own. One command runs the
whole thing:

```sh
cd ../home-server
docker compose up -d --build daily-driver   # https://dashboard.home
docker compose logs -f daily-driver
docker compose up -d --build daily-driver   # after changing the app
```

Compose resolves relative paths inside an included file against that file's own
directory, so the build context and the `.env` it reads are both this folder.
Nothing needs copying between the two repos, and the two compose files never
have to agree on anything.

What the include buys you, beyond convenience:

- **One network, no published port.** The service joins the home server
  project's default network, which is the one Caddy is on, so Caddy proxies to
  `daily-driver:5000` directly. Nothing binds a port on the LAN, so the
  dashboard is only reachable over Caddy's certificate, like every other app in
  the stack. For the same reason `SELF_HOSTED_SITES` can address the other
  containers by name (`http://it-tools`) and skip a hop through the host.
- **One `docker compose ps`.** Stopping the stack stops the dashboard with it,
  rather than leaving an orphan pointing at a network that is gone.

The GitHub OAuth app needs its callback URL registered as
`https://dashboard.home/oauth/github/callback`, which the compose file sets in
`GITHUB_REDIRECT_URI`. It is set explicitly rather than left to Flask's
`url_for` because nothing in the app trusts Caddy's `X-Forwarded-Proto`, so a
generated URL would come out as `http`.

Do not run `docker compose -f docker-compose.home-server.yml up` on its own.
There is no Caddy to serve it and no network to sit on; it is a fragment.

### On its own

```sh
docker compose up -d --build     # http://localhost:5000
docker compose logs -f
docker compose down
docker compose run --rm tests    # test suite against the working tree
```

Same `.env`, same port, same URLs, so nothing about the browser setup changes.
Two things are worth knowing about this one.

**Start the other stack first.** This file attaches to the home server stack's
network, `home-server_default`, so `SELF_HOSTED_SITES` can address those
containers by name. Compose needs that network to exist, so bring up the other
stack first, or create it once by hand with
`docker network create home-server_default`. The other stack adopts an existing
network of that name without complaint, so this does not lock it out. For
anything not on that network, `host.docker.internal:<port>` reaches a published
port.

**It is on loopback only.** The port is published as `127.0.0.1:5000`, so the
dashboard is not reachable from your LAN, even though the container listens on
`0.0.0.0` — that binding is required, as Docker's published port connects to
the container's own interface and never its loopback.

### Either way

**Do not raise the worker count.** Credentials live in an in-process store, so
a second gunicorn worker would not see the session that just finished an OAuth
login and the dashboard would report "not connected" straight after a
successful sign-in. The compose files run one worker with threads; that is a
correctness requirement, not a default. The same applies to `docker compose up
--scale daily-driver=2`, which will look like it works and then fail login.

**It is locked down, because it holds tokens.** Non-root, `cap_drop: ALL`,
`no-new-privileges`, and a read-only root filesystem, since there is no state
to write.

A container restart still drops browser logins, exactly like restarting the
server locally, because the credential store is in memory.

### About your credentials

`SECRET_KEY` must be at least 32 characters. A shorter or placeholder value is
replaced with a random key for that run, which signs you out on restart:

```sh
python -c "import secrets; print(secrets.token_hex(32))"
```

Access tokens are never sent to the browser. The session cookie holds nothing
but a random id that points at an in-process store, so a token is not readable
by anything that can see the cookie. The tradeoff is that the store is not
persisted: restarting the server disconnects every browser, and `.env`
credentials have to be re-entered or reconnected once. Stale sessions are
evicted after 30 days.

## Connecting an account

Both providers can also be configured in `.env` alone, which is handy for a
headless setup. Otherwise use the buttons in the dashboard.

**GitHub** uses a real OAuth app: register one under
[GitHub developer settings](https://github.com/settings/developers) with
`http://localhost:5000/oauth/github/callback` as the callback URL when running
on its own, or `https://dashboard.home/oauth/github/callback` when it runs in
the home server stack, which is what the compose file sets for you. Then set
`GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` and press *Connect GitHub*. The
dashboard only requests the `read:user` scope, which is enough for the profile,
public repositories, and the public activity feed it reads. Set `GITHUB_TOKEN`
to a personal access token instead if you would rather skip the browser; it
also raises the rate limit from 60 to 5000 requests an hour.

**LeetCode** has no OAuth app that a third-party dashboard can register, so
there is nothing to create. Its API is the private GraphQL endpoint the website
itself uses, and that endpoint only checks the `LEETCODE_SESSION` cookie set at
login. Sign in at leetcode.com, copy that cookie value from DevTools, and paste
it into *Connect LeetCode*. The cookie expires every few weeks, so expect to
reconnect now and then. `LEETCODE_SESSION` in `.env` does the same thing
without a browser.

*Disconnect accounts* clears both. Credentials in `.env` apply to every session,
so a disconnect is remembered per browser rather than being undone on the next
page load.
