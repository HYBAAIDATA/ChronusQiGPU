"""Tests for Parts 14-16: Cross-Vendor GPU Architecture Comparison."""

from quantum_compute_substrate.nvidia_advances import NVIDIAAdvances
from quantum_compute_substrate.apple_advances import AppleAdvances
from quantum_compute_substrate.hp_advances import HPAdvances


class TestNVIDIAAdvances:
    """Part 14: NVIDIA GPU architecture tests."""

    def test_all_gpus_loaded(self):
        nvidia = NVIDIAAdvances()
        gpus = nvidia.get_all_gpus()
        names = [g.name for g in gpus]
        assert 'NVIDIA Rubin R100' in names
        assert 'NVIDIA Blackwell Ultra B300' in names
        assert 'NVIDIA Hopper H100' in names
        assert len(gpus) == 3

    def test_rubin_r100_specs(self):
        nvidia = NVIDIAAdvances()
        gpu = nvidia.get_gpu('rubin_r100')
        assert gpu is not None
        assert gpu.tensor_cores == 896
        assert gpu.process_node == '3nm EUV'
        assert gpu.memory_capacity_gb == 288
        assert gpu.fp4_performance_pflops == 50.0
        assert gpu.nvlink_generation == 6

    def test_blackwell_b300_specs(self):
        nvidia = NVIDIAAdvances()
        gpu = nvidia.get_gpu('blackwell_b300')
        assert gpu is not None
        assert gpu.tensor_cores == 592
        assert gpu.process_node == '5nm EUV'

    def test_hopper_h100_no_fp4(self):
        nvidia = NVIDIAAdvances()
        gpu = nvidia.get_gpu('hopper_h100')
        assert gpu is not None
        assert gpu.fp4_performance_pflops == 0

    def test_compare_to_hyba(self):
        nvidia = NVIDIAAdvances()
        hyba = {'tensor_cores': 8192, 'fp4_eflops': 500, 'memory_tb': 512,
                'bandwidth_pbs': 2, 'streaming_processors': 65536}
        result = nvidia.compare_to_hyba('rubin_r100', hyba)
        assert 'ratios' in result
        assert result['ratios']['tensor_cores'] > 1

    def test_compare_nonexistent_gpu(self):
        nvidia = NVIDIAAdvances()
        result = nvidia.compare_to_hyba('nonexistent', {})
        assert 'error' in result

    def test_get_nonexistent_gpu(self):
        nvidia = NVIDIAAdvances()
        assert nvidia.get_gpu('nonexistent') is None

    def test_get_specs(self):
        nvidia = NVIDIAAdvances()
        specs = nvidia.get_specs()
        assert 'gpus_modelled' in specs
        assert len(specs['gpus_modelled']) == 3

    def test_power_ratings_plausible(self):
        nvidia = NVIDIAAdvances()
        for gpu in nvidia.get_all_gpus():
            assert 100 < gpu.power_watts < 2000

    def test_all_gpus_have_features(self):
        nvidia = NVIDIAAdvances()
        for gpu in nvidia.get_all_gpus():
            assert len(gpu.features) > 0


class TestAppleAdvances:
    """Part 15: Apple Silicon architecture tests."""

    def test_all_chips_loaded(self):
        apple = AppleAdvances()
        chips = apple.get_all_chips()
        names = [c.name for c in chips]
        assert 'Apple M5 Ultra' in names
        assert 'Apple M5 Max' in names
        assert len(chips) == 2

    def test_m5_ultra_specs(self):
        apple = AppleAdvances()
        chip = apple.get_chip('m5_ultra')
        assert chip is not None
        assert chip.cpu_cores == 32
        assert chip.gpu_cores == 160
        assert chip.neural_engine_cores == 32
        assert chip.unified_memory_gb == 512
        assert chip.process_node == '3nm EUV'

    def test_m5_max_specs(self):
        apple = AppleAdvances()
        chip = apple.get_chip('m5_max')
        assert chip is not None
        assert chip.cpu_cores == 16
        assert chip.gpu_cores == 80
        assert chip.unified_memory_gb == 128

    def test_compare_to_hyba(self):
        apple = AppleAdvances()
        hyba = {'tensor_cores': 8192, 'memory_tb': 512, 'bandwidth_pbs': 2,
                'int8_tops': 500e6, 'fp16_eflops': 15}
        result = apple.compare_to_hyba('m5_ultra', hyba)
        assert 'ratios' in result
        assert result['chip'] == 'Apple M5 Ultra'

    def test_neural_engine_tops(self):
        apple = AppleAdvances()
        chip = apple.get_chip('m5_ultra')
        assert chip.int8_performance_tops > 0

    def test_chips_have_features(self):
        apple = AppleAdvances()
        for chip in apple.get_all_chips():
            assert 'Unified Memory Architecture' in chip.features

    def test_power_ratings_plausible(self):
        apple = AppleAdvances()
        for chip in apple.get_all_chips():
            assert 50 < chip.power_watts < 1000

    def test_get_specs(self):
        apple = AppleAdvances()
        specs = apple.get_specs()
        assert 'chips_modelled' in specs
        assert 'unified_memory' in specs

    def test_get_nonexistent_chip(self):
        apple = AppleAdvances()
        assert apple.get_chip('nonexistent') is None


class TestHPAdvances:
    """Part 16: HP/HPE enterprise computing tests."""

    def test_all_systems_loaded(self):
        hp = HPAdvances()
        systems = hp.get_all_systems()
        names = [s.name for s in systems]
        assert 'HPE Cray EX4000' in names
        assert 'HPE Superdome Flex' in names
        assert len(systems) == 2

    def test_cray_ex4000_specs(self):
        hp = HPAdvances()
        system = hp.get_system('cray_ex4000')
        assert system is not None
        assert system.cores_per_node == 2048
        assert system.interconnect_bandwidth_tbps == 4.0
        assert system.cooling_type == 'Direct Liquid Cooling'
        assert 'Slingshot Interconnect' in system.features

    def test_superdome_flex_specs(self):
        hp = HPAdvances()
        system = hp.get_system('superdome_flex')
        assert system is not None
        assert system.cores_per_node == 1024
        assert system.process_node == '5nm EUV'
        assert 'Mission-Critical Computing' in system.features

    def test_compare_to_hyba(self):
        hp = HPAdvances()
        hyba = {'streaming_processors': 65536, 'memory_tb': 512,
                'bandwidth_pbs': 2, 'fp64_eflops': 2.5, 'fp32_eflops': 5}
        result = hp.compare_to_hyba('cray_ex4000', hyba)
        assert 'ratios' in result
        assert result['system'] == 'HPE Cray EX4000'

    def test_memory_driven_computing(self):
        hp = HPAdvances()
        for system in hp.get_all_systems():
            assert 'Memory-Driven Computing' in system.features

    def test_direct_liquid_cooling(self):
        hp = HPAdvances()
        for system in hp.get_all_systems():
            assert 'Direct Liquid Cooling' in system.features

    def test_get_specs(self):
        hp = HPAdvances()
        specs = hp.get_specs()
        assert 'systems_modelled' in specs
        assert 'cooling_efficiency' in specs

    def test_get_nonexistent_system(self):
        hp = HPAdvances()
        assert hp.get_system('nonexistent') is None

    def test_power_ratings_plausible(self):
        hp = HPAdvances()
        for system in hp.get_all_systems():
            assert 10 < system.power_kw < 1000
