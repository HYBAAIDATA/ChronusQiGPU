"""Native Lucas scaling invariants: executable address work, not a speedup claim."""

import pytest
from chronus.igpu.scaled_plan import LADDER, ScaledPlan


def require(value, reason):
    if not value:
        raise AssertionError(reason)


@pytest.mark.parametrize("rung", LADDER)
def test_lucas_streamed_address_coverage(rung):
    values = [2, 1]
    for _ in range(2, rung + 1):
        values.append(values[-1] + values[-2])
    plan = ScaledPlan(
        base_items=3, scale_index=rung, start=7, lanes=8, address_limit=4096
    )
    require(plan.factor == values[rung], "independent Lucas recurrence mismatch")
    require(
        plan.effective_items == min(3 * values[rung], 4089), "address bound mismatch"
    )
    chunks = list(plan.chunks(max_chunk_items=31))
    require(
        chunks[0][0] == 7 and chunks[-1][1] == 7 + plan.effective_items,
        "coverage endpoints mismatch",
    )
    require(
        all(a[1] == b[0] for a, b in zip(chunks, chunks[1:])), "stream gaps/overlaps"
    )
    require(all(0 < end - start <= 31 for start, end in chunks), "unbounded chunk")
    require(
        plan.manifest()["physical_throughput_multiplier"] is None,
        "unmeasured throughput claimed",
    )


def test_zero_work_has_no_chunks():
    require(list(ScaledPlan(0).chunks()) == [], "zero work emitted chunks")


def test_unsupported_rung_refused():
    with pytest.raises(ValueError):
        ScaledPlan(1, scale_index=11)
