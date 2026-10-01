"""``gpu.tensor`` stays a thin, non-duplicating compatibility shim over ``tensor``."""

from __future__ import annotations

import warnings

import pytest


def test_gpu_tensor_emits_deprecation_warning_on_import():
    import sys

    sys.modules.pop("gpu.tensor", None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import gpu.tensor  # noqa: F401

    messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
    assert any("tensor" in message for message in messages)


def test_gpu_tensor_measurement_is_the_same_class_as_tensor_contracts():
    import gpu.tensor as gpu_tensor
    from tensor.contracts import TensorMeasurement

    assert gpu_tensor.TensorMeasurement is TensorMeasurement


def test_gpu_tensor_measurement_still_constructs_positionally():
    import gpu.tensor as gpu_tensor

    measurement = gpu_tensor.TensorMeasurement(5_000_000_000_000, 1_000_000_000, "test")
    assert measurement.tflops == pytest.approx(5.0)
    assert measurement.as_dict()["hashrate_hps"] is None


def test_gpu_tensor_advisor_reexports_match_tensor_advisor():
    import gpu.tensor as gpu_tensor
    from tensor.advisor import WindowRanker, apply_tensor_advice

    assert gpu_tensor.apply_tensor_advice is apply_tensor_advice
    assert gpu_tensor.WindowRanker is WindowRanker


def test_gpu_tensor_loaders_match_kellogg_bridge():
    import gpu.tensor as gpu_tensor
    from tensor.kellogg_bridge import load_exact_tensor_module, load_quantum_tensor_module

    assert gpu_tensor.load_exact_tensor_module is load_exact_tensor_module
    assert gpu_tensor.load_quantum_tensor_module is load_quantum_tensor_module


def test_gpu_tensor_raises_attribute_error_for_unknown_names():
    import gpu.tensor as gpu_tensor

    with pytest.raises(AttributeError):
        gpu_tensor.not_a_real_export
