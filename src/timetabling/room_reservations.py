"""Weekly external bookings. Department is descriptive, never an exemption."""
from dataclasses import replace
import re
from .csv_import import normalize_header

_DAYS = dict(zip(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"), (
    ("mo", "mon", "monday", "pazartesi"), ("tu", "tue", "tuesday", "sali"),
    ("we", "wed", "wednesday", "carsamba"), ("th", "thu", "thursday", "persembe"),
    ("fr", "fri", "friday", "cuma"), ("sa", "sat", "saturday", "cumartesi"),
    ("su", "sun", "sunday", "pazar"))))


def _minutes(value):
    match = re.fullmatch(r"(\d{1,2})(?::([0-5]\d)(?::00)?)?", str(value).strip())
    if not match:
        raise ValueError("Time must be HH:MM, for example 11:00")
    hour, minute = int(match[1]), int(match[2] or 0)
    if hour > 24 or (hour == 24 and minute):
        raise ValueError("Time must be between 00:00 and 24:00")
    return hour * 60 + minute


def parse_room_reservations(raw_rows):
    """Require headers and reject malformed reservations; ignore blank Room cells."""
    rows = [r for r in raw_rows if any(str(v or "").strip() for v in r)]
    if not rows:
        return []
    headers = [normalize_header(v) for v in rows[0]]
    for field in ("room", "day", "start", "end"):
        if headers.count(field) != 1:
            raise ValueError(f"Exactly one {field.title()} column is required")
    out = []
    for n, row in enumerate(rows[1:], 2):
        def cell(key):
            idx = headers.index(key) if key in headers else len(row)
            return str(row[idx] or "").strip() if idx < len(row) else ""
        room = cell("room")
        if not room:
            continue
        try:
            day = next((d for d, aliases in _DAYS.items() if normalize_header(cell("day")) in aliases), None)
            if day is None:
                raise ValueError("Day must be Monday–Sunday (or Mo–Su)")
            start, end = _minutes(cell("start")), _minutes(cell("end"))
            if start >= end:
                raise ValueError("End must be after Start on the same day")
            out.append({"Room": room, "Dept": cell("dept"), "Day": day,
                        "Start": f"{start // 60:02}:{start % 60:02}",
                        "End": f"{end // 60:02}:{end % 60:02}"})
        except ValueError as exc:
            raise ValueError(f"Row {n}: {exc}") from exc
    return out


def apply_room_reservations(rooms, rows):
    """Attach bookings to a fresh inventory; reject unknown and virtual rooms."""
    bookings = {key: set(room.reservations) for key, room in rooms.items()}
    for row in rows:
        name = row["Room"]
        if name not in rooms:
            raise ValueError(f"Reservation room is not in the room inventory: {name}")
        if rooms[name].is_virtual:
            raise ValueError(f"Reservations require a physical room: {name}")
        bookings[name].add((row["Day"], _minutes(row["Start"]), _minutes(row["End"])))
    return {key: replace(room, reservations=frozenset(bookings[key])) for key, room in rooms.items()}
