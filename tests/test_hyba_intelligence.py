from __future__ import annotations

from dataclasses import dataclass

import pytest

from chronus.mla1517.mining.hyba_intelligence import (
    CandidateBoundaryError,
    HYBAIntelligencePipeline,
)


@dataclass
class _Folded:
    values: tuple[int, ...]

    def unfold(self):
        return self.values


class _Geodesic:
    def order_window(self, candidates, *, anchor=None):
        return list(reversed(candidates))


class _VQC:
    def rank_candidates(self, header, candidates):
        assert "nonce" not in header
        return {"candidates": sorted(candidates)}


def _profile(fn):
    return fn(), 0.001


def _pipeline(**kwargs):
    return HYBAIntelligencePipeline(
        fold=lambda values, depth: _Folded(tuple(values)),
        geodesic=_Geodesic(),
        vqc=_VQC(),
        profiler=_profile,
        **kwargs,
    )


def test_all_stages_preserve_candidate_membership_and_report_no_authority():
    result = _pipeline().prepare({"job": "abc", "nonce": 9}, [4, 2, 8, 1])
    assert result.candidates == (1, 2, 4, 8)
    assert [stage.name for stage in result.stages] == [
        "pulvini_custody",
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
        fold=lambda values, depth: _Folded(tuple(values)),
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
        fold=lambda values, depth: _Folded(tuple(values)),
        geodesic=Failed(),
        vqc=_VQC(),
        profiler=_profile,
        fail_open=True,
    )
    result = pipeline.prepare({}, [3, 1, 2])
    assert result.candidates == (1, 2, 3)
    assert result.stages[1].state == "DEGRADED_BASELINE"
    assert "backend unavailable" in result.stages[1].detail


def test_exact_custody_mismatch_always_fails_closed():
    pipeline = HYBAIntelligencePipeline(
        fold=lambda values, depth: _Folded(tuple(reversed(values))),
        geodesic=_Geodesic(),
        vqc=_VQC(),
        profiler=_profile,
        fail_open=True,
    )
    with pytest.raises(CandidateBoundaryError):
        pipeline.prepare({}, [1, 2, 3])


def test_candidate_limit_is_enforced_before_any_backend_call():
    pipeline = _pipeline(max_candidates=2)
    with pytest.raises(CandidateBoundaryError):
        pipeline.prepare({}, [1, 2, 3])