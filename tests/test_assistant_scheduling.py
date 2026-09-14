from dataclasses import replace

import pytest

from timetabling.config import Config
from timetabling.csv_import import parse_courselist, ok_rows, normalize_room_type
from timetabling.derive import blocks_from_tpl
from timetabling.ui_input import build_sections_from_courselist, build_rooms_from_ui, build_instructors_from_courselist
from timetabling.model import Assignment, Candidate
from timetabling.model_cpsat import gen_candidates, feasible_rooms_for, split_roomable
from timetabling.pipeline import run_pipeline
from timetabling.repair import State, assistant_preference_counts
from timetabling.soft_search import _global_terms, _local_terms, try_relocate
from timetabling.settings import default_settings, build_config, profile_to_json, profile_from_json
from timetabling.validate import validate


def row(code="X 101", **kw):
    return {"Course Code": code, "Course Name": code, "Section No": "1",
            "Dept": code[0], "T": "2", "P": "1", "L": "2",
            "Instructor Name": "Prof " + code, "Instructor Email": code[0] + "@example.test",
            "Assistant Name": "Assistant A", "Assistant Email": "a@example.test",
            "Section Capacity": "20", "Room Type": "electronics_lab", **kw}


def setup(rows, cfg=None):
    cfg = cfg or Config(solve_time_limit_s=2, repair_time_limit_s=2, soft_polish_budget_s=.05)
    sections = build_sections_from_courselist(rows, "2026", cfg)[0]
    rooms = build_rooms_from_ui([
        {"Room": "R1", "Capacity": "40", "Type": "classroom"},
        {"Room": "R2", "Capacity": "40", "Type": "classroom"},
        {"Room": "PC", "Capacity": "40", "Type": "pc_lab"},
        {"Room": "EE", "Capacity": "40", "Type": "electronics_lab"},
        {"Room": "A-VIRTUAL", "Capacity": "1", "Type": "online"},
    ], cfg)
    return sections, rooms, build_instructors_from_courselist(rows), cfg


@pytest.mark.parametrize("alias", ["Assistant Name", "Assistant", "Research Assistant", "Teaching Assistant Name", "TA", "Arş. Gör.", "Ars. Gor.", "Araştırma Görevlisi", "Asistan"])
def test_assistant_aliases_and_u(alias):
    parsed = parse_courselist([["Course Code", "Section No", "T", "U", "L", alias, "TA Email", "Section Capacity"],
                              ["X 101", "1", "2", "1", "2", "Ada", "ADA@EXAMPLE.TEST", "20"]])
    r = ok_rows(parsed)[0]
    assert (r["P"], r["Assistant Name"], r["Assistant Email"]) == ("1", "Ada", "ADA@EXAMPLE.TEST")
    assert build_sections_from_courselist([r], "1", Config())[0][0].assistant_ids == ["ada"]


@pytest.mark.parametrize("role", ["Instructor", "Assistant"])
def test_email_columns_never_change_identity(role):
    from timetabling.ui_input import people_for_row

    assert people_for_row({f"{role} Name": " Person A ", f"{role} Email": "old@example.test"}, role) == {"person a": "Person A"}
    assert people_for_row({f"{role} Name": "Person A", f"{role} Email": "different@example.test"}, role) == {"person a": "Person A"}
    assert people_for_row({f"{role} Name": "Person B", f"{role} Email": "old@example.test"}, role) == {"person b": "Person B"}
    assert not people_for_row({f"{role} Email": "old@example.test"}, role)


def test_tpl_distinct_and_split_ids():
    bs = blocks_from_tpl("X_1", 2, 1, 2, 5)
    assert [(b.block_id, b.kind, b.length) for b in bs] == [
        ("X_1#T", "theory", 2), ("X_1#P", "practice", 1), ("X_1#L", "lab", 2)]
    assert [(b.block_id, b.length) for b in blocks_from_tpl("X", 4, 5, 5, 14)] == [
        ("X#T", 4), ("X#P", 5), ("X#L", 5)]


def test_theory_practice_and_lab_are_consecutive_and_lab_uses_pc_without_assistant():
    from timetabling.pipeline import run_pipeline
    from timetabling.model import Room

    course = row() | {"T": "1", "P": "1", "L": "1", "Assistant Name": "", "Room Type": ""}
    sections, _ = build_sections_from_courselist([course], "001", Config(solve_time_limit_s=5))
    instructors = build_instructors_from_courselist([course])
    rooms = {
        "Classroom": Room("Classroom", 40, False, True, type="classroom"),
        "PC Lab": Room("PC Lab", 40, True, True, type="pc_lab"),
    }
    result = run_pipeline("001", sections, rooms, instructors, Config(solve_time_limit_s=5), solver="cpsat")
    by_kind = {a.kind: a for a in result.assignments}
    assert by_kind["theory"].day == by_kind["practice"].day == by_kind["lab"].day
    assert by_kind["theory"].end == by_kind["practice"].start
    assert by_kind["practice"].end == by_kind["lab"].start
    assert by_kind["lab"].room == "PC Lab"


def test_assistant_only_pl_and_joint_availability():
    secs, rooms, ins, cfg = setup([row()])
    s = secs[0]
    cfg.assistant_unavailable = frozenset(("assistant a", "Mo", h) for h in range(9, 21))
    cfg.instr_unavailable = frozenset((s.instructor_ids[0], "Tu", h) for h in range(9, 21))
    for b in s.blocks:
        candidates = gen_candidates(b, s, list(ins.values()), list(rooms.values()), cfg)
        days = {c.day for c in candidates}
        assert "Tu" not in days
        assert ("Mo" in days) == (b.kind == "theory")


@pytest.mark.parametrize("solver", ["cpsat", "repair", "decompose"])
def test_shared_assistant_and_cross_role_no_overlap(solver):
    rows = [row("X 101", T="0", P="2", L="0"),
            row("Y 101", T="0", P="0", L="2"),
            row("Z 101", T="2", P="0", L="0", **{"Instructor Name": "Assistant A", "Instructor Email": "A@EXAMPLE.TEST", "Room Type": "classroom"})]
    secs, rooms, ins, cfg = setup(rows)
    cfg.assistant_unavailable = frozenset(("assistant a", d, h) for d in cfg.days()[1:] for h in range(9, 21))
    result = run_pipeline("1", secs, rooms, ins, cfg, solver)
    assert len(result.assignments) == 3
    assert not result.violations
    human_slots = set()
    for a in result.assignments:
        if a.kind != "theory":
            assert a.day == "Mo"
        slots = {(a.day, h) for h in range(a.start, a.end)}
        assert not human_slots & slots
        human_slots |= slots


def test_multiple_assistants_all_required_and_deduplicated():
    secs, rooms, ins, cfg = setup([row(**{"Assistant Name": "One, Two, One", "Assistant Email": "one@x, two@x, one@x"})])
    s = secs[0]
    assert s.assistant_ids == ["one", "two"]
    cfg.assistant_unavailable = frozenset({("one", "Mo", 9), ("two", "Mo", 10)})
    cs = gen_candidates(s.blocks[1], s, list(ins.values()), list(rooms.values()), cfg)
    assert not any(c.day == "Mo" and c.start in (9, 10) for c in cs)


@pytest.mark.parametrize("solver", ["cpsat", "repair"])
def test_prefer_avoid_soft(solver):
    secs, rooms, ins, cfg = setup([row(T="0", P="1", L="0", **{"Room Type": "classroom"})])
    cfg.assistant_preferred = frozenset({("assistant a", "Mo", 9)})
    cfg.assistant_prefer_ids = frozenset({"assistant a"})
    cfg.assistant_avoid = frozenset(("assistant a", d, h) for d in cfg.days() for h in range(10,18))
    result = run_pipeline("1", secs, rooms, ins, cfg, solver)
    assert (result.assignments[0].day, result.assignments[0].start) == ("Mo", 9)
    cfg.assistant_avoid = frozenset(("assistant a", d, h) for d in cfg.days() for h in range(9,18))
    result = run_pipeline("1", secs, rooms, ins, cfg, solver)
    assert len(result.assignments) == 1 and not result.violations


@pytest.mark.parametrize("alias,canonical", [("normal","classroom"), ("pc","pc_lab"), ("lab","electronics_lab"), ("studio","online"), ("sınıf","classroom"), ("çevrimiçi","online"), ("bilgisayar laboratuvarı","pc_lab"), ("elektronik laboratuvarı","electronics_lab")])
def test_room_migration(alias, canonical):
    assert normalize_room_type(alias) == canonical


@pytest.mark.parametrize("rt", ["classroom", "pc_lab", "electronics_lab"])
def test_exact_room_type_and_mixed_theory(rt):
    secs, rooms, _, cfg = setup([row(**{"Room Type":rt})])
    s=secs[0]
    for b in s.blocks:
        expected = {"pc_lab"} if b.kind == "lab" else {"classroom"}
        assert {r.type for r in feasible_rooms_for(b, s, list(rooms.values()), cfg)} == expected


@pytest.mark.parametrize("solver", ["cpsat", "repair", "decompose"])
def test_online_unlimited_occupancy_and_export(solver):
    rows=[row(c,T="1",P="0",L="0", **{"Room Type":"studio", "Fixed":"Mo 9"}) for c in ("X 101","Y 101")]
    secs, rooms, ins, cfg=setup(rows)
    cfg.w_building_change=10
    result=run_pipeline("1",secs,rooms,ins,cfg,solver)
    assert len(result.assignments)==2 and not result.violations
    assert {a.room for a in result.assignments}=={"A-VIRTUAL"}
    assert all(a["is_online"] and a["room_type"]=="online" and not a["assistant_id"] for a in result.schedule["assignments"])


@pytest.mark.parametrize("role", ["Instructor Name", "Assistant Name"])
def test_online_still_has_human_conflicts(role):
    rows=[row(c,T="0",P="1",L="0", **{"Room Type":"online",role:"Shared Person"}) for c in ("X 101","Y 101")]
    secs,rooms,ins,cfg=setup(rows)
    result=run_pipeline("1",secs,rooms,ins,cfg)
    a,b=result.assignments
    assert (a.day,a.start)!=(b.day,b.start)
    wrong=[a,replace(b,day=a.day,start=a.start,end=a.end)]
    assert any(v.kind=="instructor" for v in validate(wrong,secs,rooms,ins,cfg))


@pytest.mark.parametrize("solver", ["cpsat", "repair", "decompose"])
@pytest.mark.parametrize("name", ["", "   ", None])
def test_blank_assistant_name_schedules_pl_without_assistant(solver, name):
    from timetabling.ui_input import build_assistants_from_courselist

    rows = [row(**{"Assistant Name": name})]  # An old email must not assign an assistant.
    secs, rooms, ins, cfg = setup(rows)
    assert not secs[0].assistant_ids
    assert not build_assistants_from_courselist(rows)
    cfg.assistant_unavailable = frozenset(
        ("assistant a", d, h) for d in cfg.days() for h in range(9, 21))
    result = run_pipeline("1", secs, rooms, ins, cfg, solver)
    assert not result.violations
    assert sum(a.end - a.start for a in result.assignments) == 5
    assert {a.kind for a in result.assignments} == {"theory", "practice", "lab"}
    assert all(not a["assistant_id"] for a in result.schedule["assignments"])


def test_old_csv_no_assistant_and_profile_roundtrip():
    r=row(); r.pop("Assistant Name"); r.pop("Assistant Email")
    parsed=ok_rows(parse_courselist([list(r), list(r.values())]))
    secs,rooms,ins,cfg=setup(parsed)
    assert not secs[0].assistant_ids
    assert not run_pipeline("1",secs,rooms,ins,cfg).violations
    settings=default_settings()
    payload=profile_to_json(settings,{},assistant_availability={"a@x":[["Tu",9]]},assistant_availability_avoid={"a@x":[["Mo",10]]},assistant_availability_prefer={"a@x":[["Mo",9]]})
    restored,*_=profile_from_json(payload)
    config=build_config(restored,{},1)
    assert ("a@x","Tu",9) in config.assistant_unavailable
    assert ("a@x","Mo",10) in config.assistant_avoid
    assert config.assistant_prefer_ids==frozenset({"a@x"})


def test_assistant_diagnostic_and_soft_delta():
    secs,rooms,ins,cfg=setup([row(T="0",P="1",L="0")])
    s=secs[0]; b=s.blocks[0]
    cfg.assistant_unavailable=frozenset(("assistant a",d,h) for d in cfg.days() for h in range(9,21))
    good,bad=split_roomable(secs,list(rooms.values()),cfg,ins)
    assert not good and "Assistant A" in bad[0]["issues"][0][1]
    state=State({b.block_id:s},{s.section_id:s.instructor_ids},set())
    c=Candidate(b.block_id,"EE","Mo",9,1)
    state.occupy(b.block_id,c)
    cfg.assistant_avoid=frozenset({("assistant a","Mo",9)})
    assert assistant_preference_counts(c,s,cfg)==(1,0)
    global_terms=_global_terms(state,cfg)
    local_terms=_local_terms(state,{s.cohort_key},s.human_ids(b.kind),{"EE"},{b.block_id},cfg)
    assert global_terms==local_terms
    assert global_terms["instr_avoid_viol"]==1


@pytest.mark.parametrize("lang", ["en", "tr"])
def test_settings_role_grids_are_independent(lang):
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import streamlit as st
from timetabling.settings import default_settings
from views.settings import _availability
st.session_state.setdefault("settings", default_settings())
st.session_state["courses"] = [{"Instructor Name":"Ada", "Instructor Email":"ada@x", "Assistant Name":"Ada", "Assistant Email":"ada@x"}]
_availability(LANG, "Instructor")
_availability(LANG, "Assistant")
'''.replace('LANG', repr(lang))).run()
    assert not app.exception
    app.checkbox(key="assistant_av_u_ada_Mo_9_0").check().run()
    assert not app.exception
    assert app.session_state["assistant_availability"]["ada"] == [["Mo", 9]]
    assert not app.session_state["availability"]


def test_exports_and_grid_use_block_kind_not_section_p():
    from timetabling.ui_style import week_grid_html
    from timetabling.pdf_export import _block_tag
    secs,rooms,ins,cfg=setup([row()])
    result=run_pipeline("1",secs,rooms,ins,cfg)
    items={a["block_kind"]:a for a in result.schedule["assignments"]}
    assert not items["theory"]["assistant_name"]
    assert items["practice"]["assistant_name"] == "Assistant A"
    assert _block_tag(items["theory"]) == ""
    assert _block_tag(items["practice"]) == "PRAT"
    html=week_grid_html({"assignments":[items["practice"]]}, lang="tr")
    assert "Uygulama" in html and "Assistant A" in html


def test_repair_soft_move_cannot_double_book_assistant():
    import random
    secs,rooms,ins,cfg=setup([row("X 101",T="0",P="1",L="0"),row("Y 101",T="0",P="1",L="0")])
    a,b=secs
    ba,bb=a.blocks[0].block_id,b.blocks[0].block_id
    state=State({ba:a,bb:b},{s.section_id:s.instructor_ids for s in secs},set())
    ca=Candidate(ba,"R1","Mo",9,1)
    cb=Candidate(bb,"R2","Mo",10,1)
    bad=replace(cb,start=9)
    state.occupy(ba,ca); state.occupy(bb,cb)
    assert try_relocate(state,{ba:[ca],bb:[cb,bad]},bb,random.Random(0),lambda *args:(0,{})) is None
    assert state.placed=={ba:ca,bb:cb}


def test_physical_room_named_online_is_not_replaced_or_exempted():
    from timetabling.model import Room
    rooms=build_rooms_from_ui([{"Room":"Online","Capacity":"20","Type":"classroom"}],Config())
    assert rooms["Online"].is_physical
    assert len(rooms)==2
    secs,_,ins,cfg=setup([row("X 101",T="1",P="0",L="0",**{"Room Type":"classroom"}),
                         row("Y 101",T="1",P="0",L="0",**{"Room Type":"classroom"})])
    result=run_pipeline("1",secs,rooms,ins,cfg)
    assert len(result.assignments)==2
    a,b=result.assignments
    assert a.room==b.room=="Online" and (a.day,a.start)!=(b.day,b.start)


def test_online_without_inventory_and_normalized_name_cross_role():
    rows=[row("X 101",T="1",P="0",L="0",**{"Room Type":"online","Instructor Name":"  Person   A ","Instructor Email":""}),
          row("Y 101",T="0",P="1",L="0",**{"Room Type":"online","Assistant Name":"person a","Assistant Email":""})]
    secs,_,ins,cfg=setup(rows)
    assert secs[0].instructor_ids==secs[1].assistant_ids==["person a"]
    result=run_pipeline("1",secs,{},ins,cfg)
    assert len(result.assignments)==2 and not result.violations
    assert all(a["is_online"] for a in result.schedule["assignments"])
