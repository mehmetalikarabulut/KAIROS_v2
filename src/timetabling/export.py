from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import json
import csv
import os
import sys

from .model import Assignment, Section, Room, Instructor

# Canonical per-assignment column order, shared by the CLI CSV and the UI
# download so both outputs are byte-for-byte identical in shape.
CSV_FIELDS = ["section_id", "course_code", "course_name", "block_kind",
              "instructor_id", "instructor_name", "cohort", "dept", "department",
              "section_cap", "section_p", "day", "start", "end",
              "room", "room_cap", "is_lab_room", "assistant_id", "assistant_name", "room_type", "is_online"]

# Runtime schedules can contain course, room, and staff information.  Keep them
# outside the source checkout so they cannot be accidentally staged or pushed
# with application code.
def _default_schedule_output_dir() -> Path:
    """Return a private, platform-specific directory outside the checkout."""
    configured = os.environ.get("KAIROS_SCHEDULE_OUTPUT_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        return Path(r"D:\Projects\kairos_v2_schedules")
    if sys.platform == "darwin":
        return Path.home() / "Projects" / "kairos_v2_schedules"
    return Path.home() / "kairos_v2_schedules"


SCHEDULE_OUTPUT_DIR = _default_schedule_output_dir()
ROOM_RESERVATION_FIELDS = ["Room", "Dept", "Day", "Start", "End"]


def build_schedule_dict(period, assignments: List[Assignment], sections: List[Section],
                        rooms: Dict[str, Room], instructors: Dict[str, Instructor],
                        unmet_soft=None, conflicts=None, missing_blocks=None) -> dict:
    sec_by_id = {s.section_id: s for s in sections}
    items = []
    for a in assignments:
        s = sec_by_id.get(a.section_id)
        room = rooms.get(a.room)
        ids = s.instructor_ids if s else []
        names = [instructors[i].name for i in ids if i in instructors and instructors[i].name]
        items.append({
            "block_id": a.block_id,
            "section_id": a.section_id,
            "course_code": s.code if s else "",
            "course_name": s.name if s else "",
            "block_kind": a.kind,
            "assistant_id": ",".join(s.assistants_for(a.kind)) if s else "",
            "assistant_name": " & ".join(
                (s.lab_assistant_names if a.kind == "lab" else s.assistant_names).get(i, i)
                for i in s.assistants_for(a.kind)
            ) if s else "",
            "room_type": room.type if room else ("online" if s and s.is_virtual else ""),
            "is_online": room.is_virtual if room else bool(s and s.is_virtual),
            "instructor_id": ",".join(ids),
            "instructor_name": " & ".join(names),
            "cohort": s.cohort_key if s else "",
            "dept": s.dept_code if s else "",
            "department": s.department if s else "",
            "section_cap": s.students if s else 0,
            "section_p": s.P if s else 0,
            "day": a.day, "start": a.start, "end": a.end,
            "room": a.room,
            "room_cap": room.cap if room else None,
            "is_lab_room": room.is_lab if room else None,
        })
    missing_blocks = list(missing_blocks or [])
    return {
        "period": period,
        "meta": {"n_assignments": len(items), "n_sections": len(sections),
                 "n_required_blocks": len(items) + len(missing_blocks),
                 "n_missing_blocks": len(missing_blocks),
                 "is_complete": not missing_blocks},
        "assignments": items,
        "missing_blocks": missing_blocks,
        "unmet_soft": unmet_soft or [],
        "conflicts": conflicts or [],
    }


def load_ref_schedule(data: dict) -> dict:
    """Parse a schedule_*.json dict into {block_id: (day, start, room)}.
    Entries without a 'block_id' key are skipped for backward compatibility."""
    ref = {}
    for item in (data or {}).get("assignments", []):
        bid = item.get("block_id")
        if bid:
            ref[bid] = (item["day"], int(item["start"]), item["room"])
    return ref


def write_schedule_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_csv(path: str, payload: dict) -> None:
    # utf-8-sig: BOM lets Excel (notably on macOS) detect UTF-8 so Turkish
    # characters (ş, ğ, ü, …) render correctly instead of mojibake.
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for item in payload["assignments"]:
            w.writerow(item)


def write_room_reservations_csv(path: str | Path, payload: dict) -> None:
    """Write physical schedule assignments as a reusable reservation CSV."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=ROOM_RESERVATION_FIELDS)
        writer.writeheader()
        for item in payload.get("assignments", []):
            if item.get("is_online") or str(item.get("room_type", "")).casefold() == "online":
                continue
            room = str(item.get("room", "")).strip()
            if not room:
                continue
            writer.writerow({
                "Room": room,
                "Dept": item.get("department") or item.get("dept", ""),
                "Day": item.get("day", ""),
                "Start": f"{int(item['start']):02}:00",
                "End": f"{int(item['end']):02}:00",
            })


def write_schedule_outputs(
    out_dir: str | Path,
    payload: dict,
    period: str | None = None,
    generated_at: datetime | None = None,
    include_period: bool = True,
) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = (generated_at or datetime.now()).strftime("%Y%m%d_%H%M%S")
    suffix = period or payload.get("period")
    complete = bool(payload.get("meta", {}).get("is_complete", True))
    prefix = "schedule" if complete else "schedule.draft"
    stem = f"{prefix}_{suffix}_{stamp}" if include_period and suffix else f"{prefix}_{stamp}"
    paths = {
        "json": out / f"{stem}.json",
        "csv": out / f"{stem}.csv",
        # The latest generated physical schedule is directly usable as the
        # next run's room_reservations.csv input.
        "room_reservations": out / "room_reservations.csv",
    }
    write_schedule_json(str(paths["json"]), payload)
    write_csv(str(paths["csv"]), payload)
    if not complete:
        paths["unplaced_blocks"] = out / f"{stem}.unplaced_blocks.json"
        with open(paths["unplaced_blocks"], "w", encoding="utf-8") as f:
            json.dump(payload.get("missing_blocks", []), f, ensure_ascii=False, indent=2)
    else:
        write_room_reservations_csv(paths["room_reservations"], payload)
    return paths
