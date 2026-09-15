import json
import os
import sys
from datetime import datetime
from timetabling.model import Section, Block, Room, Instructor, Assignment
from timetabling import export


def test_build_schedule_dict_schema(tmp_path):
    s = Section("ADA 403_01", "001", "ADA 403", "EDA", 4, "ADA", "Fac", "ADA-4",
                ["i1"], 24, 3, 0, 0, 3, "Course")
    s.blocks = [Block("ADA 403_01#T", "ADA 403_01", "theory", 3, False)]
    rooms = {"G005": Room("G005", 60, False, True)}
    instr = {"i1": Instructor("i1", "Instructor A", True, "ADA")}
    a = [Assignment("ADA 403_01#T", "ADA 403_01", "theory", "G005", "Fr", 13, 16)]
    payload = export.build_schedule_dict("001", a, [s], rooms, instr)
    assert payload["period"] == "001"
    item = payload["assignments"][0]
    assert item["section_id"] == "ADA 403_01"
    assert item["course_code"] == "ADA 403" and item["course_name"] == "EDA"
    assert item["instructor_name"] == "Instructor A"
    assert item["cohort"] == "ADA-4" and item["dept"] == "ADA"
    assert item["department"] == "Fac" and item["day"] == "Fr"
    assert item["start"] == 13 and item["end"] == 16
    assert item["room"] == "G005" and item["room_cap"] == 60 and item["is_lab_room"] is False

    p = tmp_path / "schedule.json"
    export.write_schedule_json(str(p), payload)
    assert json.loads(p.read_text())["assignments"][0]["section_id"] == "ADA 403_01"


def test_write_schedule_outputs_creates_out_json_and_csv_with_timestamp(tmp_path):
    payload = {"period": "001", "meta": {}, "assignments": [
        {"section_id": "ADA 403_01", "course_code": "ADA 403"}
    ]}

    written = export.write_schedule_outputs(
        tmp_path / "out",
        payload,
        period="001",
        generated_at=datetime(2026, 6, 28, 14, 5, 9),
    )

    assert written["json"] == tmp_path / "out" / "schedule_001_20260628_140509.json"
    assert written["csv"] == tmp_path / "out" / "schedule_001_20260628_140509.csv"
    assert written["room_reservations"] == tmp_path / "out" / "room_reservations.csv"
    assert json.loads(written["json"].read_text())["assignments"][0]["section_id"] == "ADA 403_01"
    assert written["csv"].read_text(encoding="utf-8-sig").startswith("section_id,course_code")


def test_room_reservations_export_contains_only_physical_assignments(tmp_path):
    payload = {"assignments": [
        {"room": "R1", "department": "Engineering", "day": "Mo", "start": 9, "end": 11},
        {"room": "Online", "room_type": "online", "day": "Mo", "start": 11, "end": 12},
    ]}
    path = tmp_path / "room_reservations.csv"
    export.write_room_reservations_csv(path, payload)
    assert path.read_text(encoding="utf-8-sig").splitlines() == [
        "Room,Dept,Day,Start,End", "R1,Engineering,Mo,09:00,11:00",
    ]


def test_private_schedule_output_includes_latest_room_reservations(tmp_path):
    payload = {"period": "Example", "meta": {}, "assignments": [
        {"room": "ROOM-01", "department": "Department A", "day": "Mo", "start": 9, "end": 11},
    ]}

    written = export.write_schedule_outputs(tmp_path, payload)

    assert written["room_reservations"] == tmp_path / "room_reservations.csv"
    assert written["room_reservations"].read_text(encoding="utf-8-sig").splitlines() == [
        "Room,Dept,Day,Start,End", "ROOM-01,Department A,Mo,09:00,11:00",
    ]


def test_private_schedule_output_dir_is_outside_source_checkout():
    expected = (
        export.Path(r"D:\Projects\kairos_v2_schedules")
        if os.name == "nt"
        else export.Path.home() / "Projects" / "kairos_v2_schedules"
        if sys.platform == "darwin"
        else export.Path.home() / "kairos_v2_schedules"
    )
    assert export.SCHEDULE_OUTPUT_DIR == expected
    assert export.SCHEDULE_OUTPUT_DIR.name == "kairos_v2_schedules"


def test_write_schedule_outputs_can_omit_period_from_filename(tmp_path):
    payload = {"period": "001", "meta": {}, "assignments": []}

    written = export.write_schedule_outputs(
        tmp_path / "out",
        payload,
        period="001",
        generated_at=datetime(2026, 6, 28, 14, 5, 9),
        include_period=False,
    )

    assert written["json"] == tmp_path / "out" / "schedule_20260628_140509.json"
    assert written["csv"] == tmp_path / "out" / "schedule_20260628_140509.csv"


def test_build_schedule_dict_includes_block_id():
    s = Section("ADA 403_01", "001", "ADA 403", "EDA", 4, "ADA", "Fac", "ADA-4",
                ["i1"], 24, 3, 0, 0, 3, "Course")
    s.blocks = [Block("ADA 403_01#T", "ADA 403_01", "theory", 3, False)]
    rooms = {"G005": Room("G005", 60, False, True)}
    instr = {"i1": Instructor("i1", "Test", True, "ADA")}
    a = [Assignment("ADA 403_01#T", "ADA 403_01", "theory", "G005", "Fr", 13, 16)]
    payload = export.build_schedule_dict("001", a, [s], rooms, instr)
    assert payload["assignments"][0]["block_id"] == "ADA 403_01#T"


def test_load_ref_schedule_extracts_block_day_start_room():
    data = {
        "assignments": [
            {"block_id": "ADA 403_01#T", "day": "Fr", "start": 13, "room": "G005"},
            {"block_id": "ADA 403_01#L", "day": "Mo", "start": 9,  "room": "PC-L1"},
        ]
    }
    ref = export.load_ref_schedule(data)
    assert ref["ADA 403_01#T"] == ("Fr", 13, "G005")
    assert ref["ADA 403_01#L"] == ("Mo", 9,  "PC-L1")


def test_load_ref_schedule_skips_entries_without_block_id():
    data = {
        "assignments": [
            {"section_id": "ADA 403_01", "day": "Fr", "start": 13, "room": "G005"},
        ]
    }
    assert export.load_ref_schedule(data) == {}


def test_load_ref_schedule_empty_input():
    assert export.load_ref_schedule({}) == {}
    assert export.load_ref_schedule({"assignments": []}) == {}
