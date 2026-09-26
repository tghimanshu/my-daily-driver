import os
from datetime import datetime, timedelta, timezone

import requests

from integration import Integration


class GitHubIntegration(Integration):
    """
    Handles all communication with the GitHub REST API.

    OAuth happens in the widget layer, so this integration expects to receive
    an already issued access token and keeps it for the lifetime of the instance.
    """

    API_BASE_URL = "https://api.github.com"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_AGENT = "my-daily-driver"
    DEFAULT_TIMEOUT = 15
    CACHE_TTL_SECONDS = 300

    DEFAULT_SETTINGS = {
        "username": None,
        "include_private": False,
        "max_repos": 10,
        "activity_days": 30,
        "theme": "light",
    }

    def __init__(self, name="github", settings=None):
        super().__init__(name)
        self._access_token = None
        self._authenticated_user = None
        self._rate_limit = None
        self._cache = None
        self._cache_timestamp = None
        self._settings = dict(self.DEFAULT_SETTINGS)
        if settings:
            self.settings = settings

    def authenticate(self, credentials):
        """
        Authenticate the integration.

        ``credentials`` may be an access token, a mapping containing an
        ``access_token``/``token`` key, or a mapping containing ``client_id``,
        ``client_secret`` and ``code`` to exchange an OAuth code for a token.
        """
        if not credentials:
            raise ValueError("No credentials provided for GitHub.")

        if isinstance(credentials, str):
            token = credentials
        else:
            token = credentials.get("access_token") or credentials.get("token")
            if not token:
                token = self._exchange_oauth_code(credentials)

        if not token:
            raise ValueError("Could not resolve a GitHub access token.")

        self._access_token = token
        try:
            payload = self._request("GET", "/user")
        except Exception:
            self._access_token = None
            raise

        self._authenticated_user = payload.get("login")
        self._is_authenticated = True
        if not self._settings.get("username") and self._authenticated_user:
            self._settings["username"] = self._authenticated_user
        self._cache = None
        self._cache_timestamp = None
        return self.get_user_info()

    def get_access_token(self):
        if not self._access_token:
            raise ValueError("GitHub integration is not authenticated.")
        return self._access_token

    def logout(self):
        self._access_token = None
        self._authenticated_user = None
        self._is_authenticated = False
        self._rate_limit = None
        self._cache = None
        self._cache_timestamp = None

    def get_user_info(self, user=None):
        username = user or self._settings.get("username") or self._authenticated_user
        if not username:
            raise ValueError("No GitHub username configured for this integration.")

        path = "/user" if not user and self._is_authenticated else f"/users/{username}"
        payload = self._request("GET", path)
        return {
            "login": payload.get("login"),
            "name": payload.get("name"),
            "bio": payload.get("bio"),
            "avatar_url": payload.get("avatar_url"),
            "html_url": payload.get("html_url"),
            "company": payload.get("company"),
            "location": payload.get("location"),
            "public_repos": payload.get("public_repos", 0),
            "public_gists": payload.get("public_gists", 0),
            "followers": payload.get("followers", 0),
            "following": payload.get("following", 0),
            "created_at": payload.get("created_at"),
        }

    def get_repositories(self, username=None, limit=None):
        username = (
            username or self._settings.get("username") or self._authenticated_user
        )
        if not username:
            raise ValueError("No GitHub username configured for this integration.")

        limit = limit or self._settings.get("max_repos", 10)
        params = {
            "sort": "updated",
            "per_page": min(limit, 100),
            "type": "owner",
        }
        if not self._settings.get("include_private", False):
            params["visibility"] = "public"

        repos = self._request("GET", f"/users/{username}/repos", params=params)
        return [
            {
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "description": repo.get("description"),
                "html_url": repo.get("html_url"),
                "language": repo.get("language"),
                "stargazers_count": repo.get("stargazers_count", 0),
                "forks_count": repo.get("forks_count", 0),
                "open_issues_count": repo.get("open_issues_count", 0),
                "pushed_at": repo.get("pushed_at"),
            }
            for repo in repos[:limit]
        ]

    def get_activity_contributions(self, days=None, username=None):
        """
        Approximate daily contribution counts from the public events feed, since
        the REST API does not expose a contribution graph.
        """
        days = days or self._settings.get("activity_days", 30)
        username = (
            username or self._settings.get("username") or self._authenticated_user
        )
        if not username:
            raise ValueError("No GitHub username configured for this integration.")

        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=days - 1)
        counts = {start + timedelta(days=offset): 0 for offset in range(days)}

        page = 1
        while len(counts) and page <= 3:
            events = self._request(
                "GET",
                f"/users/{username}/events/public",
                params={"per_page": 100, "page": page},
            )
            if not events:
                break
            for event in events:
                created = event.get("created_at")
                if not created:
                    continue
                event_day = datetime.fromisoformat(
                    created.replace("Z", "+00:00")
                ).date()
                if event_day in counts:
                    counts[event_day] += 1
            page += 1

        series = [
            {"date": day.isoformat(), "count": count} for day, count in counts.items()
        ]
        total = sum(item["count"] for item in series)
        return {
            "days": series,
            "total": total,
            "current_streak": self._current_streak(series),
            "longest_streak": self._longest_streak(series),
        }

    def core_functionality(self):
        """
        Build the payload consumed by the GitHub widget.
        """
        if self._is_authenticated:
            cached = self._get_cached()
            if cached is not None:
                return cached

        payload = {
            "integration": self.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "user": self.get_user_info(),
            "repositories": self.get_repositories(),
            "contributions": self.get_activity_contributions(),
            "rate_limit": self._rate_limit,
        }

        if self._is_authenticated:
            self._set_cached(payload)
        return payload

    @property
    def settings(self):
        return self._settings

    @settings.setter
    def settings(self, value):
        """
        Merge the provided settings over the GitHub defaults so a widget can
        override a single key without dropping the rest.
        """
        if not self._validate_settings(value):
            raise ValueError("Invalid settings provided.")
        merged = dict(self.DEFAULT_SETTINGS)
        merged.update(value)
        self._settings = merged

    def _validate_settings(self, settings):
        if not isinstance(settings, dict):
            return False

        username = settings.get("username", self._settings.get("username"))
        if username is not None and not isinstance(username, str):
            return False

        for key in ("include_private",):
            if key in settings and not isinstance(settings[key], bool):
                return False

        for key in ("max_repos", "activity_days"):
            if key in settings:
                value = settings[key]
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    return False

        if "theme" in settings and not isinstance(settings["theme"], str):
            return False

        return True

    def _exchange_oauth_code(self, credentials):
        client_id = credentials.get("client_id") or os.getenv("GITHUB_CLIENT_ID")
        client_secret = credentials.get("client_secret") or os.getenv(
            "GITHUB_CLIENT_SECRET"
        )
        code = credentials.get("code")
        if not (client_id and client_secret and code):
            raise ValueError("Incomplete GitHub OAuth credentials.")

        response = requests.post(
            self.TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
            timeout=self.DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise ValueError(f"GitHub OAuth error: {payload['error']}")
        return payload.get("access_token")

    def _request(self, method, path, params=None):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": self.USER_AGENT,
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        url = path if path.startswith("http") else f"{self.API_BASE_URL}{path}"
        response = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            timeout=self.DEFAULT_TIMEOUT,
        )
        self._update_rate_limit(response)
        if response.status_code == 401:
            self._is_authenticated = False
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    def _update_rate_limit(self, response):
        limit = response.headers.get("X-RateLimit-Limit")
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        if limit is None or remaining is None:
            return
        self._rate_limit = {
            "limit": int(limit),
            "remaining": int(remaining),
            "reset": int(reset) if reset else None,
        }

    def _get_cached(self):
        if self._cache is None or self._cache_timestamp is None:
            return None
        age = (datetime.now(timezone.utc) - self._cache_timestamp).total_seconds()
        if age > self.CACHE_TTL_SECONDS:
            return None
        return {**self._cache, "cached": True}

    def _set_cached(self, payload):
        self._cache = payload
        self._cache_timestamp = datetime.now(timezone.utc)

    def _current_streak(self, series):
        streak = 0
        for item in reversed(series):
            if item["count"] == 0:
                break
            streak += 1
        return streak

    def _longest_streak(self, series):
        longest = 0
        current = 0
        for item in series:
            current = current + 1 if item["count"] > 0 else 0
            longest = max(longest, current)
        return longest
