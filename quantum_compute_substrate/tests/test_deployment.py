"""Tests for deployment and validation."""

from quantum_compute_substrate.system import QuantumGPUSystem
from quantum_compute_substrate.deployment import (
    QuantumGPUDeployment,
    PerformanceValidation,
    PerformanceTargets,
)


class TestPerformanceTargets:
    def test_defaults(self):
        t = PerformanceTargets()
        assert t.fp64_target_eflops == 2.5
        assert t.fp16_target_eflops == 15.0
        assert t.int8_target_eflops == 500.0
        assert t.memory_bandwidth_target_pbs == 2.0
        assert t.power_target_mw == 1.2
        assert t.tensor_cores_target == 8192
        assert t.qubits_target == 4096
        assert t.neural_params_target == 10**12


class TestPerformanceValidation:
    def test_validate(self):
        # Create mock benchmark results
        benchmarks = {
            "linpack": {"measured_gflops": 10.0, "verified": True},
            "matmul": {"measured_gflops": 80.0, "verified": True},
            "memory_bandwidth": {"triad_bandwidth_gbps": 20.0},
            "grover_search": {"found": True, "speedup_ratio": 10.7},
            "error_correction": {"small_lattice": {"correction_rate": 1.0, "all_corrected": True}},
            "neural_network": {
                "training_result": {"parameter_count": 2162, "loss_reduction_pct": 84.1}
            },
        }
        specs = {"system_name": "test"}
        validator = PerformanceValidation(benchmarks, specs)
        result = validator.validate()
        assert "validation" in result
        assert "all_passed" in result
        assert "honest_assessment" in result
        # Targets should NOT be met (we're on test hardware)
        assert not result["all_passed"]

    def test_fp64_validation(self):
        benchmarks = {
            "linpack": {"measured_gflops": 10.0},
            "memory_bandwidth": {},
            "grover_search": {},
            "error_correction": {},
            "neural_network": {},
        }
        validator = PerformanceValidation(benchmarks, {})
        result = validator.validate()
        fp64 = result["validation"]["FP64"]
        assert not fp64["passed"]  # 10 GFLOPS << 2.5 EFLOPS
        assert "gap" in fp64


class TestQuantumGPUDeployment:
    def test_deployment_initializes(self):
        system = QuantumGPUSystem(num_cores=4, core_dim=512, lattice_size=4, nn_dims=[8, 16, 4])
        deployment = QuantumGPUDeployment(system)
        assert deployment.system is system
        assert deployment.power is not None

    def test_deployment_runs(self):
        system = QuantumGPUSystem(num_cores=4, core_dim=512, lattice_size=4, nn_dims=[8, 16, 4])
        deployment = QuantumGPUDeployment(system)
        report = deployment.deploy()
        assert report["status"] == "OPERATIONAL_RESEARCH_PROTOTYPE"
        assert "benchmarks" in report
        assert "validation" in report
        assert "power" in report
        assert "gpu_comparison" in report
