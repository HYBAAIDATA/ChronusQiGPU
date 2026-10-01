from dataclasses import replace

import pytest

from hyba.hybrid.lucas_partition import SpanAssignment
from hyba.hybrid.performance import LayerSample, PerformanceReport
from hyba.hybrid.tensor_advisor import (
    IdentityWindowRanker,
    TensorAdviceViolation,
    apply_tensor_advice,
)


def test_measured_hashrate_uses_only_protocol_hashes():
    report = PerformanceReport.from_samples(
        1_000_000_000,
        [
            LayerSample("asic", "asic-1", 1_000_000_000, protocol_hashes=2_000_000),
            LayerSample("chronus", "chronus-1", 1_000_000_000, protocol_hashes=1_000_000),
            LayerSample("tensor", "gpu-1", 1_000_000_000, tensor_operations=5_000_000_000_000),
        ],
    )
    assert report.measured_hashrate_hps == 3_000_000
    assert report.measured_tensor_tflops == 5.0
    assert report.floor_met is False


def test_tensor_layer_cannot_claim_hashes():
    with pytest.raises(ValueError, match="cannot be reported"):
        LayerSample("tensor", "gpu-1", 1, protocol_hashes=1)


def test_floor_requires_measured_protocol_work():
    report = PerformanceReport.from_samples(
        1_000_000_000,
        [LayerSample("asic", "fleet", 1_000_000_000, protocol_hashes=10**19)],
    )
    assert report.floor_met is True


def test_tensor_advice_accepts_only_an_exact_permutation():
    windows = [
        SpanAssignment("gpu-1", 0, 10, 0),
        SpanAssignment("asic-1", 10, 10, 1),
    ]
    ranked, evidence = apply_tensor_advice(IdentityWindowRanker(), object(), windows)
    assert ranked == windows
    assert evidence.permutation_valid is True
    assert evidence.as_dict()["effect"] == "dispatch_order_only"


class _MutatingRanker:
    model_id = "bad-v1"

    def rank(self, job, windows):
        del job
        return [replace(windows[0], span=windows[0].span + 1), *windows[1:]]


def test_tensor_advice_fails_closed_on_window_mutation():
    windows = [SpanAssignment("gpu-1", 0, 10, 0)]
    with pytest.raises(TensorAdviceViolation, match="exact permutation"):
        apply_tensor_advice(_MutatingRanker(), object(), windows)


def test_floor_enforcement_is_explicit_and_fail_closed():
    from hyba.hybrid.performance import HashrateFloorViolation, enforce_floor
    low = PerformanceReport.from_samples(
        1_000_000_000,
        [LayerSample("gpu", "g", 1_000_000_000, protocol_hashes=1)],
    )
    with pytest.raises(HashrateFloorViolation):
        enforce_floor(low)
    high = PerformanceReport.from_samples(
        1_000_000_000,
        [LayerSample("asic", "a", 1_000_000_000, protocol_hashes=10**19)],
    )
    assert enforce_floor(high) is high


def test_per_layer_hashrate_retains_device_attribution():
    report = PerformanceReport.from_samples(
        2_000_000_000,
        [
            LayerSample("gpu", "g1", 2_000_000_000, protocol_hashes=20),
            LayerSample("asic", "a1", 2_000_000_000, protocol_hashes=30),
        ],
    )
    rows = report.by_layer()
    assert rows["gpu"]["protocol_hashes"] == 20
    assert rows["asic"]["protocol_hashes"] == 30
    assert report.as_dict()["evidence_digest"]


class _MutableJob:
    def __init__(self):
        self.target = "original"


class _JobMutatingRanker:
    model_id = "mutates-job"

    def rank(self, job, windows):
        job.target = "changed"
        return list(windows)


def test_tensor_advice_rejects_job_mutation():
    windows = [SpanAssignment("gpu-1", 0, 10, 0)]
    with pytest.raises(TensorAdviceViolation, match="mutated the mining job"):
        apply_tensor_advice(_JobMutatingRanker(), _MutableJob(), windows)


def test_tensor_advice_evidence_replays_exactly():
    from hyba.hybrid.tensor_advisor import verify_tensor_advice_replay
    job = _MutableJob()
    windows = [
        SpanAssignment("gpu-1", 0, 10, 0),
        SpanAssignment("asic-1", 10, 10, 1),
    ]
    ranked, evidence = apply_tensor_advice(IdentityWindowRanker(), job, windows)
    assert verify_tensor_advice_replay(evidence, job, windows, ranked)
    assert evidence.replay_id


def test_hardware_evidence_refuses_unmeasured_or_empty_results():
    from bench.hardware_evidence import HardwareEvidenceError, validate_job_artifact
    with pytest.raises(HardwareEvidenceError):
        validate_job_artifact({"performance": {"truth_class": "modeled", "samples": []}})
    job = {
        "performance": {
            "truth_class": "measured",
            "protocol_hashes": 1,
            "wall_ns": 10,
            "samples": [{"source": "measured", "device_id": "gpu-1"}],
        }
    }
    assert validate_job_artifact(job)["artifact_sha256"]


def test_asic_optional_kernel_requires_explicit_advertisement():
    from hyba.hybrid.asic_solver import ASICSolver
    from hyba.hybrid.nonce_scheduler import DeviceCapability
    solver = ASICSolver()
    solver._capability = DeviceCapability(
        device_id="asic-test",
        device_class="asic",
        measured_hashes_per_sec=1.0,
        supported=True,
        detail={"advertised_kernels": ["sha256d_scan", "attest_result"]},
    )
    assert solver.supports_kernel("sha256d_scan")
    assert solver.supports_kernel("attest_result")
    assert not solver.supports_kernel("fold_certificate")
