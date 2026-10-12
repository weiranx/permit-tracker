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
