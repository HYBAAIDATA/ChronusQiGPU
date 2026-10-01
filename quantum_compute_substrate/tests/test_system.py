"""Tests for the integrated system."""

from quantum_compute_substrate.system import QuantumGPUSystem


class TestQuantumGPUSystem:
    def test_initialization(self):
        system = QuantumGPUSystem(num_cores=4, core_dim=512, lattice_size=4, nn_dims=[8, 16, 4])
        assert system.compute_engine.num_cores == 4
        assert system.error_correction.L == 4
        assert system.neural_network.parameter_count() > 0

    def test_architecture_targets_defined(self):
        system = QuantumGPUSystem(num_cores=4, core_dim=512)
        targets = system.ARCHITECTURE_TARGETS
        assert targets["tensor_cores"] == 8192
        assert targets["qubits"] == 4096
        assert "ExaFLOPS" in targets["fp64_target"]

    def test_diagnostics(self):
        system = QuantumGPUSystem(num_cores=4, core_dim=512, lattice_size=4, nn_dims=[8, 16, 4])
        diag = system.run_diagnostics()
        assert "compute" in diag
        assert "memory" in diag
        assert "error_correction" in diag
        assert "neural_network" in diag

    def test_get_system_specs(self):
        system = QuantumGPUSystem(num_cores=4, core_dim=512, lattice_size=4, nn_dims=[8, 16, 4])
        specs = system.get_system_specs()
        assert specs["claim_lane"] == "MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC)"
        assert "architecture_targets" in specs
        assert "actual_measured" in specs
        assert "honest_assessment" in specs

    def test_full_benchmark_runs(self):
        system = QuantumGPUSystem(num_cores=4, core_dim=512, lattice_size=4, nn_dims=[8, 16, 4])
        results = system.run_full_benchmark()
        assert "tensor_core" in results
        assert "grover_search" in results
        assert "error_correction" in results
        assert "neural_network" in results
        assert "linpack" in results
        assert "matmul" in results
        assert "memory_bandwidth" in results
