from __future__ import annotations

import json

import numpy as np
import pytest

from chronus.measurement.attestation.artifact import build_artifact
from chronus.measurement.production import measure_chronus_production
from chronus.measurement.store.evidence import EvidenceStore
from chronus.measurement.system.execution import bind_execution_device
from chronus.measurement.workload.device_tensor import measure_device_tensor_matmul


class _Runtime:
    device_id = "opencl:test:Physical GPU"

    def execute(self, operation, inputs, input_shapes, output_shape):
        assert operation == "matmul"
        assert tuple(output_shape) == (inputs[0].shape[0], inputs[1].shape[1])
        assert tuple(input_shapes[0]) == tuple(inputs[0].shape)
        return np.asarray(inputs[0], dtype=np.float32) @ np.asarray(inputs[1], dtype=np.float32)


class _BadRuntime(_Runtime):
    def execute(self, operation, inputs, input_shapes, output_shape):
        super().execute(operation, inputs, input_shapes, output_shape)
        return np.zeros(output_shape, dtype=np.float32)


def _baseline():
    return {
        "devices": [
            {
                "name": "MLA1517 iGPU",
                "backend": "chronus",
                "device_type": "GPU",
                "device_class": "integrated",
            },
            {
                "name": "Physical GPU",
                "backend": "opencl",
                "device_type": "GPU",
                "device_class": "integrated",
            },
        ],
        "fingerprints": [
            {"digest": "c" * 64},
            {"digest": "p" * 64},
        ],
        "os": "test",
    }


def _measurements():
    return {
        "baseline": _baseline(),
        "topology": {},
        "profiling": {},
        "roofline": {},
        "workloads": {
            "hashrate": {
                "backend": "opencl:Physical GPU",
                "device_id": "Physical GPU",
                "hps": {"mean": 1000.0},
            },
            "tensor": {"method": "host_numpy_matmul_float32"},
        },
        "efficiency": {},
        "stability": {},
    }


def test_device_tensor_measurement_is_verified_and_device_labelled():
    measured = measure_device_tensor_matmul(
        shape=(16, 16),
        repeats=3,
        warmup=1,
        runtime=_Runtime(),
    )
    assert measured.verified is True
    assert measured.backend == "chronus-opencl"
    assert measured.device_id == _Runtime.device_id
    assert measured.gflops.mean > 0
    assert measured.tflops.mean == pytest.approx(measured.gflops.mean / 1000.0)
    assert measured.method == "chronus_opencl_end_to_end_matmul_f32"


def test_device_tensor_measurement_rejects_unverified_output():
    with pytest.raises(RuntimeError, match="failed NumPy verification"):
        measure_device_tensor_matmul(
            shape=(8, 8),
            repeats=1,
            warmup=0,
            runtime=_BadRuntime(),
        )


def test_execution_binding_prefers_physical_device_over_contract_identity():
    binding = bind_execution_device(
        _baseline(),
        workload="tensor_device",
        backend="chronus-opencl",
        device_id="opencl:test:Physical GPU",
    )
    assert binding["matched"] is True
    assert binding["device_fingerprint"] == "p" * 64
    assert binding["matched_device"] == "Physical GPU"
    assert binding["matched_backend"] == "opencl"


def test_build_artifact_can_bind_explicit_execution_fingerprint():
    artifact = build_artifact(_measurements(), device_fingerprint="p" * 64)
    assert artifact.device_fingerprint == "p" * 64


def test_persisted_evidence_recomputes_digest_and_detects_tamper(tmp_path):
    store = EvidenceStore(directory=tmp_path)
    artifact = build_artifact(_measurements())
    key = store.write(artifact)
    path = tmp_path / f"{key}.json"

    assert store.load(path)["ok"] is True

    data = json.loads(path.read_text(encoding="utf-8"))
    data["workloads"]["hashrate"]["hps"]["mean"] = 999999.0
    path.write_text(json.dumps(data), encoding="utf-8")
    assert store.load(path)["ok"] is False


def test_production_artifact_adds_device_evidence_without_replacing_host_measurement(monkeypatch):
    import chronus.measurement.production as production

    base = build_artifact(_measurements())

    def fake_measure_chronus(**kwargs):
        del kwargs
        return base, {"artifact.replay": True}

    def fake_device_stage(*, quick):
        assert quick is True
        return {
            "gflops": {"mean": 2500.0, "stddev": 0.0, "samples": 1, "p50": 2500.0, "p95": 2500.0, "p99": 2500.0},
            "tflops": {"mean": 2.5, "stddev": 0.0, "samples": 1, "p50": 2.5, "p95": 2.5, "p99": 2.5},
            "operation": "matmul",
            "shape": [128, 128],
            "precision": "fp32",
            "method": "chronus_opencl_end_to_end_matmul_f32",
            "backend": "chronus-opencl",
            "device_id": "opencl:test:Physical GPU",
            "verified": True,
        }

    monkeypatch.setattr(production, "measure_chronus", fake_measure_chronus)
    monkeypatch.setattr(production, "_device_tensor_stage", fake_device_stage)

    artifact, availability = measure_chronus_production(
        quick=True,
        hmac_key=b"test-key",
        store=EvidenceStore(),
    )

    assert artifact.workloads["tensor"]["method"] == "host_numpy_matmul_float32"
    assert artifact.workloads["tensor_device"]["tflops"]["mean"] == 2.5
    assert artifact.device_fingerprint == "p" * 64
    assert artifact.baseline["execution_provenance"][1]["matched"] is True
    assert availability["workloads.tensor_device"] is True
    assert availability["artifact.execution_device_bound"] is True
    assert availability["artifact.replay"] is True
