"""Benchmarks must count all retained kernels and label reference timings correctly."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/benchmarks/storage_closeout.py"
_SPEC = importlib.util.spec_from_file_location("chronus_storage_closeout", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_reference_storage_reopen_and_latency_labels():
    result = _MODULE.storage_benchmark(records=3, payload_bytes=64)
    assert result["byte_exact_readback_verified"]
    assert result["fresh_service_reopen_verified"]
    assert result["write_call_latency"]["sample_count"] == 3
    assert result["device_iops"] is None
    assert result["power_loss_recovery"] is None


def test_complete_fold_serialization_and_accounting():
    result = _MODULE.fold_benchmark(elements=128, depth=4, seed=23)
    assert result["executed_depth"] == 4
    assert result["original_bytes"] == 128 * 8
    assert result["complete_retained_bytes"] == (
        result["active_working_set_bytes"] + result["all_kernel_bytes"]
    )
    assert result["serialized_complete_bytes"] >= result["complete_retained_bytes"]
    assert result["complete_retained_ratio"] < 1
    assert result["claimed_11_5x_promoted"] is False
    assert result["relative_reconstruction_error"] <= 1e-12


def test_serialization_independently_roundtrips_without_pickle():
    from chronus.pulvini import fold_verified, unfold_verified

    original = np.arange(91, dtype=np.float64) / 17
    state, receipt = fold_verified(original, depth=5)
    representation = _MODULE.serialize_complete_fold(state)
    restored = _MODULE.deserialize_complete_fold(representation)
    np.testing.assert_allclose(
        unfold_verified(restored, receipt=receipt), original, rtol=0, atol=1e-12
    )
