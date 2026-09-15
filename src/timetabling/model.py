from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Room:
    room: str
    cap: int
    is_lab: bool
    is_physical: bool
    is_virtual: bool = False
    type: str = ""              # canonical category; blank migrates legacy boolean fields
    dept: str = ""              # semicolon-separated owner dept names; "" = open to all
    reservations: frozenset = frozenset()  # (day, start minute, end minute), weekly

    def __post_init__(self):
        from .csv_import import normalize_room_type
        category = normalize_room_type(self.type) if self.type else (
            "online" if self.is_virtual else "electronics_lab" if self.is_lab else "classroom")
        object.__setattr__(self, "type", category)
        object.__setattr__(self, "is_virtual", category == "online")
        object.__setattr__(self, "is_physical", category != "online")
        object.__setattr__(self, "is_lab", category in ("pc_lab", "electronics_lab"))


@dataclass(frozen=True)
class Instructor:
    staff_id: str
    name: str
    is_staff: bool          # True = full-time
    home_dept: str


def virtual_supply(rooms, name="Online") -> Room:
    """Unlimited supply, preserving inventory metadata and avoiding physical-name collisions."""
    rooms = list(rooms)
    for room in rooms:
        if room.is_virtual:
            return room
    names = {r.room for r in rooms}
    candidate = name
    index = 1
    while candidate in names:
        candidate = f"{name} {index}"
        index += 1
    return Room(candidate, 10_000, False, False, True, "online")


@dataclass(frozen=True)
class Block:
    block_id: str           # e.g. "ADA 403_01#T" or "...#L"
    section_id: str
    kind: str               # "theory" | "practice" | "lab"
    length: int             # hours
    needs_lab: bool


@dataclass
class Section:
    section_id: str
    period: str
    code: str               # "ADA 403"
    name: str
    level: int              # 1..6
    dept_code: str          # "ADA"
    department: str         # Grades "Dept." column (faculty/department name)
    cohort_key: str         # "ADA-4"
    instructor_ids: List[str]
    students: int
    T: int
    P: int
    L: int
    Cr: int
    category: str
    blocks: List[Block] = field(default_factory=list)
    is_virtual: bool = False
    plan_room: str = ""
    lab_room: str = ""          # pinned lab room (from Plan), "" = any lab-family room
    requires_lab_room: bool = False  # back-compat boolean (required_room_type in lab-family)
    required_room_type: str = ""     # canonical demand; blank preserves legacy block defaults
    fixed_day: str = ""         # pin the section's first block to this day ("" = unpinned)
    fixed_start: int = -1       # pin the section's first block to this start hour (-1 = unpinned)
    min_working_days: int = 0   # soft target: section should occupy at least this many days
    assistant_ids: List[str] = field(default_factory=list)
    assistant_names: dict[str, str] = field(default_factory=dict)
    # Lab blocks always have an assistant.  When the input omits a named one,
    # these hold a per-instructor assignment placeholder for the final schedule.
    lab_assistant_ids: List[str] = field(default_factory=list)
    lab_assistant_names: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        # Older programmatic callers sometimes pass a scalar staff ID.
        if isinstance(self.instructor_ids, str):
            self.instructor_ids = [i.strip() for i in self.instructor_ids.split(",") if i.strip()]
        if isinstance(self.assistant_ids, str):
            self.assistant_ids = [i.strip() for i in self.assistant_ids.split(",") if i.strip()]

    def block_kind(self, block_id: str) -> str:
        for block in self.blocks:
            if block.block_id == block_id:
                return block.kind
        # Legacy repair/benchmark callers may omit blocks; preserve readable ID migration.
        tag = block_id.rsplit("#", 1)[-1][:1]
        return {"P": "practice", "L": "lab"}.get(tag, "theory")

    def assistants_for(self, kind: str) -> List[str]:
        if kind == "lab":
            return self.lab_assistant_ids or self.assistant_ids
        return self.assistant_ids if kind == "practice" else []

    def human_ids(self, kind: str) -> List[str]:
        return list(dict.fromkeys(self.instructor_ids + self.assistants_for(kind)))


@dataclass(frozen=True)
class Candidate:
    block_id: str
    room: str
    day: str
    start: int              # start hour
    length: int
    cap: int = 0            # room capacity (0 for virtual rooms)


@dataclass(frozen=True)
class Assignment:
    block_id: str
    section_id: str
    kind: str
    room: str
    day: str
    start: int
    end: int                # exclusive (start + length)


@dataclass(frozen=True)
class Violation:
    kind: str               # "instructor" | "cohort" | "room" | "capacity" | "lab" | "window" | "blackout" | "placement"
    detail: str


def weekly_load_hours(sections) -> dict:
    """Total weekly teaching hours per instructor id (team-taught counts fully per id)."""
    load: dict = {}
    for s in sections:
        h = sum(b.length for b in s.blocks)
        for iid in s.instructor_ids:
            load[iid] = load.get(iid, 0) + h
    return load
