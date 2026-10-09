from __future__ import annotations

from pathlib import Path

import pytest

from scripts import critical_mutation_gate as gate


@pytest.mark.parametrize("name", sorted(gate.SPECS))
def test_critical_mutation_anchor_is_present_exactly_as_declared(name: str):
    spec = gate.SPECS[name]
    source = (gate.ROOT / spec.path).read_text(encoding="utf-8")
    assert source.count(spec.before) == spec.expected_occurrences
    assert spec.before != spec.after
    assert spec.test


def test_apply_mutation_changes_only_the_declared_first_anchor(tmp_path: Path):
    spec = gate.MutationSpec(
        name="unit",
        path="sample.py",
        before="return True\n",
        after="return False\n",
        test="tests/test_sample.py",
        expected_occurrences=2,
    )
    path = tmp_path / spec.path
    path.write_text("def a():\n    return True\ndef b():\n    return True\n", encoding="utf-8")
    gate.apply_mutation(path, spec)
    mutated = path.read_text(encoding="utf-8")
    assert mutated.count("return False") == 1
    assert mutated.count("return True") == 1


def test_apply_mutation_fails_when_source_anchor_drifts(tmp_path: Path):
    spec = gate.MutationSpec(
        name="drift",
        path="sample.py",
        before="expected\n",
        after="mutated\n",
        test="tests/test_sample.py",
    )
    path = tmp_path / spec.path
    path.write_text("different\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="expected 1 source anchor"):
        gate.apply_mutation(path, spec)
