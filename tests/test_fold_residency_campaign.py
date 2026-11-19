"""Acceptance of operation-trace execution, not customer workload evidence."""
import json
from collections import Counter

import pytest

from scripts.benchmarks.fold_residency_campaign import DATA, run_trace


@pytest.mark.parametrize("name", ["event_log", "object_store", "analytics"])
def test_equal_work_and_egress(name):
    spec = json.loads(DATA.read_text())["classes"][name]
    baseline, folded = run_trace(spec, 0), run_trace(spec, 7)
    assert baseline["op_multiset"] == folded["op_multiset"] == Counter(spec["ops"])
    assert baseline["output"] == folded["output"]
    assert baseline["observations"] == folded["observations"]
    for result in (baseline, folded):
        assert result["egress_materializations"]
        assert set(result["egress_materializations"]) == {1}
        assert result["materializations"] == (
            result["ingress_materializations"] + sum(result["egress_materializations"]))


def test_unknown_op_rejected():
    with pytest.raises(ValueError):
        run_trace({"words": [1, 2], "other": [3, 4], "ops": ["unclassified"]}, 7)
