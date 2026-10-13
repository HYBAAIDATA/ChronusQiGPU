"""Chronus measurement stack — every invariant exercised on real executions.

The tests assert measured behavior, not constants: bandwidth must be a
positive measured number, hashrate a measured distribution, unavailable
sensors declared unavailable with their reason — never fabricated.
"""

from __future__ import annotations

import time

import pytest

from chronus.measurement import (
    EvidenceStore,
    attest_artifact,
    build_artifact,
    capture_baseline,
    compute_fingerprint,
    enumerate_devices,
    measure_chronus,
    replay_artifact,
)
from chronus.measurement.efficiency.perf_per_watt import compute_perf_per_watt
from chronus.measurement.efficiency.power import measure_power
from chronus.measurement.profiling.events import profile_kernel
from chronus.measurement.profiling.timeline import capture_timeline
from chronus.measurement.roofline.arithmetic_intensity import compute_intensity
from chronus.measurement.roofline.bandwidth import measure_bandwidth
from chronus.measurement.roofline.compute import measure_peak_compute
from chronus.measurement.roofline.plot import build_roofline
from chronus.measurement.stability.regression import run_regression
from chronus.measurement.stability.stress import run_stress_test
from chronus.measurement.stability.throttle import detect_throttle
from chronus.measurement.store.query import (
    query_by_device,
    query_by_hashrate,
    query_by_time,
)
from chronus.measurement.system.clinfo import OpenCLDevice
from chronus.measurement.topology.compute import measure_compute_topology
from chronus.measurement.topology.memory import measure_memory_hierarchy
from chronus.measurement.workload.hashrate import measure_hashrate
from chronus.measurement.workload.mpo import measure_mpo_apply
from chronus.measurement.workload.mps import measure_mps_gate
from chronus.measurement.workload.tensor import measure_tensor_contraction
from chronus.measurement.workload.tt import measure_tt_svd


def _device(**over) -> OpenCLDevice:
    base = dict(
        name="MLA1517 iGPU",
        vendor="hyba",
        version="1.0",
        driver_version="drv-1",
        device_type="GPU",
        device_class="integrated",
        backend="chronus",
    )
    base.update(over)
    return OpenCLDevice(**base)


class TestSystemBaseline:
    def test_enumerate_devices_named_devices(self):
        platforms = enumerate_devices()
        assert platforms, "census must see at least one platform"
        devices = [d for p in platforms for d in p.devices]
        assert devices, "SYS1: every platform must carry a device"
        assert all(d.name for d in devices), "SYS1: every device has a name"

    def test_unknown_properties_listed_not_guessed(self):
        platforms = enumerate_devices()
        devices = [d for p in platforms for d in p.devices]
        for d in devices:
            for prop in d.properties_unknown:
                assert getattr(d, prop) in (
                    None,
                    [],
                ), f"SYS2: {prop} was filled despite being listed unknown"

    def test_fingerprint_stable_with_digest(self):
        fp1 = compute_fingerprint(_device())
        fp2 = compute_fingerprint(_device())
        assert fp1.digest and len(fp1.digest) == 64, "FP1: digest present"
        assert fp1.digest == fp2.digest, "FP2: stable across runs"

    def test_fingerprint_changes_with_driver(self):
        fp1 = compute_fingerprint(_device(driver_version="drv-1"))
        fp2 = compute_fingerprint(_device(driver_version="drv-2"))
        assert fp1.digest != fp2.digest, "FP3: driver change changes fingerprint"

    def test_baseline_attested_with_devices(self):
        baseline = capture_baseline()
        assert baseline.platforms, "BL1"
        assert baseline.devices, "BL2"
        assert baseline.attestation and len(baseline.attestation) == 64, "BL3"


class TestTopology:
    def test_memory_hierarchy_declares_unknowns(self):
        h = measure_memory_hierarchy(_device())
        for prop in h.unknown:
            assert getattr(h, prop, None) is None, f"MEM1: {prop} filled despite being unknown"

    def test_compute_topology_uses_contract(self):
        t = measure_compute_topology(_device())
        assert t.warp_width == 32, "contract warp_width must surface"
        assert "fp32_tflops" in t.theoretical or any(
            "fp32" in u for u in t.unknown
        ), "COMP2: peaks marked theoretical or unknown"


class TestProfiling:
    def test_profile_kernel_measured(self):
        profiles = profile_kernel("noop", lambda: None, runs=3)
        assert len(profiles) == 3
        assert all(p.kernel_name == "noop" for p in profiles), "PROF1"
        assert all(p.duration_ns >= 0 for p in profiles), "PROF2"
        assert all(p.method for p in profiles), "PROF3"

    def test_timeline_busy_plus_idle(self):
        tl = capture_timeline([("a", lambda: None), ("b", lambda: None)])
        assert tl.events, "TL1"
        assert tl.device_busy_ns + tl.device_idle_ns == tl.total_duration_ns, "TL2"


class TestRoofline:
    def test_intensity_zero_bytes_raises(self):
        with pytest.raises(ValueError):
            compute_intensity(100, 0)

    def test_bandwidth_measured_positive(self):
        bw = measure_bandwidth(size_bytes=1 << 20, repeats=3)
        assert bw.bandwidth_gbps > 0, "BW1: measured, not assumed"
        assert bw.method, "BW2: method declared"

    def test_peak_compute_measured_positive(self):
        pk = measure_peak_compute(n=64, repeats=2)
        assert pk.tflops > 0, "CP1: measured"
        assert pk.precision == "fp32" and pk.method, "CP2: declared"

    def test_roofline_classifies_bounds(self):
        class W:
            def __init__(self, name, flops, bts):
                self.name, self.flops, self.bytes_transferred = name, flops, bts

        model = build_roofline(
            peak_tflops=1.0,
            peak_bandwidth_gbps=10.0,
            workloads=[W("mem", 1, 10), W("cmp", int(1e9), 1)],
        )
        assert model.ridge_point == pytest.approx(100.0), "RL2"
        bounds = {p.name: p.bound for p in model.points}
        assert bounds == {"mem": "memory", "cmp": "compute"}, "RL1"


class TestWorkloads:
    def test_hashrate_measured_distribution(self):
        m = measure_hashrate(samples=3, warmup=1, window=512)
        assert m.hps.mean > 0, "HR1: measured"
        assert m.hps.samples == 3, "HR2: distribution with samples"
        assert m.warmup == 1, "HR3: warmup declared"
        assert m.backend, "backend labelled"

    def test_tensor_contraction_measured(self):
        m = measure_tensor_contraction(shape=(32, 32), repeats=4)
        assert m.gflops.mean > 0, "TM1: measured"
        assert m.shape == (32, 32) and m.precision == "fp32", "TM2"
        assert m.bytes_transferred > 0

    def test_mps_gate_measured(self):
        m = measure_mps_gate(n_qubits=8, chi_max=4, repeats=3)
        assert m["available"] is True
        assert m["n_qubits"] == 8 and m["chi_max"] == 4, "MPS1"
        assert m["gate_time_ns"]["samples"] == 3, "MPS2: repeated"

    def test_tt_svd_measured(self):
        m = measure_tt_svd(tensor_shape=(4, 4, 4), max_rank=4, repeats=3)
        assert m["available"] is True
        assert m["shape"] == [4, 4, 4] and m["max_rank"] == 4, "TT1"

    def test_mpo_apply_measured(self):
        m = measure_mpo_apply(n_sites=4, repeats=3)
        assert m["available"] is True
        assert m["mpo_shape"] and m["mps_shape"], "MPO1"


class TestEfficiency:
    def test_power_measured_or_declared_unavailable(self):
        p = measure_power(duration_s=0.1, period_ms=50)
        if p.available:
            assert p.watts is not None and p.watts.mean > 0, "PW1: measured"
            assert p.method, "PW2: method declared"
        else:
            assert p.watts is None and p.reason, "unavailable must say why"
            assert p.sources_tried, "unavailable must list sources"

    def test_ppw_requires_measured_power(self):
        p = measure_power(duration_s=0.05, period_ms=25)
        if not p.available:
            ppw = compute_perf_per_watt(None, None, p)
            assert ppw.available is False and ppw.reason, "PPW: no power, no quotient"


class TestStability:
    def test_stress_runs_and_computes_degradation(self):
        rates = iter([100.0] * 8 + [99.0] * 8 + [98.0] * 8 + [97.0] * 400)

        def measure():
            time.sleep(0.02)
            return next(rates)

        out = run_stress_test(measure, duration_s=0.2, min_samples=3)
        assert out["n_samples"] == len(out["samples"]) >= 3, "STR1"
        assert out["rate_initial"] == 100.0
        expected = (out["rate_initial"] - out["rate_final"]) / out["rate_initial"] * 100
        assert out["degradation_pct"] == pytest.approx(expected), "STR2"

    def test_throttle_detects_spread(self):
        clocks = iter([1000.0, 1200.0, 1000.0, 1200.0, 1000.0])
        out = detect_throttle(samples=5, period_s=0.0, clock_fn=lambda: next(clocks))
        assert out["available"] is True and out["throttled"] is True, "THR1"

    def test_throttle_flat_clock_not_throttled(self):
        out = detect_throttle(samples=4, period_s=0.0, clock_fn=lambda: 1000.0)
        assert out["available"] is True and out["throttled"] is False

    def test_regression_reports_variance(self):
        rates = iter([10.0, 12.0, 11.0, 10.5, 11.5])
        out = run_regression(lambda: next(rates), runs=5)
        assert out["runs"] == 5, "REG1"
        assert out["stddev_of_means"] > 0 and out["coefficient_of_variation"] > 0, "REG2"


class TestAttestationAndStore:
    def _measurements(self) -> dict:
        return {
            "baseline": {"fingerprints": [{"digest": "a" * 64}], "os": "test"},
            "topology": {},
            "profiling": {},
            "roofline": {},
            "workloads": {"hashrate": {"hps": {"mean": 1234.5}}},
            "efficiency": {},
            "stability": {},
        }

    def test_artifact_digest_content_addressed(self):
        a = build_artifact(self._measurements())
        assert a.digest and len(a.digest) == 64, "ART1"
        b = build_artifact(self._measurements())
        assert a.digest == b.digest, "ART2: same content, same address"

    def test_replay_true_then_forgery_fails(self):
        a = build_artifact(self._measurements())
        assert replay_artifact(a) is True, "RPL1"
        a.baseline["os"] = "tampered"
        assert replay_artifact(a) is False, "RPL2: forgery fails replay"

    def test_hmac_attest_no_key_in_artifact(self):
        a = build_artifact(self._measurements())
        a.attestation = attest_artifact(a, b"test-key")
        assert len(a.attestation) == 64, "HM1"
        assert "test-key" not in str(a.as_dict()), "HM2: key never stored"

    def test_store_write_read_verify(self):
        store = EvidenceStore()
        a = build_artifact(self._measurements())
        key = store.write(a)
        assert store.read(key) is a, "EV1"
        assert store.verify(key) is True, "EV2"

    def test_queries(self):
        store = EvidenceStore()
        a = build_artifact(self._measurements())
        store.write(a)
        assert query_by_device(store, "a" * 64) == [a], "Q1"
        assert query_by_time(store, "0000", "9999") == [a]
        assert query_by_hashrate(store, 1000.0) == [a]
        assert query_by_hashrate(store, 9999.0) == []


class TestEntryPoint:
    def test_measure_chronus_full_artifact(self):
        artifact, availability = measure_chronus(quick=True)
        assert artifact.digest and len(artifact.digest) == 64, "RUN1"
        assert artifact.attestation and len(artifact.attestation) == 64, "RUN2"
        assert replay_artifact(artifact), "RUN4: replayable"
        assert artifact.device_fingerprint, "fingerprint bound into artifact"
        # What ran measured; what could not is declared — either way it is
        # inside the artifact, never silent.
        assert "hashrate" in artifact.workloads
        assert availability["artifact.replay"] is True
