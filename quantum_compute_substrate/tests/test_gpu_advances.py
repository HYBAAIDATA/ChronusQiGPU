"""Tests for 2026 GPU advances."""

import numpy as np
from quantum_compute_substrate.gpu_advances_2026 import (
    PrecisionMode, PRECISION_THROUGHPUT, PRECISION_BITS,
    GPUComparisonTable, RUBIN_R100, BLACKWELL_ULTRA_B300, HOPPER_H100,
    HYBA_QUANTUM_TITAN, ALL_GPUS, FP4Precision, SparseTensorCore,
    TransformerEngine, NVLink6Interconnect, ChipletArchitecture,
    HBM4Memory, DynamicPrecisionManager, MIGPartitioning,
    ConfidentialComputing, OpticalInterconnect, TensorMemory,
)


class TestPrecisionMode:
    def test_all_modes_defined(self):
        assert PrecisionMode.FP4
        assert PrecisionMode.FP6
        assert PrecisionMode.FP8
        assert PrecisionMode.BF16
        assert PrecisionMode.FP16
        assert PrecisionMode.TF32
        assert PrecisionMode.FP32
        assert PrecisionMode.FP64

    def test_throughput_multipliers(self):
        assert PRECISION_THROUGHPUT[PrecisionMode.FP4] == 200.0
        assert PRECISION_THROUGHPUT[PrecisionMode.FP64] == 1.0
        assert PRECISION_THROUGHPUT[PrecisionMode.FP4] > PRECISION_THROUGHPUT[PrecisionMode.FP8]

    def test_precision_bits(self):
        assert PRECISION_BITS[PrecisionMode.FP4] == 4
        assert PRECISION_BITS[PrecisionMode.FP64] == 64


class TestGPUComparison:
    def test_all_gpus_defined(self):
        assert len(ALL_GPUS) == 4
        assert HYBA_QUANTUM_TITAN.name == "HYBA Quantum Titan X-Infinity"
        assert RUBIN_R100.name == "NVIDIA Rubin R100"
        assert BLACKWELL_ULTRA_B300.name == "NVIDIA Blackwell Ultra B300"
        assert HOPPER_H100.name == "NVIDIA Hopper H100"

    def test_rubin_specs(self):
        assert RUBIN_R100.process_node_nm == 3
        assert RUBIN_R100.transistor_count_b == 336
        assert RUBIN_R100.memory_type == "HBM4"
        assert RUBIN_R100.memory_capacity_gb == 288
        assert RUBIN_R100.memory_bandwidth_tbs == 22.0
        assert RUBIN_R100.num_sms == 224
        assert RUBIN_R100.num_tensor_cores == 896
        assert RUBIN_R100.tensor_core_gen == 6
        assert RUBIN_R100.transformer_engine_gen == 3
        assert RUBIN_R100.fp4_pflops == 50.0

    def test_hyba_titan_specs(self):
        assert HYBA_QUANTUM_TITAN.num_tensor_cores == 8192
        assert HYBA_QUANTUM_TITAN.num_sms == 65536
        assert HYBA_QUANTUM_TITAN.tdp_watts == 1200000

    def test_comparison_table(self):
        rows = GPUComparisonTable.generate()
        assert len(rows) == 4
        assert all("name" in r for r in rows)


class TestFP4Precision:
    def test_quantize(self):
        x = np.array([0.0, 0.5, 1.0, 2.0, 4.0, -1.0, -3.0], dtype=np.float32)
        q = FP4Precision.quantize(x)
        assert q.shape == x.shape
        assert q[0] == 0.0
        assert q[1] == 0.5

    def test_matmul(self):
        a = np.random.randn(16, 16).astype(np.float32)
        b = np.random.randn(16, 16).astype(np.float32)
        result = FP4Precision.matmul_fp4(a, b)
        assert result.shape == (16, 16)

    def test_throughput_multiplier(self):
        assert FP4Precision.throughput_multiplier() == 200.0


class TestSparseTensorCore:
    def test_apply_sparsity(self):
        m = np.random.randn(8, 8)
        compressed, metadata = SparseTensorCore.apply_2_4_sparsity(m)
        # 64 elements / 4 per group = 16 groups, 2 per group = 32 compressed
        assert len(compressed) == 32
        assert metadata.shape == (16, 2)

    def test_sparse_matmul(self):
        a = np.random.randn(64, 64)
        b = np.random.randn(64, 64)
        result = SparseTensorCore.sparse_matmul(a, b)
        assert "speedup" in result
        assert "relative_error" in result
        assert result["relative_error"] >= 0  # some error from sparsity


class TestTransformerEngine:
    def test_fused_attention(self):
        seq_len, num_heads, head_dim = 32, 4, 16
        q = np.random.randn(seq_len, num_heads, head_dim)
        k = np.random.randn(seq_len, num_heads, head_dim)
        v = np.random.randn(seq_len, num_heads, head_dim)
        te = TransformerEngine(max_seq_len=seq_len, num_heads=num_heads, head_dim=head_dim)
        output = te.fused_attention(q, k, v)
        assert output.shape == (seq_len, num_heads, head_dim)

    def test_fused_ffn(self):
        x = np.random.randn(32, 64)
        w1 = np.random.randn(64, 128)
        w2 = np.random.randn(128, 64)
        te = TransformerEngine()
        output = te.fused_ffn(x, w1, w2)
        assert output.shape == (32, 64)

    def test_precision_switching(self):
        te = TransformerEngine()
        te.set_precision(PrecisionMode.FP4)
        assert te.precision == PrecisionMode.FP4
        assert te.get_throughput_multiplier() == 200.0


class TestNVLink6:
    def test_bandwidth(self):
        nvlink = NVLink6Interconnect(num_gpus=8)
        assert nvlink.aggregate_bandwidth() == 8 * 3.6

    def test_all_reduce_time(self):
        nvlink = NVLink6Interconnect(num_gpus=8)
        t = nvlink.all_reduce_time(1.0)  # 1 GB
        assert t > 0


class TestChipletArchitecture:
    def test_partition(self):
        chiplet = ChipletArchitecture(num_compute_dies=2)
        sizes = chiplet.partition_workload(100)
        assert len(sizes) == 2
        assert sum(sizes) == 100

    def test_bandwidth(self):
        chiplet = ChipletArchitecture(num_compute_dies=2, die_bandwidth_tbs=2.0)
        assert chiplet.total_compute_bandwidth() == 4.0


class TestHBM4Memory:
    def test_capacity(self):
        hbm4 = HBM4Memory(num_stacks=8)
        assert hbm4.total_capacity_gb() == 288

    def test_bandwidth(self):
        hbm4 = HBM4Memory(num_stacks=8)
        assert hbm4.total_bandwidth_tbs() == 22.4  # 8 * 2.8

    def test_improvement_vs_hbm3e(self):
        hbm4 = HBM4Memory()
        assert hbm4.bandwidth_vs_hbm3e() == 2.3


class TestDynamicPrecision:
    def test_select_for_gradient(self):
        dpm = DynamicPrecisionManager()
        mode = dpm.select_precision({"is_gradient": True})
        assert mode == PrecisionMode.FP32

    def test_select_for_low_range(self):
        dpm = DynamicPrecisionManager()
        mode = dpm.select_precision({"dynamic_range": 1.0})
        assert mode == PrecisionMode.FP4

    def test_select_for_high_range(self):
        dpm = DynamicPrecisionManager()
        mode = dpm.select_precision({"dynamic_range": 200.0})
        assert mode == PrecisionMode.BF16


class TestMIGPartitioning:
    def test_create_partition(self):
        mig = MIGPartitioning(total_sms=224)
        assert mig.create_partition("instance1", 56, 36)
        assert mig.create_partition("instance2", 56, 36)

    def test_utilization(self):
        mig = MIGPartitioning(total_sms=224)
        mig.create_partition("instance1", 56, 36)
        assert mig.utilization() > 0


class TestConfidentialComputing:
    def test_attest(self):
        cc = ConfidentialComputing(enabled=True)
        assert cc.attest()
        assert cc.attestation_verified

    def test_encrypt_decrypt(self):
        cc = ConfidentialComputing(enabled=True)
        tensor = np.array([1, 2, 3, 4], dtype=np.int32)
        encrypted = cc.encrypt_tensor(tensor)
        decrypted = cc.decrypt_tensor(encrypted)
        assert np.array_equal(decrypted, tensor)


class TestOpticalInterconnect:
    def test_bandwidth(self):
        oi = OpticalInterconnect(num_links=64)
        assert oi.aggregate_bandwidth() > 0

    def test_latency(self):
        oi = OpticalInterconnect()
        assert oi.latency() > 0


class TestTensorMemory:
    def test_capacity(self):
        tm = TensorMemory(size_kb=512, num_sms=224)
        assert tm.total_capacity_kb == 512 * 224
        assert tm.total_capacity_mb > 0

    def test_store_load(self):
        tm = TensorMemory(size_kb=512, num_sms=1)
        data = np.zeros(10, dtype=np.float32)  # 40 bytes, fits in 512KB
        assert tm.store("test", data)
        loaded = tm.load("test")
        assert loaded is not None
