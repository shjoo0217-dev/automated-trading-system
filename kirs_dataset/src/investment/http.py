"""Bounded, polite HTTPS client. No auth/CAPTCHA/robots bypass."""
from __future__ import annotations

import time
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import requests

from .common import digest, now


class AccessBlocked(RuntimeError):
    pass


class PublicClient:
    def __init__(self, allowed_hosts: list[str], interval=3.0, retries=2, max_bytes=20_000_000,
                 max_requests=40, max_retry_after=45):
        self.allowed_hosts = set(allowed_hosts)
        self.interval = interval
        self.retries = retries
        self.max_bytes = max_bytes
        self.max_requests = max_requests
        self.max_retry_after = max_retry_after
        self.used = 0
        self.last = {}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "KIRS-Investment-Research/0.1 (+bounded-public-source-check)"
        self.audit = []
        self.robots_cache = {}
        self.host_intervals = {}

    def _check_url(self, url):
        p = urlparse(url)
        if p.scheme != "https" or p.hostname not in self.allowed_hosts or p.username or p.password:
            raise AccessBlocked("URL not in explicit HTTPS host allowlist")
        if p.hostname in {"t.me", "telegram.org"}:
            raise AccessBlocked("Telegram content collection disabled by content licensing terms")

    def get(self, url: str, *, check_robots=True):
        self._check_url(url)
        if check_robots:
            self.require_robots(url)
        original_url = url
        for redirect in range(5):
            self._check_url(url)
            host = urlparse(url).hostname
            for attempt in range(self.retries + 1):
                if self.used >= self.max_requests:
                    raise AccessBlocked("Per-run request cap reached")
                interval = max(self.interval, self.host_intervals.get(host, 0))
                time.sleep(max(0, interval - (time.monotonic() - self.last.get(host, 0))))
                self.last[host] = time.monotonic()
                self.used += 1
                entry = {"url": url, "started_at": now(), "attempt": attempt + 1}
                try:
                    with self.session.get(url, timeout=(10, 25), stream=True, allow_redirects=False) as r:
                        data = bytearray()
                        for chunk in r.iter_content(65536):
                            data.extend(chunk)
                            if len(data) > self.max_bytes:
                                raise AccessBlocked("Response exceeds byte cap")
                        body = bytes(data)
                        entry.update(status=r.status_code, bytes=len(body), sha256=digest(body), finished_at=now())
                        self.audit.append(entry)
                        if r.status_code in {301, 302, 303, 307, 308}:
                            target = urljoin(url, r.headers["Location"])
                            self._check_url(target)
                            if check_robots:
                                self.require_robots(target)
                            url = target
                            break
                        if r.status_code in {401, 403}:
                            raise AccessBlocked(f"HTTP {r.status_code}; no bypass")
                        if r.status_code in {429, 500, 502, 503, 504} and attempt < self.retries:
                            retry_after = r.headers.get("Retry-After")
                            delay = 2 ** (attempt + 1)
                            if retry_after:
                                try:
                                    delay = max(delay, int(retry_after))
                                except ValueError:
                                    delay = max(delay, (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds())
                            if delay > self.max_retry_after:
                                raise AccessBlocked("Retry-After exceeds run allowance; defer to next run")
                            time.sleep(delay)
                            continue
                        if r.status_code >= 400:
                            raise AccessBlocked(f"HTTP {r.status_code}")
                        if b"cupid.js" in body or b"cf-chl-" in body:
                            raise AccessBlocked("Interactive challenge; collection stopped")
                        return body, {**entry, "requested_url": original_url, "final_url": url,
                                      "content_type": r.headers.get("Content-Type"),
                                      "etag": r.headers.get("ETag"),
                                      "last_modified": r.headers.get("Last-Modified")}
                except requests.RequestException as e:
                    # Never print request URLs from authenticated clients in exception strings.
                    entry.update(error=type(e).__name__, finished_at=now())
                    self.audit.append(entry)
                    if attempt == self.retries:
                        raise AccessBlocked(type(e).__name__) from None
                    time.sleep(2 ** (attempt + 1))
            else:
                raise AccessBlocked("Retries exhausted")
        raise AccessBlocked("Redirect limit")

    def require_robots(self, url):
        p = urlparse(url)
        origin = f"https://{p.hostname}"
        if origin not in self.robots_cache:
            try:
                body, _ = self.get(origin + "/robots.txt", check_robots=False)
                text = body.decode("utf-8", errors="replace")
                if "<html" in text.lower() or "user-agent:" not in text.lower():
                    raise AccessBlocked("robots.txt unavailable or not a robots file")
                rp = RobotFileParser()
                rp.parse(text.splitlines())
                # Conservative maximum also handles repeated wildcard groups.
                delays = re.findall(r"(?im)^crawl-delay:\s*(\d+(?:\.\d+)?)", text)
                if delays:
                    self.host_intervals[p.hostname] = max(map(float, delays))
                self.robots_cache[origin] = rp
            except AccessBlocked:
                self.robots_cache[origin] = None
        rp = self.robots_cache[origin]
        if rp is None or not rp.can_fetch(self.session.headers["User-Agent"], url):
            raise AccessBlocked("Robots permission unconfirmed or disallowed")
