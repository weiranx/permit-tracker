"""Thin client for recreation.gov's undocumented JSON endpoints.

These are the same calls the recreation.gov web UI makes. They are not a
public API: no key, no SLA, and shapes can change without notice. The client
paces itself and backs off hard on throttling so it behaves like one person
leaving a browser tab open.
"""
from __future__ import annotations

import calendar
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

BASE = "https://www.recreation.gov/api"
USER_AGENT = (
    "permit-tracker/0.1 (personal availability watcher; "
    "polls a few permits every few minutes)"
)


class RateLimited(Exception):
    """recreation.gov answered 429; stop hitting it until the cooldown ends."""


class NotFound(Exception):
    pass


class RecGovClient:
    def __init__(self, min_interval: float = 2.0, timeout: float = 20.0,
                 user_agent: str = USER_AGENT):
        self.min_interval = min_interval
        self.timeout = timeout
        self.user_agent = user_agent
        self._last_call = 0.0
        self.cooldown_until = 0.0

    # -- transport ---------------------------------------------------------
    def get_json(self, path: str, params: dict | None = None) -> dict:
        if time.time() < self.cooldown_until:
            raise RateLimited(f"cooling down until {time.ctime(self.cooldown_until)}")
        url = f"{BASE}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        })
        delay = 2.0
        for attempt in range(4):
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.load(resp)
                if not isinstance(body, dict):
                    raise ValueError(f"unexpected JSON from {url}")
                return body
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise NotFound(url) from e
                if e.code == 400:
                    # permitinyo answers 400 {"error":"invalid permit id"} for
                    # permits it doesn't serve; surface other 400s verbatim.
                    detail = e.read().decode("utf-8", "replace")[:200]
                    if "invalid permit id" in detail:
                        raise NotFound(url) from e
                    raise ValueError(f"400 from {url}: {detail}") from e
                if e.code == 429:
                    # Retrying a 429 only extends the block. Back off for a while.
                    retry_after = e.headers.get("Retry-After")
                    pause = float(retry_after) if retry_after and retry_after.isdigit() else 600
                    self.cooldown_until = time.time() + pause
                    raise RateLimited(f"429 from recreation.gov; pausing {pause:.0f}s") from e
                if e.code < 500 or attempt == 3:
                    raise
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == 3:
                    raise
            time.sleep(delay + random.uniform(0, 1))
            delay *= 2
        raise RuntimeError("unreachable")

    # -- endpoints ---------------------------------------------------------
    def permit_content(self, permit_id: str) -> dict:
        """Permit metadata: name, divisions (trailheads/entry points/zones)."""
        return self.get_json(f"/permitcontent/{permit_id}")

    def inyo_availability(self, permit_id: str, start: date, end: date) -> dict:
        """Quota-by-trailhead availability used by Inyo-style permits
        (Mt. Whitney, Inyo NF, Sierra NF, and other Sierra wilderness permits).
        start/end must be the first and last day of one calendar month, or the
        API answers 400 "can only be start/end of the month"."""
        return self.get_json(f"/permitinyo/{permit_id}/availabilityv2", {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "commercial_acct": "false",
        })

    def permits_month(self, permit_id: str, month_start: date) -> dict:
        """Generic permit availability (day-use, lottery-style and many NPS permits)."""
        return self.get_json(f"/permits/{permit_id}/availability/month", {
            "start_date": f"{month_start:%Y-%m}-01T00:00:00.000Z",
            "commercial_acct": "false",
        })


def month_chunks(start: date, end: date):
    """Yield (first_day, last_day) of every calendar month touching start..end.
    Whole months only: permitinyo rejects partial-month ranges."""
    cur = start.replace(day=1)
    while cur <= end:
        last = cur.replace(day=calendar.monthrange(cur.year, cur.month)[1])
        yield cur, last
        cur = last + timedelta(days=1)
