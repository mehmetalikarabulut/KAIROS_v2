"""Portable CSV import/export for personal availability constraints.

The format deliberately contains only staff availability.  Institutional policy,
course conflict rules, and room reservations belong to their own inputs.
"""
from __future__ import annotations

import csv
import io
import re

from .csv_import import normalize_header

HEADER = ("Role", "Name", "Constraint", "Day", "Start", "End")
_DAY = {"mo": "Mo", "mon": "Mo", "monday": "Mo", "tu": "Tu", "tue": "Tu", "tuesday": "Tu",
        "we": "We", "wed": "We", "wednesday": "We", "th": "Th", "thu": "Th", "thursday": "Th",
        "fr": "Fr", "fri": "Fr", "friday": "Fr", "sa": "Sa", "sat": "Sa", "saturday": "Sa",
        "su": "Su", "sun": "Su", "sunday": "Su"}
_TIERS = {"unavailable": "availability", "avoid": "availability_avoid", "prefer": "availability_prefer"}
_ROLES = {"instructor": "", "assistant": "assistant_"}
_S = re.compile(r"\(S\)", re.I)
_WS = re.compile(r"\s+")


def normalize_identity(name: str) -> str:
    """Same name-only identity used by course input: case/space normalized, no fuzzy merge."""
    return _WS.sub(" ", _S.sub("", str(name or ""))).strip().casefold()


def _hour(value: str, field: str) -> int:
    if not re.fullmatch(r"(?:[01]\d|2[0-4]):00", str(value or "").strip()):
        raise ValueError(f"{field} must be a whole-hour HH:MM value from 00:00 to 24:00")
    return int(value[:2])


def _expanded_slots(entries, day_start=9, day_end=18):
    """Expand legacy AM/PM state using the application's existing 13:00 boundary."""
    out = set()
    for entry in entries or []:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        day, value = str(entry[0]), entry[1]
        if str(value).upper() == "AM":
            hours = range(day_start, 13)
        elif str(value).upper() == "PM":
            hours = range(13, day_end)
        else:
            try:
                hours = (int(value),)
            except (TypeError, ValueError):
                continue
        for hour in hours:
            if 0 <= hour < 24:
                out.add((day, hour))
    return out


def export_constraints(maps: dict, settings: dict | None = None) -> bytes:
    """Return UTF-8-with-BOM CSV, including people no longer in loaded courses."""
    settings = settings or {}
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(HEADER)
    for role, prefix in _ROLES.items():
        for tier_label, suffix in _TIERS.items():
            for name, entries in (maps.get(prefix + suffix, {}) or {}).items():
                for day, hour in sorted(_expanded_slots(entries, settings.get("day_start", 9), settings.get("day_end", 18))):
                    writer.writerow((role.title(), name, tier_label.title(), day, f"{hour:02}:00", f"{hour + 1:02}:00"))
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def parse_constraints_csv(text: str) -> dict:
    """Validate the entire CSV before returning normalized availability state."""
    try:
        rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    except csv.Error as exc:
        raise ValueError(f"Invalid CSV: {exc}") from exc
    if not rows or tuple(normalize_header(c) for c in rows[0]) != tuple(normalize_header(c) for c in HEADER):
        raise ValueError("Headers must be exactly: Role, Name, Constraint, Day, Start, End")
    result = {prefix + suffix: {} for prefix in _ROLES.values() for suffix in _TIERS.values()}
    display = {}
    for number, row in enumerate(rows[1:], 2):
        if len(row) != 6:
            raise ValueError(f"Row {number}: expected 6 columns")
        role, name, tier, day, start, end = (str(v).strip() for v in row)
        role_key, tier_key, day_key = role.casefold(), tier.casefold(), day.casefold()
        identity = normalize_identity(name)
        if role_key not in _ROLES or tier_key not in _TIERS or day_key not in _DAY or not identity:
            raise ValueError(f"Row {number}: invalid Role, Name, Constraint, or Day")
        begin, finish = _hour(start, "Start"), _hour(end, "End")
        if finish <= begin:
            raise ValueError(f"Row {number}: End must be after Start")
        key = _ROLES[role_key] + _TIERS[tier_key]
        display.setdefault((key, identity), name)
        bucket = result[key].setdefault(identity, set())
        bucket.update((_DAY[day_key], h) for h in range(begin, finish))
    return {key: {identity: [[day, hour] for day, hour in sorted(slots)]
                  for identity, slots in values.items()} for key, values in result.items()}


def merge_constraints(existing: dict, incoming: dict, replace_all: bool = False) -> dict:
    """Merge slots safely, or replace every role/tier (including with an empty CSV)."""
    keys = tuple(incoming)
    out = {key: {} if replace_all else dict(existing.get(key, {}) or {}) for key in keys}
    for key in keys:
        for name, slots in incoming[key].items():
            combined = {(str(d), int(h)) for d, h in out[key].get(name, [])}
            combined.update((str(d), int(h)) for d, h in slots)
            out[key][name] = [[d, h] for d, h in sorted(combined)]
    return out
