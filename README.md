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
`http://localhost:5000/oauth/github/callback` as the callback URL, set
`GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`, then press *Connect GitHub*. The
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
