"""Tests for hardware co-design specifications."""

from quantum_compute_substrate.hardware_codesign import (
    FPGAKernelSpec,
    PhiScaledTensorCoreASIC,
    PhotonicPhiFold,
    NeuromorphicHybrid,
)


class TestFPGA:
    def test_kernel_resource_estimate(self):
        spec = FPGAKernelSpec()
        est = spec.kernel_resource_estimate(dim=512)
        assert est["dim"] == 512
        assert est["latency_us"] > 0
        assert est["claim_lane"].startswith("RESTRICTED")

    def test_feasibility_flag(self):
        spec = FPGAKernelSpec()
        est = spec.kernel_resource_estimate(dim=128)
        assert isinstance(est["feasible"], bool)


class TestASIC:
    def test_throughput_estimate(self):
        asic = PhiScaledTensorCoreASIC()
        t = asic.estimate_throughput(num_pe=1024)
        assert t["peak_tops"] > 0

    def test_phi_scaled_pe_count(self):
        asic = PhiScaledTensorCoreASIC()
        r = asic.phi_scaled_pe_count(base_pe=8192, phi_exponent=2)
        assert r["scaled_pe_target"] > 8192


class TestPhotonic:
    def test_optical_throughput(self):
        photonic = PhotonicPhiFold()
        t = photonic.optical_throughput()
        assert t["aggregate_bps"] > 0
        assert "claim_lane" in t


class TestNeuromorphic:
    def test_synops(self):
        nm = NeuromorphicHybrid()
        r = nm.synaptic_ops_per_second(spike_rate_hz=100.0)
        assert r["synops_per_second"] > 0
