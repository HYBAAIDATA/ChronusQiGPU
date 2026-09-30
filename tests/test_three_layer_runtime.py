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
            LayerSample("igpu", "igpu-1", 1_000_000_000, protocol_hashes=1_000_000),
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
