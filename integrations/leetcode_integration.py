import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests

from integration import Integration


class LeetCodeIntegration(Integration):
    """
    Handles all communication with LeetCode.

    LeetCode publishes no supported API, so this integration talks to the
    private GraphQL endpoint the website itself uses. That endpoint is not
    versioned and can change without notice, so the queries live in class
    attributes and are kept as small as possible.

    OAuth login happens in the widget layer, which forwards the resulting
    access token. The token is a JWT that LeetCode also accepts as the
    LEETCODE_SESSION cookie, so it is sent both ways to stay compatible.
    """

    GRAPHQL_URL = "https://leetcode.com/graphql/"
    TOKEN_URL = "https://leetcode.com/oauth/access_token"
    AUTHORIZE_URL = "https://leetcode.com/oauth/authorize/"
    CONTRIB_URL = "https://leetcode.com/contrib/api/hot_active_days/"
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    DEFAULT_TIMEOUT = 20
    CACHE_TTL_SECONDS = 300

    DEFAULT_SETTINGS = {
        "username": None,
        "include_contests": True,
        "recent_submissions_limit": 10,
        "track_streaks": True,
        "theme": "light",
    }

    USER_QUERY = """
    query($username: String!) {
      matchedUser(username: $username) {
        username
        profile {
          realName
          reputation
          ranking
          userAvatar
          school
          countryName
        }
        submitStats {
          acSubmissionNum { difficulty count submissions }
          totalSubmissionNum { difficulty count submissions }
        }
        userCalendar { activeYears }
      }
    }
    """

    CONTEST_QUERY = """
    query($username: String!) {
      userContestRanking(username: $username) {
        rating
        attendedContestsCount
        globalRanking
        topPercentage
      }
    }
    """

    RECENT_SOLUTIONS_QUERY = """
    query($username: String!, $limit: Int!) {
      recentAcSubmissionList(username: $username, limit: $limit) {
        id
        title
        titleSlug
      }
    }
    """

    AUTHENTICATED_USER_QUERY = """
    query {
      userStatus {
        isSignedIn
        username
      }
    }
    """

    def __init__(self, name="leetcode", settings=None):
        super().__init__(name)
        self._access_token = None
        self._authenticated_user = None
        self._cache = None
        self._cache_timestamp = None
        self._settings = dict(self.DEFAULT_SETTINGS)
        if settings:
            self.settings = settings

    @property
    def settings(self):
        return self._settings

    @settings.setter
    def settings(self, value):
        """
        Merge the provided settings over the LeetCode defaults so a widget can
        override a single key without dropping the rest.
        """
        if not self._validate_settings(value):
            raise ValueError("Invalid settings provided.")
        merged = dict(self.DEFAULT_SETTINGS)
        merged.update(value)
        self._settings = merged

    def authenticate(self, credentials):
        """
        Authenticate the integration.

        ``credentials`` may be a LeetCode session token or OAuth access token,
        a mapping containing a ``session_token``/``access_token``/``token`` key,
        or a mapping containing ``client_id``, ``client_secret`` and ``code`` to
        exchange an OAuth code for a token.
        """
        if not credentials:
            raise ValueError("No credentials provided for LeetCode.")

        if isinstance(credentials, str):
            token = credentials
        else:
            token = credentials.get("session_token") or credentials.get("access_token")
            token = token or credentials.get("token")
            if not token:
                token = self._exchange_oauth_code(credentials)

        if not token:
            raise ValueError("Could not resolve a LeetCode access token.")

        self._access_token = token
        try:
            self._authenticated_user = self._resolve_authenticated_user()
        except Exception:
            self._access_token = None
            raise

        self._is_authenticated = True
        if self._authenticated_user and not self._settings.get("username"):
            self._settings["username"] = self._authenticated_user
        self._cache = None
        self._cache_timestamp = None
        return self._authenticated_user

    def get_access_token(self):
        if not self._access_token:
            raise ValueError("LeetCode integration is not authenticated.")
        return self._access_token

    def logout(self):
        self._access_token = None
        self._authenticated_user = None
        self._is_authenticated = False
        self._cache = None
        self._cache_timestamp = None

    def get_user_info(self, user=None):
        username = user or self._settings.get("username") or self._authenticated_user
        if not username:
            raise ValueError("No LeetCode username configured for this integration.")

        try:
            data = self._graphql(self.USER_QUERY, username=username)
        except RuntimeError as exc:
            if "does not exist" in str(exc):
                raise ValueError(f"LeetCode user {username!r} was not found.") from exc
            raise

        matched = (data or {}).get("matchedUser")
        if not matched:
            raise ValueError(f"LeetCode user {username!r} was not found.")

        profile = matched.get("profile") or {}
        submit_stats = matched.get("submitStats") or {}
        solved = self._by_difficulty(submit_stats.get("acSubmissionNum"))
        attempted = self._by_difficulty(submit_stats.get("totalSubmissionNum"))

        return {
            "username": matched.get("username"),
            "name": profile.get("realName"),
            "avatar_url": profile.get("userAvatar"),
            "ranking": profile.get("ranking"),
            "reputation": profile.get("reputation"),
            "school": profile.get("school"),
            "country": profile.get("countryName"),
            "profile_url": f"https://leetcode.com/{matched.get('username')}/",
            "solved": {
                "all": solved.get("All", {}).get("count", 0),
                "easy": solved.get("Easy", {}).get("count", 0),
                "medium": solved.get("Medium", {}).get("count", 0),
                "hard": solved.get("Hard", {}).get("count", 0),
            },
            "submitted": {
                "all": attempted.get("All", {}).get("count", 0),
                "easy": attempted.get("Easy", {}).get("count", 0),
                "medium": attempted.get("Medium", {}).get("count", 0),
                "hard": attempted.get("Hard", {}).get("count", 0),
            },
            "acceptance_rate": self._acceptance_rate(solved, attempted),
            "problem_coverage": self._problem_coverage(solved, attempted),
            "active_years": (matched.get("userCalendar") or {}).get("activeYears") or [],
        }

    def get_contest_ranking(self, user=None):
        username = user or self._settings.get("username") or self._authenticated_user
        if not username:
            raise ValueError("No LeetCode username configured for this integration.")

        data = self._graphql(self.CONTEST_QUERY, username=username)
        ranking = (data or {}).get("userContestRanking")
        if not ranking:
            return None
        return {
            "rating": ranking.get("rating"),
            "attended_contests": ranking.get("attendedContestsCount", 0),
            "global_ranking": ranking.get("globalRanking"),
            "top_percentage": ranking.get("topPercentage"),
        }

    def get_recent_solutions(self, user=None, limit=None):
        username = user or self._settings.get("username") or self._authenticated_user
        limit = limit or self._settings.get("recent_submissions_limit", 10)
        if not username:
            raise ValueError("No LeetCode username configured for this integration.")

        data = self._graphql(self.RECENT_SOLUTIONS_QUERY, username=username, limit=limit)
        submissions = (data or {}).get("recentAcSubmissionList") or []
        return [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "title_slug": item.get("titleSlug"),
                "url": f"https://leetcode.com/problems/{item.get('titleSlug')}/",
            }
            for item in submissions
        ]

    def get_streak(self, user=None, days=365):
        """
        Daily solved counts and streaks.

        The counts come from the same ``contrib`` endpoint that serves the
        website heatmap, which is behind a bot check, so a failure is reported
        as unavailable rather than raised: the rest of the widget is still
        worth rendering without a heatmap.
        """
        username = user or self._settings.get("username") or self._authenticated_user
        if not username:
            raise ValueError("No LeetCode username configured for this integration.")

        to_date = datetime.now(timezone.utc).date()
        from_date = to_date - timedelta(days=days - 1)
        params = {
            "user_slug": username,
            "from": from_date.strftime("%Y%m%d"),
            "to": to_date.strftime("%Y%m%d"),
        }
        try:
            response = self._request("GET", self.CONTRIB_URL, params=params)
        except requests.RequestException:
            return {"available": False, "reason": "contrib_endpoint_unavailable"}

        counts = self._normalize_contrib_counts(response)
        series = [
            {"date": (from_date + timedelta(days=offset)).isoformat(), "count": counts.get(offset, 0)}
            for offset in range(days)
        ]
        total = sum(item["count"] for item in series)
        return {
            "available": True,
            "days": series,
            "total": total,
            "current_streak": self._current_streak(series),
            "longest_streak": self._longest_streak(series),
        }

    def core_functionality(self):
        """
        Build the payload consumed by the LeetCode widget.
        """
        if self._is_authenticated:
            cached = self._get_cached()
            if cached is not None:
                return cached

        payload = {
            "integration": self.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "user": self.get_user_info(),
        }

        if self._settings.get("include_contests", True):
            payload["contest"] = self.get_contest_ranking()

        if self._settings.get("recent_submissions_limit"):
            payload["recent_solutions"] = self.get_recent_solutions()

        if self._settings.get("track_streaks", True):
            payload["streak"] = self.get_streak()

        if self._is_authenticated:
            self._set_cached(payload)
        return payload

    def get_authorization_url(self, client_id=None, redirect_uri=None, state=None, scope="*"):
        """
        Build the OAuth URL the widget layer redirects the browser to.

        Kept here so the client id and redirect uri stay next to the token
        exchange instead of being duplicated in the widget.
        """
        client_id = client_id or os.getenv("LEETCODE_CLIENT_ID")
        redirect_uri = redirect_uri or os.getenv("LEETCODE_REDIRECT_URI")
        if not (client_id and redirect_uri):
            raise ValueError("Incomplete LeetCode OAuth configuration.")

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
        }
        if state:
            params["state"] = state

        return self.AUTHORIZE_URL + "?" + urlencode(params)

    def _validate_settings(self, settings):
        if not isinstance(settings, dict):
            return False

        username = settings.get("username", self._settings.get("username"))
        if username is not None and not isinstance(username, str):
            return False

        for key in ("include_contests", "track_streaks"):
            if key in settings and not isinstance(settings[key], bool):
                return False

        if "recent_submissions_limit" in settings:
            limit = settings["recent_submissions_limit"]
            if limit is not None and (
                not isinstance(limit, int) or isinstance(limit, bool) or limit < 0
            ):
                return False

        if "theme" in settings and not isinstance(settings["theme"], str):
            return False

        return True

    def _resolve_authenticated_user(self):
        """
        Resolve the username behind the current session token.
        """
        status = self._graphql(self.AUTHENTICATED_USER_QUERY).get("userStatus") or {}
        if not status.get("isSignedIn") or not status.get("username"):
            raise ValueError("The LeetCode session token was rejected or has expired.")
        return status.get("username")

    def _exchange_oauth_code(self, credentials):
        client_id = credentials.get("client_id") or os.getenv("LEETCODE_CLIENT_ID")
        client_secret = credentials.get("client_secret") or os.getenv("LEETCODE_CLIENT_SECRET")
        code = credentials.get("code")
        if not (client_id and client_secret and code):
            raise ValueError("Incomplete LeetCode OAuth credentials.")

        response = requests.post(
            self.TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": credentials.get("redirect_uri")
                or os.getenv("LEETCODE_REDIRECT_URI"),
            },
            headers={"User-Agent": self.USER_AGENT, "Referer": "https://leetcode.com/"},
            timeout=self.DEFAULT_TIMEOUT,
        )
        if response.status_code in (301, 302, 303, 307, 308) or not response.headers.get(
            "Content-Type", ""
        ).startswith("application/json"):
            raise ValueError(
                "LeetCode OAuth token endpoint rejected the request "
                f"(HTTP {response.status_code}); it is protected by a bot check."
            )
        payload = response.json()
        if payload.get("error"):
            raise ValueError(f"LeetCode OAuth error: {payload['error']}")
        return payload.get("access_token")

    def _graphql(self, query, **variables):
        data = self._request("POST", self.GRAPHQL_URL, json_body={"query": query, "variables": variables})
        if data.get("errors"):
            raise RuntimeError(f"LeetCode GraphQL error: {data['errors'][0].get('message')}")
        return data.get("data") or {}

    def _request(self, method, url, params=None, json_body=None):
        headers = {
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com/",
            "Origin": "https://leetcode.com",
            "User-Agent": self.USER_AGENT,
        }
        if self._access_token:
            headers["Cookie"] = f"LEETCODE_SESSION={self._access_token}"
            headers["Authorization"] = f"Bearer {self._access_token}"

        response = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=self.DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    def _normalize_contrib_counts(self, payload):
        if not isinstance(payload, dict):
            return {}
        return {int(day): int(count) for day, count in payload.items() if str(day).lstrip("-").isdigit()}

    def _by_difficulty(self, entries):
        return {
            (entry or {}).get("difficulty"): {
                "count": (entry or {}).get("count", 0),
                "submissions": (entry or {}).get("submissions", 0),
            }
            for entry in (entries or [])
        }

    def _acceptance_rate(self, solved, attempted):
        """Share of submissions that were accepted."""
        total_submissions = attempted.get("All", {}).get("submissions", 0)
        if not total_submissions:
            return 0.0
        accepted = solved.get("All", {}).get("submissions", 0)
        return round(accepted / total_submissions * 100, 2)

    def _problem_coverage(self, solved, attempted):
        """Share of distinct problems attempted that were solved."""
        attempted_count = attempted.get("All", {}).get("count", 0)
        if not attempted_count:
            return 0.0
        return round(solved.get("All", {}).get("count", 0) / attempted_count * 100, 2)

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
