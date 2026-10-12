"""Offline tests. Payloads below are hand-built to the shapes documented in
API_NOTES.md; they are not captured live responses."""
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from unittest import mock

from permit_tracker import cli
from permit_tracker.api import NotFound, month_chunks
from permit_tracker.parse import parse_divisions, parse_inyo, parse_permits_month
from permit_tracker.state import State

CONTENT = {"payload": {"name": "Mt. Whitney", "divisions": {
    "166": {"id": "166", "name": "Mt. Whitney Trail (Overnight)", "code": "JM34", "district": "Mt Whitney"},
    "406": {"id": "406", "name": "Mt. Whitney Day Use (All Routes)", "code": "JM23", "district": "Mt Whitney"},
}}}


def inyo(day_counts):
    return {"payload": {d: {div: {"quota_usage_by_member_daily": {"total": 60, "remaining": r},
                                  "is_walkup": False, "not_yet_released": 0}
                            for div, r in divs.items()}
                        for d, divs in day_counts.items()}}


class FakeClient:
    def __init__(self, inyo_bodies=None, month_body=None, inyo_404=False):
        self.inyo_bodies = list(inyo_bodies or [])
        self.month_body = month_body
        self.inyo_404 = inyo_404
        self.calls = []
        self.cooldown_until = 0

    def permit_content(self, pid):
        return CONTENT

    def inyo_availability(self, pid, lo, hi):
        self.calls.append(("inyo", lo, hi))
        if self.inyo_404:
            raise NotFound(pid)
        return self.inyo_bodies.pop(0) if len(self.inyo_bodies) > 1 else self.inyo_bodies[0]

    def permits_month(self, pid, lo):
        self.calls.append(("permits", lo))
        return self.month_body


class ParseTests(unittest.TestCase):
    def test_inyo(self):
        slots = parse_inyo(inyo({"2027-07-17": {"166": 0, "406": 4}}))
        self.assertEqual({(s.division_id, s.remaining) for s in slots}, {("166", 0), ("406", 4)})
        self.assertEqual(slots[0].date, "2027-07-17")

    def test_permits_month(self):
        body = {"payload": {"availability": {"9": {"division_id": "9", "date_availability": {
            "2027-07-17T00:00:00Z": {"total": 30, "remaining": 2, "show_walkup": False}}}}}}
        [s] = parse_permits_month(body)
        self.assertEqual((s.division_id, s.date, s.remaining, s.total), ("9", "2027-07-17", 2, 30))

    def test_divisions(self):
        self.assertEqual(parse_divisions(CONTENT)["166"]["code"], "JM34")

    def test_month_chunks(self):
        self.assertEqual(list(month_chunks(date(2027, 6, 15), date(2027, 8, 3))), [
            (date(2027, 6, 1), date(2027, 6, 30)),
            (date(2027, 7, 1), date(2027, 7, 31)),
            (date(2027, 8, 1), date(2027, 8, 31))])


UNRELEASED = {"payload": {"2027-07-17": {
    "166": {"quota_usage_by_member_daily": {"total": 0, "remaining": 0}, "is_walkup": True,
            "not_yet_released": True, "release_date": "2027-01-17T07:00:00-08:00"},
    "520": {"quota_usage_by_member_daily": {"total": 899990, "remaining": 899990}, "is_walkup": False}}}}


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state = State(os.path.join(self.tmp, "s.db"))
        self.cfg = {"notify": {}, "watches": [{
            "name": "Whitney", "permit_id": "445860", "divisions": ["166"],
            "dates": ["2027-07-17"], "min_party": 2}]}

    def run_with(self, body):
        tracker = cli.Tracker(FakeClient([body]))
        with mock.patch.object(cli.notify, "send_all") as send, redirect_stdout(io.StringIO()):
            cli.run_once(self.cfg, tracker, self.state)
        return send

    def test_alerts_only_on_transition(self):
        self.assertFalse(self.run_with(inyo({"2027-07-17": {"166": 0}})).called)
        self.assertFalse(self.run_with(inyo({"2027-07-17": {"166": 1}})).called)  # below party size
        send = self.run_with(inyo({"2027-07-17": {"166": 3}}))
        self.assertEqual(send.call_count, 1)
        self.assertIn("detailed-availability?date=2027-07-17", send.call_args[0][3])
        self.assertFalse(self.run_with(inyo({"2027-07-17": {"166": 2}})).called)  # still open
        self.run_with(inyo({"2027-07-17": {"166": 0}}))
        self.assertTrue(self.run_with(inyo({"2027-07-17": {"166": 2}})).called)  # re-opened

    def test_division_and_weekday_filters(self):
        self.cfg["watches"][0].update(dates=None, divisions=None, division_names=["day use"],
                                      start="2027-07-16", end="2027-07-18", weekdays=["sat"])
        with mock.patch.object(cli, "date", wraps=date) as d:
            d.today.return_value = date(2027, 1, 1)
            send = self.run_with(inyo({"2027-07-16": {"406": 5}, "2027-07-17": {"406": 5, "166": 5}}))
        self.assertEqual(send.call_count, 1)
        self.assertIn("Day Use", send.call_args[0][1])

    def test_report_rows_for_dashboard(self):
        report = []
        tracker = cli.Tracker(FakeClient([inyo({"2027-07-17": {"166": 5}})]))
        with mock.patch.object(cli.notify, "send_all"), redirect_stdout(io.StringIO()):
            cli.run_once(self.cfg, tracker, self.state, report=report)
        [w] = report
        self.assertEqual(w["permit_name"], "Mt. Whitney")
        self.assertEqual(w["rows"][0]["state"], "open")
        self.assertEqual(w["rows"][0]["division"], "Mt. Whitney Trail (Overnight)")

    def test_skips_unreleased_and_non_quota(self):
        self.cfg["watches"][0]["divisions"] = ["166", "520"]
        self.assertFalse(self.run_with(UNRELEASED).called)

    def test_lottery_untouched_quota_is_not_an_opening(self):
        lottery_content = {"payload": {**CONTENT["payload"], "has_lottery": True}}
        with mock.patch.object(FakeClient, "permit_content", return_value=lottery_content):
            body = {"payload": {"2027-07-17": {"166": {
                "quota_usage_by_member_daily": {"total": 60, "remaining": 60}, "is_walkup": False}}}}
            self.assertFalse(self.run_with(body).called)
            self.assertTrue(self.run_with(inyo({"2027-07-17": {"166": 3}})).called)

    def test_falls_back_to_generic_endpoint(self):
        body = {"payload": {"availability": {"1": {"division_id": "1", "date_availability": {
            "2027-07-17T00:00:00Z": {"total": 5, "remaining": 5}}}}}}
        fc = FakeClient(month_body=body, inyo_404=True)
        slots = cli.Tracker(fc).fetch("999", date(2027, 7, 1), date(2027, 7, 31))
        self.assertEqual(len(slots), 1)
        self.assertEqual([c[0] for c in fc.calls], ["inyo", "permits"])


if __name__ == "__main__":
    unittest.main()
