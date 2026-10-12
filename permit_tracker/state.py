"""Remembers what was open last poll so we alert on openings, not on every poll."""
from __future__ import annotations

import sqlite3
import time


class State:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS seen (
            permit_id TEXT, division_id TEXT, date TEXT,
            remaining INTEGER, updated REAL,
            PRIMARY KEY (permit_id, division_id, date))""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS history (
            ts REAL, permit_id TEXT, division_id TEXT, date TEXT,
            old_remaining INTEGER, new_remaining INTEGER)""")

    def update(self, permit_id: str, division_id: str, day: str, remaining: int):
        """Store the new count and return the previous one (None if never seen)."""
        row = self.db.execute(
            "SELECT remaining FROM seen WHERE permit_id=? AND division_id=? AND date=?",
            (permit_id, division_id, day)).fetchone()
        old = row[0] if row else None
        now = time.time()
        self.db.execute("INSERT OR REPLACE INTO seen VALUES (?,?,?,?,?)",
                        (permit_id, division_id, day, remaining, now))
        if old != remaining:
            self.db.execute("INSERT INTO history VALUES (?,?,?,?,?,?)",
                            (now, permit_id, division_id, day, old, remaining))
        self.db.commit()
        return old

    def recent(self, limit: int = 40) -> list[dict]:
        """Latest count changes, newest first (first sightings excluded)."""
        rows = self.db.execute(
            "SELECT ts, permit_id, division_id, date, old_remaining, new_remaining "
            "FROM history WHERE old_remaining IS NOT NULL ORDER BY ts DESC LIMIT ?",
            (limit,)).fetchall()
        return [{"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r[0])),
                 "permit_id": r[1], "division_id": r[2], "date": r[3],
                 "old": r[4], "new": r[5]} for r in rows]
