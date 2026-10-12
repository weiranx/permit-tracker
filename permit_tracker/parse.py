"""Normalize recreation.gov availability payloads into flat Slot records.

Two shapes are handled:

permitinyo availabilityv2 (Inyo-style quota permits):
    {"payload": {"2026-07-14": {"<division_id>": {
        "quota_usage_by_member_daily": {"total": 60, "remaining": 3},
        "is_walkup": false, "not_yet_released": 0, "release_date": "..."}}}}

permits/{id}/availability/month (generic):
    {"payload": {"availability": {"<division_id>": {
        "date_availability": {"2026-07-14T00:00:00Z": {"total": 30, "remaining": 2,
                                                       "show_walkup": false}}}}}}
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Slot:
    division_id: str
    date: str          # YYYY-MM-DD (trip entry date)
    remaining: int
    total: int | None
    walkup: bool = False
    not_yet_released: bool = False


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_inyo(body: dict) -> list[Slot]:
    payload = body.get("payload") or {}
    slots = []
    for day, divisions in payload.items():
        if not isinstance(divisions, dict):
            continue
        for div_id, info in divisions.items():
            if not isinstance(info, dict):
                continue
            q = info.get("quota_usage_by_member_daily") or info
            remaining = _int(q.get("remaining"))
            if remaining is None:
                continue
            slots.append(Slot(
                division_id=str(div_id),
                date=str(day)[:10],
                remaining=remaining,
                total=_int(q.get("total")),
                walkup=bool(info.get("is_walkup")),
                not_yet_released=bool(info.get("not_yet_released")),
            ))
    return slots


def parse_permits_month(body: dict) -> list[Slot]:
    payload = body.get("payload") or body
    avail = payload.get("availability") or {}
    slots = []
    for key, entry in avail.items():
        if not isinstance(entry, dict):
            continue
        if "date_availability" in entry:
            div_id = str(entry.get("division_id") or key)
            for day, info in (entry.get("date_availability") or {}).items():
                remaining = _int((info or {}).get("remaining"))
                if remaining is None:
                    continue
                slots.append(Slot(div_id, str(day)[:10], remaining,
                                  _int(info.get("total")), bool(info.get("show_walkup"))))
        elif "remaining" in entry:  # older flat shape keyed by date
            remaining = _int(entry.get("remaining"))
            if remaining is not None:
                slots.append(Slot("", str(key)[:10], remaining, _int(entry.get("total"))))
    return slots


def parse_divisions(content: dict) -> dict[str, dict]:
    """permitcontent -> {division_id: {name, code, district, ...}}"""
    payload = content.get("payload") or {}
    divs = payload.get("divisions") or {}
    out = {}
    for key, d in divs.items():
        if isinstance(d, dict):
            out[str(d.get("id") or key)] = {
                "name": d.get("name", ""),
                "code": d.get("code", ""),
                "district": d.get("district", ""),
            }
    return out


def permit_name(content: dict) -> str:
    payload = content.get("payload") or {}
    return payload.get("name") or payload.get("permit_name") or ""
