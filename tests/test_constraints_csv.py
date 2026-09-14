from timetabling.constraints_csv import export_constraints, merge_constraints, parse_constraints_csv


def test_round_trip_both_roles_and_ranges():
    source = {"availability": {"Instructor A": [["Mo", 9], ["Mo", 10]]},
              "availability_avoid": {}, "availability_prefer": {"Instructor A": [["Tu", 14]]},
              "assistant_availability": {"Assistant A": [["We", 11]]},
              "assistant_availability_avoid": {}, "assistant_availability_prefer": {}}
    parsed = parse_constraints_csv(export_constraints(source).decode("utf-8-sig"))
    assert parsed["availability"]["instructor a"] == [["Mo", 9], ["Mo", 10]]
    assert parsed["assistant_availability"]["assistant a"] == [["We", 11]]


def test_invalid_is_rejected_and_merge_or_replace_is_explicit():
    good = "Role,Name,Constraint,Day,Start,End\nInstructor, A (S) ,Unavailable,Mo,09:00,11:00\n"
    incoming = parse_constraints_csv(good)
    existing = {key: {} for key in incoming}
    existing["availability"] = {"existing": [["Fr", 9]]}
    assert set(merge_constraints(existing, incoming)["availability"]) == {"existing", "a"}
    assert set(merge_constraints(existing, incoming, replace_all=True)["availability"]) == {"a"}
    try:
        parse_constraints_csv("Role,Name,Constraint,Day,Start,End\nInstructor,A,Unavailable,Mo,09:30,10:00\n")
    except ValueError as exc:
        assert "whole-hour" in str(exc)
    else:
        assert False
