from fractions import Fraction as F
from conftest import H
from chronus.agent.memory import LongHorizonMemory, Episode, Lesson


def test_unsupported_memory_and_conflict_retained(ledger, task):
    m = LongHorizonMemory(ledger, minimum_support=2)
    a = Lesson("a", task.key, "old", "FACT", ("one", "two"), F(1))
    assert not m.consolidate_memory(a, now=1)
    for id, group, conclusion in [
        ("one", "g1", "old"),
        ("two", "g2", "old"),
        ("three", "g3", "new"),
        ("four", "g4", "new"),
    ]:
        m.record_episode(Episode(id, task.key, H, group, "verifier", True, conclusion), now=2)
    assert m.consolidate_memory(a, now=3)
    b = Lesson("b", task.key, "new", "FACT", ("three", "four"), F(1))
    assert not m.consolidate_memory(b, now=4)
    assert "b" in m.contested and "a" in m.semantic
    assert m.semantic["a"].confidence == F(2, 3)
