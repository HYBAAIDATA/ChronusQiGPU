from dataclasses import dataclass

from hyba.hybrid.hybrid_asic_profile import HybridAsicDesignProfile
from hyba.hybrid.lucas_partition import SpanAssignment
from hyba.hybrid.tensor_advisor import (
    apply_tensor_advice,
    verify_tensor_advice_replay,
)
from hyba.hybrid.unified_theory_ranker import GoldenUnifiedWindowRanker


@dataclass(frozen=True)
class FakeJob:
    job_id: str = "job-1"
    header80: bytes = bytes(range(80))


def _windows():
    return [
        SpanAssignment("gpu:0", 0, 8, 0),
        SpanAssignment("asic:0", 8, 8, 1),
        SpanAssignment("gpu:0", 16, 8, 2),
    ]


def test_ranker_is_deterministic_exact_permutation_with_replay_evidence():
    ranker = GoldenUnifiedWindowRanker()
    job = FakeJob()
    original = _windows()
    ranked, evidence = apply_tensor_advice(ranker, job, original)
    ranked_again, _ = apply_tensor_advice(ranker, job, original)
    assert ranked == ranked_again
    assert sorted(ranked, key=repr) == sorted(original, key=repr)
    assert evidence.permutation_valid is True
    assert evidence.as_dict()["effect"] == "dispatch_order_only"
    assert verify_tensor_advice_replay(evidence, job, original, ranked)


def test_design_profile_keeps_protocol_truth_separate_from_future_silicon():
    report = HybridAsicDesignProfile(rounds_per_stage=4).report()
    assert report["sha256d_compressions_per_header"] == 3
    assert report["variable_compressions_per_nonce"] == 2
    assert report["host_reverification_required"] is True
    assert report["pdk_area_power_timing_claimed"] is False
    assert report["physical_asic_present"] is False
    assert report["comparative_advantage_claimed"] is False
