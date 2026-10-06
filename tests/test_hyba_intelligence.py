from __future__ import annotations

import pytest

from chronus.mla1517.mining.hyba_intelligence import (
    CandidateBoundaryError,
    HYBAIntelligencePipeline,
)


class _Geodesic:
    def order_window(self, candidates, *, anchor=None):
        return list(reversed(candidates))


class _VQC:
    def rank_candidates(self, header, candidates):
        assert "nonce" not in header
        return {"candidates": sorted(candidates)}


class _Table:
    def __init__(self, values):
        self.values = tuple(values)

    def lookup_int(self, index):
        return self.values[index]


def _profile(fn):
    return fn(), 0.001


def _pipeline(**kwargs):
    return HYBAIntelligencePipeline(
        memory_custody=lambda values: _Table(values),
        geodesic=_Geodesic(),
        vqc=_VQC(),
        profiler=_profile,
        **kwargs,
    )


def test_all_stages_preserve_candidate_membership_and_report_no_authority():
    result = _pipeline().prepare({"job": "abc", "nonce": 9}, [4, 2, 8, 1])
    assert result.candidates == (1, 2, 4, 8)
    assert [stage.name for stage in result.stages] == [
        "chronus_v33_memory",
        "geodesic",
        "phi_vqc",
    ]
    assert all(stage.permutation_preserved for stage in result.stages)
    assert result.consensus_authority is False
    assert result.proof_authority is False


def test_binary_header_is_bounded_and_nonce_is_excluded_from_features():
    result = _pipeline(enable_geodesic=False).prepare(bytes(80), [3, 2, 1])
    assert result.candidates == (1, 2, 3)
    with pytest.raises(ValueError):
        _pipeline().prepare(bytes(79), [1])


@pytest.mark.parametrize("values", [[], [1, 1], [-1], [2**32], [True], ["1"]])
def test_invalid_candidate_windows_are_rejected(values):
    with pytest.raises(CandidateBoundaryError):
        _pipeline().prepare({}, values)


def test_stage_cannot_add_or_remove_candidates_even_when_fail_open():
    class Malicious:
        def order_window(self, candidates, *, anchor=None):
            return list(candidates) + [99]

    pipeline = HYBAIntelligencePipeline(
        memory_custody=lambda values: _Table(values),
        geodesic=Malicious(),
        vqc=_VQC(),
        profiler=_profile,
        fail_open=True,
    )
    with pytest.raises(CandidateBoundaryError):
        pipeline.prepare({}, [1, 2, 3])


def test_unavailable_advisory_stage_degrades_to_baseline():
    class Failed:
        def order_window(self, candidates, *, anchor=None):
            raise RuntimeError("backend unavailable")

    pipeline = HYBAIntelligencePipeline(
        memory_custody=lambda values: _Table(values),
        geodesic=Failed(),
        vqc=_VQC(),
        profiler=_profile,
        fail_open=True,
    )
    result = pipeline.prepare({}, [3, 1, 2])
    assert result.candidates == (1, 2, 3)
    assert result.stages[1].state == "DEGRADED_BASELINE"
    assert "backend unavailable" in result.stages[1].detail


def test_pulvini_fold_injection_is_rejected_at_production_boundary():
    with pytest.raises(ValueError, match="PULVINI/data fold injection is forbidden"):
        HYBAIntelligencePipeline(
            fold=lambda values, depth: values,
            memory_custody=lambda values: _Table(values),
            geodesic=_Geodesic(),
            vqc=_VQC(),
            profiler=_profile,
        )


def test_candidate_limit_is_enforced_before_any_backend_call():
    pipeline = _pipeline(max_candidates=2)
    with pytest.raises(CandidateBoundaryError):
        pipeline.prepare({}, [1, 2, 3])


def test_default_chronus_v33_memory_custody_roundtrips_uint32_candidates():
    pipeline = HYBAIntelligencePipeline(
        enable_geodesic=False,
        enable_vqc=False,
        profiler=_profile,
    )
    result = pipeline.prepare({}, [0, 17, 2**32 - 1])
    assert result.candidates == (0, 17, 2**32 - 1)
    assert result.stages[0].name == "chronus_v33_memory"
    assert result.stages[0].state == "ACTIVE"
