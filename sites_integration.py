import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests


class SiteStatus:
    """
    Reachability checks for the self-hosted sites listed in SELF_HOSTED_SITES.

    Deliberately not an ``Integration`` subclass: that base class is shaped
    around a per-user provider that authenticates, caches a payload per account
    and can be logged out. A URL check has no credentials, no user and no
    session, so the auth surface would be four methods that do nothing.

    Sites are configured as ``name=url`` pairs, comma separated, with an
    optional ``|keyword`` that must appear in the body:

        SELF_HOSTED_SITES=blog=https://blog.example.com,immich=http://10.0.0.4:2283|/login

    A bare url is allowed, in which case the host becomes the label.
    """

    DEFAULT_TIMEOUT = 8.0
    MAX_WORKERS = 8
    # 2xx and 3xx count as reachable: a healthy service commonly redirects.
    UP_FROM = 200
    UP_TO = 399
    # Enough to spot a login page or a health string without pulling a whole
    # application into memory.
    MAX_BODY_BYTES = 65536
    USER_AGENT = "my-daily-driver/1.0 (+site-status)"

    def __init__(self, timeout=None, workers=None):
        self.timeout = float(timeout or self.DEFAULT_TIMEOUT)
        self.workers = int(workers or self.MAX_WORKERS)

    # ---------- configuration ----------

    def parse(self, raw=None):
        """
        Turn the SELF_HOSTED_SITES value into a list of site definitions.

        Malformed entries are dropped rather than raising, so one typo cannot
        take the whole dashboard down.
        """
        if raw is None:
            raw = os.environ.get("SELF_HOSTED_SITES", "")
        if not raw or not raw.strip():
            return []

        sites = []
        for chunk in raw.split(","):
            entry = chunk.strip()
            if not entry:
                continue

            label, separator, remainder = entry.partition("=")
            if separator:
                label = label.strip()
                target = remainder.strip()
            else:
                target = label
                label = ""

            url, _, keyword = target.partition("|")
            url = url.strip()
            keyword = keyword.strip()

            if not url:
                continue
            if not url.startswith(("http://", "https://")):
                url = "https://" + url.lstrip("/")

            if not label:
                label = self._label_for(url)

            sites.append({"name": label, "url": url, "keyword": keyword})
        return sites

    @staticmethod
    def _label_for(url):
        """A short host label for entries configured without a name."""
        trimmed = url.split("://", 1)[-1]
        host = trimmed.split("/", 1)[0]
        return host.split(":", 1)[0] or url

    # ---------- checking ----------

    def check(self, site):
        """
        Probe one site, always returning a result.

        A failed check is data, not an exception: the widget needs to show that
        a site is down as readily as one that is up.
        """
        result = {
            "name": site.get("name") or self._label_for(site.get("url", "")),
            "url": site.get("url", ""),
            "up": False,
            "status_code": None,
            "latency_ms": None,
            "detail": "",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        started = time.perf_counter()
        try:
            response = requests.get(
                result["url"],
                timeout=self.timeout,
                allow_redirects=True,
                stream=True,
                headers={"User-Agent": self.USER_AGENT, "Accept": "*/*"},
            )
        except requests.exceptions.Timeout:
            result["latency_ms"] = self._elapsed_ms(started)
            result["detail"] = "timed out after %gs" % self.timeout
            return result
        except requests.exceptions.SSLError as exc:
            result["latency_ms"] = self._elapsed_ms(started)
            result["detail"] = "TLS problem: %s" % self._first_line(exc)
            return result
        except requests.exceptions.ConnectionError as exc:
            result["latency_ms"] = self._elapsed_ms(started)
            result["detail"] = self._describe_connection_error(exc)
            return result
        except requests.RequestException as exc:
            result["latency_ms"] = self._elapsed_ms(started)
            result["detail"] = self._first_line(exc)
            return result

        try:
            result["status_code"] = response.status_code
            result["latency_ms"] = self._elapsed_ms(started)
            reachable = self.UP_FROM <= response.status_code <= self.UP_TO

            keyword = site.get("keyword")
            if keyword:
                body = response.raw.read(self.MAX_BODY_BYTES, decode_content=True) or b""
                found = keyword.lower() in body.decode("utf-8", "replace").lower()
                if not found:
                    reachable = False
                    result["detail"] = "responded without %r" % keyword

            if not reachable and not result["detail"]:
                result["detail"] = "HTTP %s" % response.status_code
            result["up"] = reachable
            if reachable:
                result["detail"] = "HTTP %s" % response.status_code
        finally:
            response.close()

        return result

    def check_all(self, sites):
        """
        Probe every site concurrently.

        Sequential checks would make the widget wait for the sum of every
        timeout, so one unreachable host would hold up the healthy ones.
        """
        if not sites:
            return []
        workers = min(self.workers, len(sites))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(self.check, sites))

    # ---------- helpers ----------

    @staticmethod
    def _elapsed_ms(started):
        return int(round((time.perf_counter() - started) * 1000))

    @staticmethod
    def _first_line(exc):
        """The useful part of a requests error, without the whole traceback."""
        text = str(exc).strip()
        return text.splitlines()[0] if text else exc.__class__.__name__

    @staticmethod
    def _describe_connection_error(exc):
        """
        Separate the connection failures worth telling apart.

        "refused" means nothing is listening, a name lookup failure means the
        host is wrong, and a timeout usually means a firewall dropped it.
        """
        text = SiteStatus._first_line(exc).lower()
        if "name or service not known" in text or "nodename nor servname" in text \
                or "getaddrinfo" in text or "failed to resolve" in text:
            return "host not found"
        if "refused" in text:
            return "connection refused"
        if "timed out" in text or "timeout" in text:
            return "timed out"
        return SiteStatus._first_line(exc)
