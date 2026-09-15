from __future__ import annotations
from typing import List, Dict
from collections import defaultdict
from dataclasses import replace

from .config import Config
from .model import Assignment, Section, Room, Instructor, Violation, virtual_supply


def validate(assignments: List[Assignment], sections: List[Section],
             rooms: Dict[str, Room], instructors: Dict[str, Instructor],
             cfg: Config, check_placement: bool = True) -> List[Violation]:
    """Re-derive every hard-constraint violation independently of the solver.
    Empty list = feasible. Set check_placement=False for Mode-B benchmarking of
    an existing schedule whose session structure differs from our derived blocks."""
    viol: List[Violation] = []
    rooms = dict(rooms)
    supply = virtual_supply(rooms.values(), cfg.online_room)
    rooms.setdefault(supply.room, supply)
    sec_by_id = {s.section_id: s for s in sections}

    if check_placement:
        placed = defaultdict(int)
        for a in assignments:
            placed[a.block_id] += 1
        for s in sections:
            for b in s.blocks:
                if placed.get(b.block_id, 0) != 1:
                    viol.append(Violation("placement",
                                f"{b.block_id} placed {placed.get(b.block_id, 0)} times (expected 1)"))
    block_by_id = {b.block_id: b for s in sections for b in s.blocks}
    has_lab_blocks = {s.section_id: any(b.needs_lab for b in s.blocks) for s in sections}

    room_occ = defaultdict(list)
    instr_occ = defaultdict(list)
    section_occ = defaultdict(list)

    for a in assignments:
        s = sec_by_id.get(a.section_id)
        if s is None:
            continue
        room = rooms.get(a.room)
        if room and any(day == a.day and a.start * 60 < end and a.end * 60 > start
                        for day, start, end in room.reservations):
            viol.append(Violation("room_reserved", f"{a.block_id}: {a.room} overlaps a room reservation"))
        is_virt = (room is not None and room.is_virtual) or (a.room == cfg.online_room and s.is_virtual)
        if a.kind == "lab" and not is_virt and s.lab_room and a.room != s.lab_room:
            viol.append(Violation("lab_room",
                        f"{a.block_id} lab not in pinned {s.lab_room} (got {a.room})"))
        block = block_by_id.get(a.block_id)
        from .model_cpsat import feasible_rooms_for
        from .model import Block
        block = block or Block(a.block_id, a.section_id, a.kind, a.end-a.start, a.kind == "lab")
        if not any(r.room == a.room for r in feasible_rooms_for(block, s, list(rooms.values()),
                   replace(cfg, max_rooms_per_block=len(rooms)+1))):
            viol.append(Violation("room_type", f"{a.block_id}: incompatible room {a.room}"))
        if s.fixed_day and s.blocks and a.block_id == s.blocks[0].block_id \
                and (a.day != s.fixed_day or a.start != s.fixed_start):
            viol.append(Violation("fixed",
                        f"{a.block_id} not at fixed {s.fixed_day} {s.fixed_start}:00 "
                        f"(got {a.day} {a.start})"))
        end_cap = cfg.undergrad_end if s.level <= 4 else cfg.grad_end
        if a.end > end_cap:
            viol.append(Violation("window",
                        f"{a.block_id} ends {a.end} > allowed {end_cap} (level {s.level})"))
        ins_list = [instructors.get(i, Instructor("", "", False, "")) for i in s.instructor_ids]
        closed = cfg.closed_hours(any(ins.is_staff for ins in ins_list))
        for hh in range(a.start, a.end):
            if (a.day, hh) in closed:
                viol.append(Violation("blackout", f"{a.block_id} covers blackout {a.day} {hh}:00"))
                break
        if cfg.instr_unavailable:
            hit = next(((iid, hh) for iid in s.instructor_ids
                        for hh in range(a.start, a.end)
                        if (iid, a.day, hh) in cfg.instr_unavailable), None)
            if hit:
                viol.append(Violation("instructor_unavailable",
                            f"{a.block_id}: {hit[0]} unavailable {a.day} {hit[1]}:00"))
        for aid in s.assistants_for(a.kind):
            if any((aid, a.day, h) in cfg.assistant_unavailable for h in range(a.start, a.end)):
                viol.append(Violation("assistant_unavailable", f"{a.block_id}: {aid} unavailable"))
        for hh in range(a.start, a.end):
            if not is_virt:
                room_occ[(a.room, a.day, hh)].append(a.block_id)
            for iid in s.human_ids(a.kind):
                instr_occ[(iid, a.day, hh)].append(a.block_id)
            section_occ[(a.section_id, a.day, hh)].append(a.block_id)

    # Theory → Practice is a hard sequence. Lab sessions are assistant-led and
    # intentionally independent, so they are not included in this check.
    assignment_by_block = {a.block_id: a for a in assignments}
    for s in sections:
        components = [b for b in s.blocks if b.kind in ("theory", "practice")]
        for previous, current in zip(components, components[1:]):
            left, right = assignment_by_block.get(previous.block_id), assignment_by_block.get(current.block_id)
            if left and right and (left.day != right.day or left.end != right.start):
                viol.append(Violation("component_sequence",
                            f"{s.section_id}: {previous.kind} must end where {current.kind} begins"))

    for (room, day, hh), bids in room_occ.items():
        if len(bids) > 1:
            viol.append(Violation("room", f"room {room} double-booked {day} {hh}:00 by {bids}"))
    for (iid, day, hh), bids in instr_occ.items():
        if len(set(b.split('#')[0] for b in bids)) > 1:
            viol.append(Violation("instructor", f"human resource {iid} double-booked {day} {hh}:00 by {bids}"))
    for (sid, day, hh), bids in section_occ.items():
        if len(set(bids)) > 1:
            viol.append(Violation("self", f"section {sid} self-overlap {day} {hh}:00 by {bids}"))

    return viol
