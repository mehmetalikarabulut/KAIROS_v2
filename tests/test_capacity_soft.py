from timetabling.config import Config
from timetabling.model import Room
from timetabling.model_cpsat import feasible_rooms_for
from timetabling.pipeline import run_pipeline
from timetabling.ui_input import build_instructors_from_courselist, build_sections_from_courselist
from timetabling.validate import validate


def _section(required=45):
    row = {"Course Code": "CMPE 101", "Course Name": "Intro", "Dept": "Engineering",
           "Section No": "1", "Instructor Name": "Instructor A", "T": "1", "P": "0", "L": "0",
           "Section Capacity": str(required), "Room Type": "classroom"}
    return row, build_sections_from_courselist([row], "001", Config())[0][0]


def test_sufficient_capacity_is_preferred_but_undersized_rooms_remain_candidates():
    _, section = _section()
    rooms = [Room("Small", 40, False, True), Room("Large", 50, False, True)]
    candidates = feasible_rooms_for(section.blocks[0], section, rooms, Config(max_rooms_per_block=2))
    assert [room.room for room in candidates] == ["Large", "Small"]


def test_undersized_room_solves_and_is_reported_as_soft_shortfall():
    row, section = _section()
    rooms = {"Small": Room("Small", 40, False, True)}
    instructors = build_instructors_from_courselist([row])
    result = run_pipeline("001", [section], rooms, instructors, Config(solve_time_limit_s=5), solver="cpsat")
    assert len(result.assignments) == 1
    assert validate(result.assignments, [section], rooms, instructors, Config()) == []
    assert result.schedule["unmet_soft"] == [{
        "kind": "capacity_shortfall", "block_id": "CMPE 101_1#T", "section_id": "CMPE 101_1",
        "required_seating": 45, "room": "Small", "room_capacity": 40, "shortfall": 5,
    }]
