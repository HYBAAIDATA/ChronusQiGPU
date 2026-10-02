from __future__ import annotations

from chronus.measurement.attestation.hmac import ENV_KEY
from chronus.measurement.attestation.artifact import build_artifact
from chronus.measurement.production import measure_chronus_production
from chronus.measurement.store.evidence import EvidenceStore


def _base_artifact():
    return build_artifact(
        {
            "baseline": {
                "devices": [
                    {
                        "name": "Physical GPU",
                        "backend": "opencl",
                        "device_type": "GPU",
                        "device_class": "integrated",
                    }
                ],
                "fingerprints": [{"digest": "a" * 64}],
            },
            "topology": {},
            "profiling": {},
            "roofline": {},
            "workloads": {
                "hashrate": {
                    "backend": "opencl:Physical GPU",
                    "device_id": "Physical GPU",
                    "hps": {"mean": 1.0},
                }
            },
            "efficiency": {},
            "stability": {},
        }
    )


def _patch_measurement(monkeypatch):
    import chronus.measurement.production as production

    base = _base_artifact()

    def fake_measure_chronus(**kwargs):
        del kwargs
        return base, {"artifact.replay": True}

    def fake_device_stage(*, quick):
        del quick
        return {
            "tflops": {"mean": 1.0},
            "gflops": {"mean": 1000.0},
            "backend": "chronus-opencl",
            "device_id": "Physical GPU",
            "verified": True,
        }

    monkeypatch.setattr(production, "measure_chronus", fake_measure_chronus)
    monkeypatch.setattr(production, "_device_tensor_stage", fake_device_stage)


def test_explicit_hmac_key_is_durable_attestation(monkeypatch):
    _patch_measurement(monkeypatch)
    monkeypatch.delenv(ENV_KEY, raising=False)
    _, availability = measure_chronus_production(
        hmac_key=b"persistent-test-key",
        store=EvidenceStore(),
    )
    assert availability["artifact.persistent_attestation_key"] is True


def test_environment_hmac_key_is_durable_attestation(monkeypatch):
    _patch_measurement(monkeypatch)
    monkeypatch.setenv(ENV_KEY, "00112233445566778899aabbccddeeff")
    _, availability = measure_chronus_production(store=EvidenceStore())
    assert availability["artifact.persistent_attestation_key"] is True


def test_ephemeral_hmac_key_is_not_client_grade_attestation(monkeypatch):
    _patch_measurement(monkeypatch)
    monkeypatch.delenv(ENV_KEY, raising=False)
    _, availability = measure_chronus_production(store=EvidenceStore())
    assert availability["artifact.persistent_attestation_key"] is False
