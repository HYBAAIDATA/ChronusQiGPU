"""Tests for power and cooling systems."""

from quantum_compute_substrate.power_cooling import (
    QuantumPowerSystem, LiquidHeliumCooling, DiamondSubstrateCooling,
    QuantumCryostat, DirectToChipLiquidCooling,
)


class TestLiquidHeliumCooling:
    def test_cooling_capacity(self):
        lhe = LiquidHeliumCooling()
        assert lhe.cooling_capacity() == 500_000

    def test_power_required(self):
        lhe = LiquidHeliumCooling()
        power = lhe.power_required(1000)  # 1kW heat at 4.2K
        assert power > 1000  # COP < 1, so more power needed

    def test_boil_off_rate(self):
        lhe = LiquidHeliumCooling()
        rate = lhe.boil_off_rate(1000)
        assert rate > 0


class TestDiamondSubstrateCooling:
    def test_thermal_resistance(self):
        ds = DiamondSubstrateCooling()
        r = ds.thermal_resistance()
        assert r > 0
        assert r < 0.001  # very low resistance due to diamond

    def test_temperature_rise(self):
        ds = DiamondSubstrateCooling()
        rise = ds.temperature_rise(1_000_000)  # 1MW
        assert rise > 0

    def test_max_heat_flux(self):
        ds = DiamondSubstrateCooling()
        flux = ds.max_heat_flux(20.0)
        assert flux > 0


class TestQuantumCryostat:
    def test_cooling_capacity(self):
        qc = QuantumCryostat()
        assert qc.cooling_capacity() == 10_000

    def test_power_required(self):
        qc = QuantumCryostat()
        power = qc.power_required(100)
        assert power > 0

    def test_cooling_stages(self):
        qc = QuantumCryostat()
        assert len(qc.cooling_stages) == 5


class TestDirectToChipLiquidCooling:
    def test_heat_removal(self):
        dlc = DirectToChipLiquidCooling(coolant_flow_lpm=20.0, inlet_temp_c=25.0)
        capacity = dlc.heat_removal_capacity(outlet_temp_c=45.0)
        assert capacity > 0

    def test_outlet_temp(self):
        dlc = DirectToChipLiquidCooling()
        temp = dlc.outlet_temp(100_000)  # 100kW
        assert temp > dlc.inlet_temp


class TestQuantumPowerSystem:
    def test_power_at_90pct(self):
        ps = QuantumPowerSystem(total_power_w=1_200_000)
        result = ps.calculate_power_consumption(0.9)
        assert result["compute_power_w"] > 0
        assert result["total_power_w"] > result["compute_power_w"]
        assert result["pue"] > 1.0

    def test_quantum_reduction_at_70pct(self):
        ps = QuantumPowerSystem(total_power_w=1_200_000)
        result = ps.calculate_power_consumption(0.7)
        assert result["quantum_reduction"] == 0.15

    def test_no_quantum_reduction_at_50pct(self):
        ps = QuantumPowerSystem(total_power_w=1_200_000)
        result = ps.calculate_power_consumption(0.5)
        assert result["quantum_reduction"] == 0.0

    def test_cooling_capacity(self):
        ps = QuantumPowerSystem()
        cap = ps.cooling_capacity()
        assert cap["total_cooling_w"] > 0
        assert "liquid_helium_w" in cap
        assert "diamond_substrate_w" in cap

    def test_thermal_analysis(self):
        ps = QuantumPowerSystem()
        analysis = ps.thermal_analysis()
        assert "diamond_temp_rise_k" in analysis
        assert "helium_boil_off_lph" in analysis
        assert "liquid_cooling_outlet_c" in analysis

    def test_get_specs(self):
        ps = QuantumPowerSystem()
        specs = ps.get_specs()
        assert "total_power_target" in specs
        assert "cooling_systems" in specs
