"""Fail-closed boundaries for the repaired 600-lane consumer contracts."""

import math

import pytest

from chronus.entangled_hashing import EntangledQubitHasher
from chronus.exact_geometry import build_600_partition
from kellogg.ansatz_v3 import AnsatzV3, TOEAnsatzV3, load_ansatz


def test_ansatz_alias_uses_single_canonical_type():
    assert AnsatzV3 is TOEAnsatzV3
    assert isinstance(load_ansatz(), AnsatzV3)


@pytest.mark.parametrize("initial", [math.nan, math.inf, -math.inf])
def test_nonfinite_curvature_is_not_an_execution_grant(initial):
    with pytest.raises(ValueError, match="finite"):
        load_ansatz().reconcile_lane(0, initial_kappa=initial)


@pytest.mark.parametrize("lane", [-1, 600, True, 1.5])
def test_lane_identity_is_validated(lane):
    with pytest.raises(ValueError):
        load_ansatz().reconcile_lane(lane)


def test_exhausted_flow_denies_execution():
    result = load_ansatz().reconcile_lane(0, max_steps=0)
    assert result.execution_granted is False
    assert abs(result.final_kappa) > 0.05


def test_legacy_trace_matches_typed_lane_trace():
    ansatz = load_ansatz()
    rows = ansatz.reconcile_lane_curvature()
    trace = ansatz.reconcile_lane(599)
    assert trace.execution_granted is True
    assert trace.steps_taken <= 8
    assert [step.kappa for step in trace.trace] == [row["kappa"] for row in rows]


@pytest.mark.parametrize("base,window,seed", [(0, 1200, 1337), (12345, 1801, 42)])
def test_candidate_reordering_preserves_each_exact_lease(base, window, seed):
    chunks, _ = build_600_partition(base, window, seed)
    seen = set()
    for chunk in chunks:
        hasher = EntangledQubitHasher(chunk, b"L" * 76, 0)
        generated = [n for n, _ in hasher._generate_entangled_nonces()]
        assert set(generated) == set(chunk.nonces)
        assert len(generated) == len(set(generated))
        assert not seen.intersection(generated)
        seen.update(generated)
    assert seen == set(range(base, base + window))


def test_explicit_zero_budget_never_hashes_a_nonce():
    chunks, _ = build_600_partition(0, 600)
    hasher = EntangledQubitHasher(chunks[0], b"L" * 76, (1 << 256) - 1)
    receipt = hasher.execute(max_evaluations=0)
    assert receipt.nonces_evaluated == 0
    assert receipt.winning_candidate is None
    assert receipt.device_id.startswith("cpu_reference_")
    assert receipt.fallback_reason != "NONE"
