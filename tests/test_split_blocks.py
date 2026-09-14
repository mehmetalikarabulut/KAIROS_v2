from timetabling.config import Config
from timetabling.model import Room, Instructor
from timetabling import derive, model_cpsat, validate


def test_single_block_keeps_plain_id():
    bs = derive.blocks_from_tpl("S_01", 2, 0, 0, 2, max_block_len=4)
    assert [b.block_id for b in bs] == ["S_01#T"]   # T<=2 stays one session


def test_theory_is_one_uninterrupted_session():
    assert [b.length for b in derive.blocks_from_tpl("S_01", 3, 0, 0, 3)] == [3]
    assert [b.length for b in derive.blocks_from_tpl("S_01", 4, 0, 0, 4)] == [4]
    bs = derive.blocks_from_tpl("S_01", 5, 0, 0, 5)
    assert [b.length for b in bs] == [5]
    assert [b.block_id for b in bs] == ["S_01#T"]
    assert all(b.kind == "theory" and not b.needs_lab for b in bs)


def test_long_lab_is_uninterrupted_and_marks_lab():
    bs = derive.blocks_from_tpl("S_01", 0, 0, 6, 0, max_block_len=4)
    labs = [b for b in bs if b.needs_lab]
    assert len(bs) == 1 and len(labs) == 1 and [b.length for b in bs] == [6]
    assert all("#L" in b.block_id for b in bs)


def test_long_component_is_not_silently_split_to_fit_the_day():
    cfg = Config()
    rooms = [Room("R1", 50, False, True)]
    instr = {"i1": Instructor("i1", "n", False, "D")}
    from timetabling.model import Section
    s = Section("S_01", "001", "S 201", "n", 2, "D", "Fac", "D-2", ["i1"],
                10, 10, 0, 0, 0, "Course")
    s.blocks = derive.blocks_from_tpl("S_01", 10, 0, 0, 0, cfg.max_block_len)
    assert len(s.blocks) == 1 and s.blocks[0].length == 10
    assert model_cpsat.gen_candidates(s.blocks[0], s, list(instr.values()), rooms, cfg) == []
