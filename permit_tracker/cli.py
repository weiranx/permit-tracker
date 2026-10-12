"""permit-tracker: watch recreation.gov permit quotas and alert when spots open."""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import date, datetime

from . import notify
from .api import NotFound, RateLimited, RecGovClient, month_chunks
from .parse import (Slot, has_lottery, parse_divisions, parse_inyo,
                    parse_permits_month, permit_name)
from .state import State

# Permits known to use the permitinyo quota endpoint. Anything else is tried
# there first and falls back to the generic endpoint on 404.
INYO_STYLE = {
    "445860",  # Mt. Whitney (233260 is the retired legacy ID)
    "233262",  # Inyo NF wilderness (trailhead quotas)
    "445858",  # Sierra NF wilderness
}
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def booking_url(permit_id: str, day: str) -> str:
    return f"https://www.recreation.gov/permits/{permit_id}/registration/detailed-availability?date={day}"


class Tracker:
    def __init__(self, client: RecGovClient):
        self.client = client
        self._api_for: dict[str, str] = {}
        self._content: dict[str, dict] = {}

    def content(self, permit_id: str) -> dict:
        if permit_id not in self._content:
            try:
                self._content[permit_id] = self.client.permit_content(permit_id)
            except (NotFound, RateLimited, OSError, ValueError) as e:
                print(f"[warn] couldn't load details for {permit_id}: {e}", file=sys.stderr)
                return {}
        return self._content[permit_id]

    def names(self, permit_id: str) -> tuple[str, dict]:
        c = self.content(permit_id)
        return (permit_name(c) or permit_id, parse_divisions(c))

    def fetch(self, permit_id: str, start: date, end: date, api: str = "auto") -> list[Slot]:
        api = self._api_for.get(permit_id, api)
        if api == "auto":
            api = "inyo" if permit_id in INYO_STYLE else "auto"
        slots: list[Slot] = []
        for lo, hi in month_chunks(start, end):
            if api in ("inyo", "auto"):
                try:
                    slots += parse_inyo(self.client.inyo_availability(permit_id, lo, hi))
                    self._api_for[permit_id] = "inyo"
                    continue
                except NotFound:
                    if api == "inyo":
                        raise
                    api = "permits"
            slots += parse_permits_month(self.client.permits_month(permit_id, lo))
            self._api_for[permit_id] = "permits"
        lo_s, hi_s = start.isoformat(), end.isoformat()
        return [s for s in slots if lo_s <= s.date <= hi_s]


def _dates_filter(w: dict):
    dates = set(w.get("dates") or [])
    days = {d.lower()[:3] for d in (w.get("weekdays") or [])}

    def ok(day: str) -> bool:
        if dates and day not in dates:
            return False
        if days and WEEKDAYS[date.fromisoformat(day).weekday()] not in days:
            return False
        return True
    return ok


def _range(w: dict) -> tuple[date, date]:
    if w.get("dates"):
        ds = sorted(date.fromisoformat(d) for d in w["dates"])
        return ds[0], ds[-1]
    start = max(date.fromisoformat(w["start"]), date.today())
    return start, date.fromisoformat(w["end"])


def run_once(cfg: dict, tracker: Tracker, state: State, quiet: bool = False) -> int:
    alerts = 0
    for w in cfg["watches"]:
        pid = str(w["permit_id"])
        min_party = int(w.get("min_party", 1))
        want_divs = {str(d) for d in w.get("divisions") or []}
        ok_day = _dates_filter(w)
        start, end = _range(w)
        if end < start:
            continue
        try:
            slots = tracker.fetch(pid, start, end, w.get("api", "auto"))
        except RateLimited as e:
            print(f"[rate-limited] {e}", file=sys.stderr)
            return alerts
        except Exception as e:
            print(f"[error] {w.get('name', pid)}: {e}", file=sys.stderr)
            continue
        pname, divs = tracker.names(pid)
        lottery = has_lottery(tracker.content(pid))
        name_bits = [n.lower() for n in w.get("division_names") or []]
        counts = {"open": 0, "full": 0, "not released": 0}
        for s in sorted(slots, key=lambda s: (s.date, s.division_id)):
            div_name = divs.get(s.division_id, {}).get("name") or s.division_id
            if want_divs and s.division_id not in want_divs:
                continue
            if name_bits and not any(b in div_name.lower() for b in name_bits):
                continue
            if not ok_day(s.date) or s.walkup or s.non_quota:
                continue
            if s.not_yet_released or (lottery and s.total and s.remaining == s.total):
                # Lottery permits (Whitney) show untouched full quotas for dates
                # the lottery hasn't released yet. Real openings are partial.
                counts["not released"] += 1
                continue
            counts["open" if s.remaining >= min_party else "full"] += 1
            old = state.update(pid, s.division_id, s.date, s.remaining)
            if not quiet:
                total = f"/{s.total}" if s.total is not None else ""
                print(f"  {w.get('name', pid):<28} {s.date}  {div_name[:34]:<34} {s.remaining:>3}{total}")
            newly_open = s.remaining >= min_party and (old is None or old < min_party)
            if newly_open:
                alerts += 1
                when = datetime.fromisoformat(s.date).strftime("%a %b %-d")
                notify.send_all(
                    cfg.get("notify", {}),
                    f"Permit open: {div_name} {when}",
                    f"{pname or pid}: {s.remaining} spot(s) for {div_name} on {when} "
                    f"(watch: {w.get('name', pid)}, need {min_party}).",
                    booking_url(pid, s.date),
                )
        print(f"{w.get('name', pid)}: " + ", ".join(f"{v} {k}" for k, v in counts.items())
              + (" (nothing published for these dates yet)" if not any(counts.values()) else ""))
    return alerts


def cmd_watch(args, cfg):
    client = RecGovClient(min_interval=float(cfg.get("min_request_interval_s", 2)))
    tracker, state = Tracker(client), State(cfg.get("state_db", "permit_state.sqlite3"))
    interval = max(60.0, float(cfg.get("poll_minutes", 5)) * 60)
    print(f"Watching {len(cfg['watches'])} permit watch(es) every ~{interval/60:.0f} min. Ctrl-C to stop.")
    while True:
        print(f"[{datetime.now():%H:%M:%S}] checking")
        run_once(cfg, tracker, state, quiet=not args.verbose)
        if client.cooldown_until > time.time():
            time.sleep(client.cooldown_until - time.time())
        time.sleep(interval * random.uniform(0.85, 1.15))  # jitter so we don't poll on the dot


def cmd_check(args, cfg):
    client = RecGovClient(min_interval=float(cfg.get("min_request_interval_s", 2)))
    n = run_once(cfg, Tracker(client), State(cfg.get("state_db", "permit_state.sqlite3")))
    print(f"\n{n} new opening(s).")


def cmd_divisions(args, _cfg):
    content = RecGovClient().permit_content(args.permit_id)
    print(permit_name(content) or args.permit_id)
    for did, d in sorted(parse_divisions(content).items(), key=lambda kv: kv[1]["name"]):
        if args.grep and args.grep.lower() not in d["name"].lower():
            continue
        print(f"  {did:>8}  {d['code']:<8} {d['name']}  ({d['district']})")


def cmd_peek(args, _cfg):
    tracker = Tracker(RecGovClient())
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    _, divs = tracker.names(args.permit_id)
    for s in sorted(tracker.fetch(args.permit_id, start, end),
                    key=lambda s: (s.division_id, s.date)):
        if args.division and s.division_id not in args.division:
            continue
        name = divs.get(s.division_id, {}).get("name") or s.division_id
        tot = f"/{s.total}" if s.total is not None else ""
        note = ("  not released" + (f" (opens {s.release_date[:10]})" if s.release_date else "")
                if s.not_yet_released else "  walk-up only" if s.walkup
                else "  non-quota" if s.non_quota else "")
        count = "  -" if s.non_quota else f"{s.remaining:>3}{tot}"
        print(f"{s.date}  {name[:40]:<40} {count}{note}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="permit-tracker", description=__doc__)
    p.add_argument("-c", "--config", default="config.json")
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch", help="poll forever and alert on new openings")
    w.add_argument("-v", "--verbose", action="store_true")
    sub.add_parser("check", help="one pass over the config, print counts")
    d = sub.add_parser("divisions", help="list a permit's trailheads / entry points")
    d.add_argument("permit_id")
    d.add_argument("--grep")
    k = sub.add_parser("peek", help="print availability for a permit and date range")
    k.add_argument("permit_id")
    k.add_argument("start")
    k.add_argument("end")
    k.add_argument("--division", action="append")
    args = p.parse_args(argv)

    cfg = {}
    if args.cmd in ("watch", "check"):
        with open(args.config) as f:
            cfg = json.load(f)
    {"watch": cmd_watch, "check": cmd_check,
     "divisions": cmd_divisions, "peek": cmd_peek}[args.cmd](args, cfg)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
