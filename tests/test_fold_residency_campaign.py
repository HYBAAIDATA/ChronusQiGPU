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


@pytest.mark.parametrize("stage", [0, 7])
@pytest.mark.parametrize("nonempty", [False, True])
def test_analytics_boundary_accounting_and_plain_reference(stage, nonempty):
    """Post-campaign diagnostic; historical trace unchanged."""
    spec = json.loads(DATA.read_text())["classes"]["analytics"]
    if nonempty:
        spec = {**spec, "words": [11, 128, 200, 250], "other": [200, 250, 7, 8]}
    assert spec["ops"] == ["sort", "threshold", "topk", "magnitude_join", "sort", "equals"]
    thresholded = [x if x >= 128 else 0 for x in sorted(spec["words"])]
    top = sorted(thresholded, reverse=True)[:2]
    expected = sorted(v for x in top for y in spec["other"] if abs(x) == abs(y) for v in (x, y))
    if nonempty:
        assert thresholded == [0, 128, 200, 250]
        assert expected == [200, 200, 250, 250]
    else:
        assert thresholded == [0, 0, 0, 0]
        assert expected == []
    actual = run_trace(spec, stage)
    assert actual["output"] == expected
    assert actual["observations"] == [expected == [0] * len(expected)]
    assert actual["op_multiset"] == {"sort": 2, "threshold": 1, "topk": 1,
                                     "magnitude_join": 1, "equals": 1}
    assert actual["ingress_materializations"] == 12
    assert actual["egress_materializations"] == [1] * 6
    assert actual["materializations"] == 18
