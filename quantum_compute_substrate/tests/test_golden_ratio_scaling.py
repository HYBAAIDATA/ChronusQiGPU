"""Tests for golden ratio scaling module."""

from quantum_compute_substrate.golden_ratio_scaling import (
    GoldenRatioScaler,
    PHI_10,
    PHI_12,
    PHI_15,
    PHI_37,
    phi_power,
    fibonacci,
    phi_power_decomposition,
)
from quantum_compute_substrate.phi_tensor_core import PHI


class TestPhiPowers:
    def test_phi_10_value(self):
        assert abs(PHI_10 - 122.991869) < 0.001

    def test_phi_12_value(self):
        assert abs(PHI_12 - 321.996894) < 0.001

    def test_phi_15_value(self):
        assert abs(PHI_15 - 1364.000737) < 0.001

    def test_phi_37_value(self):
        assert PHI_37 > 50e6  # > 50 million
        assert PHI_37 < 60e6  # < 60 million

    def test_phi_power_general(self):
        assert abs(phi_power(0) - 1.0) < 1e-10
        assert abs(phi_power(1) - PHI) < 1e-10
        assert abs(phi_power(2) - PHI**2) < 1e-10

    def test_cascaded_equals_product(self):
        # φ^37 should equal φ^10 × φ^12 × φ^15
        product = PHI_10 * PHI_12 * PHI_15
        assert abs(PHI_37 - product) < 1e-6


class TestFibonacci:
    def test_fibonacci_sequence(self):
        expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
        for i, exp in enumerate(expected):
            assert fibonacci(i) == exp

    def test_fibonacci_10(self):
        assert fibonacci(10) == 55

    def test_fibonacci_12(self):
        assert fibonacci(12) == 144

    def test_fibonacci_15(self):
        assert fibonacci(15) == 610

    def test_fibonacci_37(self):
        assert fibonacci(37) == 24157817


class TestPhiDecomposition:
    def test_decomposition_10(self):
        d = phi_power_decomposition(10)
        assert d["fibonacci_n"] == 55
        assert d["fibonacci_n_minus_1"] == 34
        assert abs(d["value"] - d["verification"]) < 1e-10

    def test_decomposition_12(self):
        d = phi_power_decomposition(12)
        assert d["fibonacci_n"] == 144
        assert d["fibonacci_n_minus_1"] == 89
        assert abs(d["value"] - d["verification"]) < 1e-10

    def test_decomposition_15(self):
        d = phi_power_decomposition(15)
        assert d["fibonacci_n"] == 610
        assert d["fibonacci_n_minus_1"] == 377
        assert abs(d["value"] - d["verification"]) < 1e-10

    def test_decomposition_37(self):
        d = phi_power_decomposition(37)
        assert d["fibonacci_n"] == 24157817
        assert abs(d["value"] - d["verification"]) < 1e-6

    def test_self_similar_property(self):
        # φ^n = F(n)·φ + F(n-1) — the self-similar identity
        for n in [5, 10, 12, 15, 20, 37]:
            d = phi_power_decomposition(n)
            assert (
                abs(d["value"] - d["verification"]) < 1e-6
            ), f"Failed for n={n}: {d['value']} != {d['verification']}"


class TestGoldenRatioScaler:
    def test_base_targets(self):
        scaler = GoldenRatioScaler()
        assert scaler.base.tensor_cores == 8192
        assert scaler.base.qubits == 4096
        assert scaler.base.fp64_eflops == 2.5

    def test_scale_tier_10(self):
        scaler = GoldenRatioScaler()
        arch = scaler.scale_tier(10)
        assert arch.scaling_factor > 122
        assert arch.scaling_factor < 123
        assert arch.tensor_cores == int(8192 * PHI_10)
        assert arch.fp64_eflops == 2.5 * PHI_10

    def test_scale_tier_12(self):
        scaler = GoldenRatioScaler()
        arch = scaler.scale_tier(12)
        assert arch.scaling_factor > 321
        assert arch.scaling_factor < 322
        assert arch.tensor_cores == int(8192 * PHI_12)

    def test_scale_tier_15(self):
        scaler = GoldenRatioScaler()
        arch = scaler.scale_tier(15)
        assert arch.scaling_factor > 1363
        assert arch.scaling_factor < 1365
        assert arch.tensor_cores == int(8192 * PHI_15)
        assert arch.fp64_eflops == 2.5 * PHI_15

    def test_scale_all_tiers(self):
        scaler = GoldenRatioScaler()
        tiers = scaler.scale_all_tiers()
        assert "base" in tiers
        assert "tier_i" in tiers
        assert "tier_ii" in tiers
        assert "tier_iii" in tiers
        assert "cascaded" in tiers

    def test_cascaded_is_phi_37(self):
        scaler = GoldenRatioScaler()
        tiers = scaler.scale_all_tiers()
        cascaded = tiers["cascaded"]
        assert abs(cascaded.scaling_factor - PHI_37) < 1e-6

    def test_scaling_monotonic(self):
        scaler = GoldenRatioScaler()
        tiers = scaler.scale_all_tiers()
        assert tiers["base"].scaling_factor < tiers["tier_i"].scaling_factor
        assert tiers["tier_i"].scaling_factor < tiers["tier_ii"].scaling_factor
        assert tiers["tier_ii"].scaling_factor < tiers["tier_iii"].scaling_factor
        assert tiers["tier_iii"].scaling_factor < tiers["cascaded"].scaling_factor

    def test_fibonacci_chain(self):
        scaler = GoldenRatioScaler()
        chain = scaler.get_fibonacci_chain()
        assert len(chain) == 4
        assert chain[0]["n"] == 10
        assert chain[1]["n"] == 12
        assert chain[2]["n"] == 15
        assert chain[3]["n"] == 37

    def test_scaling_table(self):
        scaler = GoldenRatioScaler()
        table = scaler.get_scaling_table()
        assert len(table) == 5  # base + 3 tiers + cascaded
        for row in table:
            assert "tensor_cores" in row
            assert "fp64_eflops" in row

    def test_get_specs(self):
        scaler = GoldenRatioScaler()
        specs = scaler.get_specs()
        assert "phi" in specs
        assert "phi_10" in specs
        assert "phi_12" in specs
        assert "phi_15" in specs
        assert "phi_37" in specs
        assert "scaling_table" in specs
        assert "fibonacci_chain" in specs

    def test_to_dict(self):
        scaler = GoldenRatioScaler()
        arch = scaler.scale_tier(10, "Tier I: φ^10 (Foundational)")
        d = arch.to_dict()
        assert d["tier"] == "Tier I: φ^10 (Foundational)"
        assert d["scaling_factor"] > 122
        assert d["tensor_cores"] > 0

    def test_tier_15_exceeds_rubin(self):
        """φ^15 scaled tensor cores should massively exceed Rubin R100's 896."""
        scaler = GoldenRatioScaler()
        arch = scaler.scale_tier(15)
        assert arch.tensor_cores > 896 * 1000  # at least 1000× more

    def test_cascaded_exceeds_all(self):
        """Cascaded φ^37 scaling should be massive."""
        scaler = GoldenRatioScaler()
        arch = scaler.scale_tier(37)
        assert arch.tensor_cores > 1e11  # > 100 billion (8192 × 54M ≈ 442B)
        assert arch.fp64_eflops > 1e8  # > 100 million EFLOPS (2.5 × 54M ≈ 135M)
