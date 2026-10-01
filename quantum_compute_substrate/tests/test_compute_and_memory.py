"""Tests for the compute engine and memory hierarchy."""

import numpy as np
from quantum_compute_substrate.compute_engine import ComputeEngine
from quantum_compute_substrate.memory_hierarchy import QuantumMemoryHierarchy
from quantum_compute_substrate.phi_tensor_core import FoldState, PHI


class TestComputeEngine:
    def test_initialization(self):
        engine = ComputeEngine(num_cores=4, core_dim=512, seed=42)
        assert engine.num_cores == 4
        assert len(engine.cores) == 4

    def test_parallel_tensor_product(self):
        engine = ComputeEngine(num_cores=4, core_dim=512, seed=42)
        a = FoldState(np.ones(32, dtype=np.complex128), 0, 32)
        b = FoldState(np.ones(32, dtype=np.complex128), 0, 32)
        results = engine.parallel_tensor_product([a, b, a, b], [a, b, a, b])
        assert len(results) == 4
        for r in results:
            assert r.dim == 1024  # 32 * 32

    def test_linpack_benchmark(self):
        engine = ComputeEngine(num_cores=4, core_dim=512, seed=42)
        result = engine.linpack_benchmark(matrix_size=128)
        assert result["measured_flops"] > 0
        assert result["measured_gflops"] > 0
        assert result["verified"]
        assert result["residual"] < 1e-6

    def test_matmul_benchmark(self):
        engine = ComputeEngine(num_cores=4, core_dim=512, seed=42)
        result = engine.matmul_benchmark(matrix_size=128)
        assert result["measured_flops"] > 0
        assert result["verified"]

    def test_measured_flops_after_operations(self):
        engine = ComputeEngine(num_cores=4, core_dim=512, seed=42)
        a = FoldState(np.ones(32, dtype=np.complex128), 0, 32)
        b = FoldState(np.ones(32, dtype=np.complex128), 0, 32)
        engine.parallel_tensor_product([a, a, a, a], [b, b, b, b])
        assert engine.measured_flops() > 0

    def test_get_specs(self):
        engine = ComputeEngine(num_cores=4, core_dim=512, seed=42)
        specs = engine.get_specs()
        assert specs["num_cores"] == 4
        assert "measured_gflops" in specs
        assert specs["architecture_target_cores"] == 8192


class TestMemoryHierarchy:
    def test_initialization(self):
        mem = QuantumMemoryHierarchy(register_cap=64, sram_cap=256, l2_cap=1024, hbm_cap=4096)
        assert len(mem.tiers) == 4
        assert mem.register.depth == 0
        assert mem.sram.depth == 1
        assert mem.l2.depth == 2
        assert mem.hbm.depth == 3

    def test_compression_factors(self):
        mem = QuantumMemoryHierarchy()
        assert abs(mem.register.compression_factor - 1.0) < 1e-10
        assert abs(mem.sram.compression_factor - PHI) < 1e-10
        assert abs(mem.l2.compression_factor - PHI**2) < 1e-10
        assert abs(mem.hbm.compression_factor - PHI**3) < 1e-10

    def test_store_and_load_register(self):
        mem = QuantumMemoryHierarchy()
        data = np.ones(64, dtype=np.complex128) / 8
        state = FoldState(data, 0, 64)
        assert mem.store("test", state, "register")
        loaded = mem.load("test", "register")
        assert loaded is not None
        assert np.allclose(loaded.data, data)

    def test_store_and_load_sram_with_folding(self):
        mem = QuantumMemoryHierarchy()
        data = np.random.default_rng(42).standard_normal(1024) + 1j * np.random.default_rng(
            43
        ).standard_normal(1024)
        state = FoldState(data, 0, 1024)
        assert mem.store("test", state, "sram")
        loaded = mem.load("test", "sram")
        assert loaded is not None
        # Folded data has smaller dimension
        assert loaded.dim == 1024  # unfolded back

    def test_promote_and_demote(self):
        mem = QuantumMemoryHierarchy()
        data = np.random.default_rng(42).standard_normal(256) + 1j * np.random.default_rng(
            43
        ).standard_normal(256)
        state = FoldState(data, 0, 256)
        mem.store("test", state, "hbm")
        assert mem.promote("test", "hbm", "l2")
        assert mem.load("test", "l2") is not None

    def test_stream_benchmark(self):
        mem = QuantumMemoryHierarchy()
        result = mem.stream_benchmark(array_size=10000, trials=10)
        assert result["copy_bandwidth_gbps"] > 0
        assert result["triad_bandwidth_gbps"] > 0

    def test_fold_integrity_test(self):
        mem = QuantumMemoryHierarchy()
        result = mem.fold_integrity_test(dim=1024, depths=[0, 1, 2, 3])
        assert len(result["results"]) == 4
        # Depth 0 should be lossless
        assert result["results"][0]["lossless"]
        # Higher depths should have increasing error
        errors = [r["relative_error"] for r in result["results"]]
        assert errors[1] >= errors[0]

    def test_get_specs(self):
        mem = QuantumMemoryHierarchy()
        specs = mem.get_specs()
        assert len(specs["tiers"]) == 4
        assert "architecture_target" in specs
        assert specs["architecture_target"]["hbm4"] == "512 TB"
