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
_LEGACY_ROLES = {"tz": "instructor", "dsu": "instructor", "dsü": "instructor"}
_S = re.compile(r"\(S\)", re.I)
_WS = re.compile(r"\s+")


def normalize_identity(name: str) -> str:
    """Same name-only identity used by course input: case/space normalized, no fuzzy merge."""
    return _WS.sub(" ", _S.sub("", str(name or ""))).strip().casefold()


def _hour(value: str, field: str) -> int:
    if not re.fullmatch(r"(?:[01]\d|2[0-4]):00", str(value or "").strip()):
        raise ValueError(f"{field} must be a whole-hour HH:MM value from 00:00 to 24:00")
    return int(value[:2])


def _legacy_minutes(value: str, field: str, default: int) -> int:
    """Parse a legacy optional HH:MM boundary without weakening the new schema."""
    value = str(value or "").strip()
    if not value:
        return default
    if not re.fullmatch(r"(?:[01]?\d|2[0-4]):[0-5]\d", value):
        raise ValueError(f"{field} must be HH:MM")
    hour, minute = (int(part) for part in value.split(":"))
    if hour == 24 and minute:
        raise ValueError(f"{field} must be between 00:00 and 24:00")
    return hour * 60 + minute


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


def parse_constraints_csv(text: str, day_start: int = 9, day_end: int = 18,
                          days=("Mo", "Tu", "We", "Th", "Fr")) -> dict:
    """Validate the entire CSV before returning normalized availability state."""
    try:
        rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    except csv.Error as exc:
        raise ValueError(f"Invalid CSV: {exc}") from exc
    if not rows or tuple(normalize_header(c) for c in rows[0]) != tuple(normalize_header(c) for c in HEADER):
        raise ValueError("Headers must be exactly: Role, Name, Constraint, Day, Start, End")
    result = {prefix + suffix: {} for prefix in _ROLES.values() for suffix in _TIERS.values()}
    display = {}
    legacy_available = {}
    for number, row in enumerate(rows[1:], 2):
        if len(row) != 6:
            raise ValueError(f"Row {number}: expected 6 columns")
        role, name, tier, day, start, end = (str(v).strip() for v in row)
        role_key, tier_key, day_key = role.casefold(), tier.casefold(), day.casefold()
        identity = normalize_identity(name)
        legacy = role_key in _LEGACY_ROLES or tier_key == "available"
        if legacy:
            role_key = _LEGACY_ROLES.get(role_key, role_key)
        if role_key not in _ROLES or day_key not in _DAY or not identity:
            raise ValueError(f"Row {number}: invalid Role, Name, Constraint, or Day")
        if legacy and tier_key == "available":
            begin = _legacy_minutes(start, "Start", day_start * 60)
            finish = _legacy_minutes(end, "End", day_end * 60)
            if finish <= begin:
                raise ValueError(f"Row {number}: End must be after Start")
            legacy_available.setdefault((role_key, identity), {}).setdefault(_DAY[day_key], []).append((begin, finish))
            continue
        if tier_key not in _TIERS:
            raise ValueError(f"Row {number}: invalid Role, Name, Constraint, or Day")
        if legacy:
            begin = _legacy_minutes(start, "Start", day_start * 60)
            finish = _legacy_minutes(end, "End", day_end * 60)
        else:
            begin, finish = _hour(start, "Start"), _hour(end, "End")
        if finish <= begin:
            raise ValueError(f"Row {number}: End must be after Start")
        key = _ROLES[role_key] + _TIERS[tier_key]
        display.setdefault((key, identity), name)
        bucket = result[key].setdefault(identity, set())
        if legacy:
            # A legacy minute-precision unavailability blocks every teaching
            # hour it overlaps; the solver itself schedules in whole hours.
            bucket.update((_DAY[day_key], h) for h in range(day_start, day_end)
                          if h * 60 < finish and (h + 1) * 60 > begin)
        else:
            bucket.update((_DAY[day_key], h) for h in range(begin, finish))
    # Legacy "Available" declares the permitted hours. Convert it to the
    # application's hard-unavailable map; a teaching hour must fit entirely in
    # a declared availability interval. This preserves half-hour boundaries
    # rather than rounding them into extra availability.
    for (role, identity), by_day in legacy_available.items():
        key = _ROLES[role] + _TIERS["unavailable"]
        bucket = result[key].setdefault(identity, set())
        for day in days:
            windows = by_day.get(day, [])
            for hour in range(day_start, day_end):
                start, end = hour * 60, (hour + 1) * 60
                if not any(start >= left and end <= right for left, right in windows):
                    bucket.add((day, hour))
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
