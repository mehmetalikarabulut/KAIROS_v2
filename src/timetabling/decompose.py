from __future__ import annotations
from typing import List, Dict, Tuple, Callable
from collections import defaultdict

from .config import Config
from .model import Section, Room, Instructor, Assignment, virtual_supply
from .model_cpsat import build_and_solve


def solve_decomposed(sections: List[Section], rooms: List[Room],
                     instructors: Dict[str, Instructor], cfg: Config,
                     group_key: Callable[[Section], str] = lambda s: s.department
                     ) -> Tuple[List[Assignment], Dict]:
    """Solve sections group-by-group (default: by department), largest group first,
    reserving each group's used (room, day, hour) slots for later groups so the
    shared room pool stays conflict-free across the partition."""
    groups: Dict[str, List[Section]] = defaultdict(list)
    for s in sections:
        groups[group_key(s)].append(s)
    order = sorted(groups, key=lambda g: -len(groups[g]))

    reserved: set = set()
    reserved_instr: set = set()
    sec_by_id = {s.section_id: s for s in sections}
    virtual = {r.room for r in rooms if r.is_virtual} | {virtual_supply(rooms, cfg.online_room).room}
    all_assigns: List[Assignment] = []
    per_group = []
    for g in order:
        a, st = build_and_solve(groups[g], rooms, instructors, cfg,
                                reserved=reserved, reserved_instr=reserved_instr)
        for x in a:
            for hh in range(x.start, x.end):
                if x.room not in virtual:
                    reserved.add((x.room, x.day, hh))
                for iid in sec_by_id[x.section_id].human_ids(x.kind):
                    reserved_instr.add((iid, x.day, hh))
        all_assigns.extend(a)
        # st always carries status_name/unplaced/wall_time: each group is solved by
        # build_and_solve (never the decomposed path), so these keys are guaranteed.
        per_group.append({"group": g, "n_sections": len(groups[g]),
                          "status": st["status_name"], "unplaced": len(st["unplaced"]),
                          "wall_time": st["wall_time"]})
    stats = {"groups": per_group, "n_groups": len(order),
             "n_assignments": len(all_assigns)}
    return all_assigns, stats
