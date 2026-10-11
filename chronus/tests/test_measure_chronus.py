"""The iGPU measurement script, run against the CPU reference hasher."""

from __future__ import annotations

import pytest

from mining.bitcoin_hasher import BitcoinHasher
from chronus.scripts import measure_chronus


def test_self_check_accepts_a_correct_device_and_refuses_a_wrong_one():
    hasher = BitcoinHasher(backend="cpu")
    measure_chronus.self_check(hasher)

    class Wrong:
        def hash_batch(self, header, nonces):
            return [bytes(32) for _ in nonces]

    with pytest.raises(SystemExit, match="differs from hashlib"):
        measure_chronus.self_check(Wrong())


def test_measure_fits_the_world_models_line_over_real_windows():
    report = measure_chronus.measure(BitcoinHasher(backend="cpu"), [1024, 2048, 4096, 6144], 4)
    assert set(report["measured_ms"]) == {"1024", "2048", "4096", "6144"}
    assert report["fit_samples"] == 16 and report["hash_rate_hs"] > 0


def test_without_opencl_it_refuses_rather_than_measure_the_cpu(monkeypatch):
    class Cpu:
        backend = "cpu"
        fallback_reason = "no OpenCL device"

        def __init__(self, **_kwargs):
            pass

    monkeypatch.setattr(measure_chronus, "BitcoinHasher", Cpu)
    with pytest.raises(SystemExit, match="no OpenCL device bound"):
        measure_chronus.main([])
