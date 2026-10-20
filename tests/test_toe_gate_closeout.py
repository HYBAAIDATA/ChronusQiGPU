"""Gate completeness and negative-control regressions for the real proof."""
import pytest
from experiments import toe_enterprise_collapse as gate


def rows():
    return [{"name": f"T{i}_witness", "passed": True} for i in range(1, 17)]


def test_all_sixteen_required():
    assert gate.all_required_checks_pass(rows())


@pytest.mark.parametrize("change", ["missing", "duplicate", "skip", "false", "truthy"])
def test_no_false_green(change):
    values = rows()
    if change == "missing":
        values.pop()
    elif change == "duplicate":
        values[-1]["name"] = values[0]["name"]
    elif change == "skip":
        values[-1]["skipped"] = True
    elif change == "false":
        values[-1]["passed"] = False
    else:
        values[-1]["passed"] = "true"
    assert not gate.all_required_checks_pass(values)


def test_twelve_support_witnesses():
    assert gate.check_support_layer()["passed"] is True


def test_ladder_is_executed_not_asserted():
    result = gate.check_lucas_ladder()
    assert result["passed"] is True
    assert result["coherence_measured"] is True
    assert len(result["scaled_confidence_formula"]) == 5


def test_cache_collision_never_reuses_other_input():
    assert gate.check_scale_fold_store()["passed"] is True
    a, b = {"value": [1.0]}, {"value": [1.001]}
    assert gate.zeckendorf_signature(a) == gate.zeckendorf_signature(b)
    store = gate.ScaleFoldStore(gate.DIM, gate.HBAR, gate.MASS, gate.OMEGA)
    first, _ = store.folded_state(a)
    other, hit = store.folded_state(b)
    assert not hit and other is not first


def test_missing_t16_fails_gate(monkeypatch):
    monkeypatch.setattr(gate.Path, "is_file", lambda _: False)
    result = gate.check_first_principles_lucas_scaling()
    assert result["passed"] is False
    values = rows()
    values[-1] = result
    assert not gate.all_required_checks_pass(values)
