from dataclasses import replace
import pytest

from timetabling.config import Config
from timetabling.ui_input import build_rooms_from_ui, build_sections_from_courselist, build_instructors_from_courselist
from timetabling.room_reservations import parse_room_reservations, apply_room_reservations
from timetabling.model_cpsat import gen_candidates
from timetabling.pipeline import run_pipeline
from timetabling.validate import validate

HEAD = ["Room", "Dept", "Day", "Start", "End"]


def inputs(dept="Other Department"):
    cfg = Config(solve_time_limit_s=2, repair_time_limit_s=2, soft_polish_budget_s=.05)
    rows = [{"Course Code": "X 101", "Course Name": "Example", "Section No": "1", "Dept": dept,
             "Instructor Name": "Instructor A", "Part-time": "yes", "T": "2", "P": "0", "L": "0", "Section Capacity": "10"}]
    sections = build_sections_from_courselist(rows, "1", cfg)[0]
    rooms = build_rooms_from_ui([{"Room": "A", "Capacity": "30", "Type": "classroom"}], cfg)
    reservations = parse_room_reservations([HEAD, ["A", "Industrial Engineering", "Monday", "11:00", "13:00"]])
    return sections, apply_room_reservations(rooms, reservations), build_instructors_from_courselist(rows), cfg


def test_blank_room_ignored_and_multiple_intervals():
    result = parse_room_reservations([HEAD, ["", "", "bad", "bad", ""],
        ["A", "", "Pazartesi", "11:30", "13:00:00"], ["A", "", "Tu", "9", "10"]])
    assert len(result) == 2
    assert result[0]["Day"] == "Mo"
    assert result[0]["Start"] == "11:30"


@pytest.mark.parametrize("day,start,end", [("Wrong", "11", "13"), ("Mo", "13", "11"),
    ("Mo", "11", "11"), ("Mo", "11:60", "13"), ("Mo", "23", "24:01"), ("Mo", "", "13")])
def test_bad_reservation_rejected(day, start, end):
    with pytest.raises(ValueError, match="Row 2"):
        parse_room_reservations([HEAD, ["A", "", day, start, end]])


def test_unknown_and_online_rooms_rejected():
    _, rooms, _, _ = inputs()
    for room in ("Missing", "Online"):
        with pytest.raises(ValueError):
            apply_room_reservations(rooms, parse_room_reservations([HEAD, [room, "", "Mo", "11", "13"]]))


def test_partial_hour_overlap():
    sections, rooms, ins, cfg = inputs()
    rooms = {k: replace(r, reservations=frozenset()) for k, r in rooms.items()}
    rooms = apply_room_reservations(rooms, parse_room_reservations([HEAD, ["A", "", "Mo", "11:30", "12:30"]]))
    sec = sections[0]
    candidates = gen_candidates(sec.blocks[0], sec, list(ins.values()), list(rooms.values()), cfg)
    starts = {c.start for c in candidates if c.day == "Mo"}
    assert 9 in starts and 13 in starts
    assert not starts & {10, 11, 12}


@pytest.mark.parametrize("lang", ["en", "tr"])
def test_reservation_ui_clear_and_upload_errors(lang):
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import streamlit as st
from views.classrooms import _reservation_inputs
st.session_state.setdefault("room_reservations", [{"Room":"A", "Dept":"", "Day":"Mo", "Start":"11:00", "End":"13:00"}])
_reservation_inputs(LANG, [{"Room":"A", "Capacity":"30", "Type":"classroom"}])
'''.replace('LANG', repr(lang))).run()
    assert not app.exception
    app.button(key="reservation_clear").click().run()
    assert not app.session_state["room_reservations"]
    next(b for b in app.button if b.key != "reservation_clear").click().run()
    assert app.session_state["room_reservation_error"]
    app.button(key="reservation_clear").click().run()
    assert not app.exception
    assert "room_reservation_error" not in app.session_state


@pytest.mark.parametrize("solver", ["cpsat", "repair", "decompose"])
@pytest.mark.parametrize("dept", ["Industrial Engineering", "Other Department"])
def test_same_room_never_shared_between_courses(solver, dept):
    sections, rooms, ins, cfg = inputs()
    other_rows = [{"Course Code": "Y 101", "Course Name": "Second", "Section No": "1", "Dept": dept,
        "Instructor Name": "Instructor B", "Part-time": "yes", "T": "2", "P": "0", "L": "0", "Section Capacity": "10"}]
    sections += build_sections_from_courselist(other_rows, "1", cfg)[0]
    ins.update(build_instructors_from_courselist(other_rows))
    result = run_pipeline("1", sections, rooms, ins, cfg, solver)
    assert len(result.assignments) == 2 and not result.violations
    occupied = set()
    for a in result.assignments:
        slots = {(a.room, a.day, h) for h in range(a.start, a.end)}
        assert not occupied & slots
        occupied |= slots
        assert not (a.room == "A" and a.day == "Mo" and a.start < 13 and a.end > 11)


@pytest.mark.parametrize("dept", ["Industrial Engineering", "Other Department"])
def test_boundaries_and_all_departments(dept):
    sections, rooms, ins, cfg = inputs(dept)
    sec = sections[0]
    candidates = gen_candidates(sec.blocks[0], sec, list(ins.values()), list(rooms.values()), cfg)
    starts = {c.start for c in candidates if c.day == "Mo"}
    assert 9 in starts and 13 in starts
    assert not starts & {10, 11, 12}
    assert any(c.day == "Tu" and c.start == 11 for c in candidates)


@pytest.mark.parametrize("solver", ["cpsat", "repair", "decompose"])
def test_solver_and_independent_validator(solver):
    sections, rooms, ins, cfg = inputs()
    sections[0].fixed_day, sections[0].fixed_start = "Mo", 13
    result = run_pipeline("1", sections, rooms, ins, cfg, solver)
    assert len(result.assignments) == 1 and not result.violations
    a = result.assignments[0]
    assert (a.day, a.start) == ("Mo", 13)
    bad = replace(a, start=11, end=13)
    assert any(v.kind == "room_reserved" for v in validate([bad], sections, rooms, ins, cfg))
    sections[0].fixed_start = 11
    blocked = run_pipeline("1", sections, rooms, ins, cfg, solver)
    assert not blocked.assignments
