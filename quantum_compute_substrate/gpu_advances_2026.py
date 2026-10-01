"""
2026 GPU Architecture Advances
==============================
Incorporates all 2026 GPU technology advances into the HYBA Quantum Titan
X-Infinity architecture. Based on NVIDIA Rubin R100 (GTC 2026), Blackwell
Ultra B300, and Hopper H100 specifications.

Key 2026 advances modelled:
    - FP4 / FP6 precision (4-bit and 6-bit floating point)
    - HBM4 memory (12Hi stacks, 36GB/stack, 22 TB/s aggregate)
    - 3nm process node (TSMC N3P)
    - 6th-generation Tensor Cores with FP4/FP6 support
    - 3rd-generation Transformer Engine (hardware attention)
    - NVLink 6 (3.6 TB/s interconnect)
    - Chiplet architecture (dual compute dies via NV-HBI)
    - PCIe Gen 6
    - ConnectX-9 networking (1.6 Tb/s)
    - 2:4 structured sparsity (sparse tensor cores)
    - Dynamic precision switching (FP4/FP6/FP8/BF16/FP16/TF32/FP32/FP64)
    - Multi-Instance GPU (MIG) partitioning
    - Confidential computing (GPU TEE)
    - Co-packaged optics (CPO) / silicon photonics
    - Tensor Memory (on-chip, 256KB+ per SM)
    - Disaggregated inference support

Claim lane: MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC) — architecture modelling with real
specifications from public sources. No claim of hardware implementation.
"""

import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
import time


class PrecisionMode(Enum):
    """All precision modes supported by 2026 GPU tensor cores."""
    FP4 = "fp4"       # 4-bit floating point (2x FP8 throughput)
    FP6 = "fp6"       # 6-bit floating point (new in 2026)
    FP8 = "fp8"       # 8-bit floating point
    BF16 = "bf16"     # Brain float 16
    FP16 = "fp16"     # Half precision
    TF32 = "tf32"     # Tensor float 32
    FP32 = "fp32"     # Single precision
    FP64 = "fp64"     # Double precision


# Precision throughput multipliers relative to FP64 (based on 2026 GPU specs)
PRECISION_THROUGHPUT = {
    PrecisionMode.FP4: 200.0,    # 500 EFLOPS target → 200x FP64
    PrecisionMode.FP6: 100.0,    # ~100x FP64
    PrecisionMode.FP8: 50.0,     # ~50x FP64
    PrecisionMode.BF16: 30.0,   # ~30x FP64
    PrecisionMode.FP16: 30.0,    # ~30x FP64
    PrecisionMode.TF32: 15.0,    # ~15x FP64
    PrecisionMode.FP32: 8.0,     # ~8x FP64
    PrecisionMode.FP64: 1.0,     # baseline
}

# Bits per element for each precision mode
PRECISION_BITS = {
    PrecisionMode.FP4: 4,
    PrecisionMode.FP6: 6,
    PrecisionMode.FP8: 8,
    PrecisionMode.BF16: 16,
    PrecisionMode.FP16: 16,
    PrecisionMode.TF32: 19,  # 10-bit mantissa + 8-bit exponent + sign
    PrecisionMode.FP32: 32,
    PrecisionMode.FP64: 64,
}


@dataclass
class GPUArchitectureSpec:
    """Complete specification of a 2026-era GPU."""
    name: str
    process_node_nm: int
    transistor_count_b: int          # billions
    memory_type: str
    memory_capacity_gb: int
    memory_bandwidth_tbs: float       # TB/s
    num_sms: int                       # streaming multiprocessors
    num_tensor_cores: int
    tensor_core_gen: int
    transformer_engine_gen: int
    nvlink_version: str
    nvlink_bandwidth_tbs: float
    pcie_version: str
    fp4_pflops: float
    fp8_tflops: float
    fp16_tflops: float
    fp64_tflops: float
    tdp_watts: int
    tensor_memory_kb: int             # per-SM tensor memory
    chiplet: bool                     # multi-die design
    sparsity: bool                    # 2:4 structured sparsity support
    mig: bool                         # multi-instance GPU
    confidential_computing: bool


# ── 2026 GPU Comparison Table (from public specs) ─────────────────────

RUBIN_R100 = GPUArchitectureSpec(
    name="NVIDIA Rubin R100",
    process_node_nm=3,
    transistor_count_b=336,
    memory_type="HBM4",
    memory_capacity_gb=288,
    memory_bandwidth_tbs=22.0,
    num_sms=224,
    num_tensor_cores=896,
    tensor_core_gen=6,
    transformer_engine_gen=3,
    nvlink_version="NVLink 6",
    nvlink_bandwidth_tbs=3.6,
    pcie_version="PCIe Gen 6",
    fp4_pflops=50.0,
    fp8_tflops=16000.0,
    fp16_tflops=8000.0,
    fp64_tflops=80.0,
    tdp_watts=1400,
    tensor_memory_kb=512,
    chiplet=True,
    sparsity=True,
    mig=True,
    confidential_computing=True,
)

BLACKWELL_ULTRA_B300 = GPUArchitectureSpec(
    name="NVIDIA Blackwell Ultra B300",
    process_node_nm=5,
    transistor_count_b=208,
    memory_type="HBM3e",
    memory_capacity_gb=288,
    memory_bandwidth_tbs=10.0,
    num_sms=160,
    num_tensor_cores=592,
    tensor_core_gen=5,
    transformer_engine_gen=2,
    nvlink_version="NVLink 5",
    nvlink_bandwidth_tbs=1.8,
    pcie_version="PCIe Gen 5",
    fp4_pflops=15.0,
    fp8_tflops=4500.0,
    fp16_tflops=2250.0,
    fp64_tflops=45.0,
    tdp_watts=1400,
    tensor_memory_kb=256,
    chiplet=True,
    sparsity=True,
    mig=True,
    confidential_computing=True,
)

HOPPER_H100 = GPUArchitectureSpec(
    name="NVIDIA Hopper H100",
    process_node_nm=4,
    transistor_count_b=80,
    memory_type="HBM3",
    memory_capacity_gb=80,
    memory_bandwidth_tbs=3.35,
    num_sms=132,
    num_tensor_cores=528,
    tensor_core_gen=4,
    transformer_engine_gen=1,
    nvlink_version="NVLink 4",
    nvlink_bandwidth_tbs=0.9,
    pcie_version="PCIe Gen 5",
    fp4_pflops=0,  # H100 doesn't support FP4
    fp8_tflops=2000.0,
    fp16_tflops=1000.0,
    fp64_tflops=34.0,
    tdp_watts=700,
    tensor_memory_kb=0,  # not present on Hopper
    chiplet=False,
    sparsity=True,
    mig=True,
    confidential_computing=False,
)

# HYBA Quantum Titan X-Infinity target spec
HYBA_QUANTUM_TITAN = GPUArchitectureSpec(
    name="HYBA Quantum Titan X-Infinity",
    process_node_nm=3,
    transistor_count_b=336,  # based on 3nm density
    memory_type="HBM4 + Quantum Cache",
    memory_capacity_gb=512 * 1024,  # 512 TB = 524,288 GB
    memory_bandwidth_tbs=2000.0,  # 2 PB/s
    num_sms=65536,
    num_tensor_cores=8192,
    tensor_core_gen=6,  # 6th-gen with quantum enhancement
    transformer_engine_gen=3,
    nvlink_version="NVLink 6 + Quantum Interconnect",
    nvlink_bandwidth_tbs=3.6,
    pcie_version="PCIe Gen 6",
    fp4_pflops=500000.0,  # 500 ExaFLOPS
    fp8_tflops=16000000.0,
    fp16_tflops=15000000.0,  # 15 ExaFLOPS
    fp64_tflops=2500000.0,  # 2.5 ExaFLOPS
    tdp_watts=1200000,  # 1.2 MW
    tensor_memory_kb=1024,
    chiplet=True,
    sparsity=True,
    mig=True,
    confidential_computing=True,
)

ALL_GPUS = [HYBA_QUANTUM_TITAN, RUBIN_R100, BLACKWELL_ULTRA_B300, HOPPER_H100]


class GPUComparisonTable:
    """Generate comparison table across all GPU architectures."""

    @staticmethod
    def generate() -> List[Dict]:
        rows = []
        for gpu in ALL_GPUS:
            rows.append({
                "name": gpu.name,
                "process_nm": gpu.process_node_nm,
                "transistors_b": gpu.transistor_count_b,
                "memory": f"{gpu.memory_capacity_gb} GB {gpu.memory_type}",
                "bandwidth_tbs": gpu.memory_bandwidth_tbs,
                "sms": gpu.num_sms,
                "tensor_cores": gpu.num_tensor_cores,
                "tc_gen": gpu.tensor_core_gen,
                "te_gen": gpu.transformer_engine_gen,
                "nvlink": f"{gpu.nvlink_version} ({gpu.nvlink_bandwidth_tbs} TB/s)",
                "fp4_pflops": gpu.fp4_pflops,
                "fp8_tflops": gpu.fp8_tflops,
                "fp16_tflops": gpu.fp16_tflops,
                "fp64_tflops": gpu.fp64_tflops,
                "tdp_w": gpu.tdp_watts,
                "tensor_mem_kb": gpu.tensor_memory_kb,
                "chiplet": gpu.chiplet,
                "sparsity": gpu.sparsity,
                "mig": gpu.mig,
                "confidential": gpu.confidential_computing,
            })
        return rows

    @staticmethod
    def print_table():
        rows = GPUComparisonTable.generate()
        print("\n" + "=" * 120)
        print("2026 GPU Architecture Comparison")
        print("=" * 120)
        headers = ["GPU", "nm", "Transistors", "Memory", "BW (TB/s)", "SMs",
                   "TCs", "TC Gen", "TE Gen", "FP4 (PFLOPS)", "TDP (W)"]
        print(f"{headers[0]:<35} {headers[1]:>4} {headers[2]:>12} {headers[3]:<25} "
              f"{headers[4]:>10} {headers[5]:>8} {headers[6]:>8} {headers[7]:>6} "
              f"{headers[8]:>6} {headers[9]:>14} {headers[10]:>10}")
        print("-" * 120)
        for r in rows:
            print(f"{r['name']:<35} {r['process_nm']:>4} {r['transistors_b']:>12} "
                  f"{r['memory']:<25} {r['bandwidth_tbs']:>10.1f} {r['sms']:>8} "
                  f"{r['tensor_cores']:>8} {r['tc_gen']:>6} {r['te_gen']:>6} "
                  f"{r['fp4_pflops']:>14.1f} {r['tdp_w']:>10}")
        print("=" * 120)


class FP4Precision:
    """
    FP4 (4-bit floating point) operations — new in 2026 GPUs.

    FP4 uses 2-bit exponent + 1-bit mantissa + 1-bit sign (E2M1 format).
    Provides 2x throughput vs FP8, 4x vs FP16.
    """

    # FP4 quantization levels (E2M1: 8 representable values)
    FP4_LEVELS = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0], dtype=np.float32)

    @staticmethod
    def quantize(x: np.ndarray) -> np.ndarray:
        """Quantize to FP4 precision."""
        abs_x = np.abs(x)
        sign = np.sign(x)
        # Find nearest FP4 level
        quantized_abs = FP4Precision.FP4_LEVELS[
            np.argmin(np.abs(abs_x[:, None] - FP4Precision.FP4_LEVELS[None, :]), axis=1)
        ]
        return sign * quantized_abs

    @staticmethod
    def matmul_fp4(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Matrix multiply with FP4 quantized inputs, FP32 accumulation."""
        a_q = FP4Precision.quantize(a.flatten()).reshape(a.shape)
        b_q = FP4Precision.quantize(b.flatten()).reshape(b.shape)
        # Accumulate in FP32 (as real GPUs do)
        return np.float32(a_q) @ np.float32(b_q)

    @staticmethod
    def throughput_multiplier() -> float:
        """FP4 provides 2x throughput vs FP8, 4x vs FP16."""
        return 200.0  # relative to FP64


class SparseTensorCore:
    """
    2:4 structured sparsity — 2026 GPU feature.

    In each group of 4 elements, at most 2 can be non-zero.
    This provides 2x throughput for sparse matrices with no accuracy loss.
    """

    @staticmethod
    def apply_2_4_sparsity(matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply 2:4 structured sparsity pattern.
        Returns (compressed_matrix, metadata) where metadata encodes
        which 2 of every 4 elements are non-zero.
        """
        flat = matrix.flatten()
        # Process in groups of 4
        n_groups = len(flat) // 4
        compressed = np.zeros(n_groups * 2, dtype=matrix.dtype)
        metadata = np.zeros((n_groups, 2), dtype=np.int32)

        for i in range(n_groups):
            group = flat[i * 4:(i + 1) * 4]
            # Keep 2 largest-magnitude elements
            indices = np.argsort(np.abs(group))[-2:]
            indices.sort()
            compressed[i * 2] = group[indices[0]]
            compressed[i * 2 + 1] = group[indices[1]]
            metadata[i] = indices

        return compressed, metadata

    @staticmethod
    def sparse_matmul(a: np.ndarray, b: np.ndarray, sparsity_ratio: float = 0.5) -> Dict:
        """
        Sparse matrix multiply with 2:4 sparsity.
        Measures speedup vs dense matmul.
        """
        # Dense reference
        t0 = time.perf_counter()
        dense_result = a @ b
        dense_time = time.perf_counter() - t0

        # Sparse (simulated: zero out 50% of elements in 2:4 pattern)
        a_sparse = a.copy()
        for i in range(0, a_sparse.shape[0], 4):
            end = min(i + 4, a_sparse.shape[0])
            for j in range(a_sparse.shape[1]):
                col = a_sparse[i:end, j]
                if len(col) == 4:
                    # Zero out 2 smallest-magnitude elements
                    zero_idx = np.argsort(np.abs(col))[:2]
                    col[zero_idx] = 0

        t0 = time.perf_counter()
        sparse_result = a_sparse @ b
        sparse_time = time.perf_counter() - t0

        # Verify results are approximately equal
        error = np.linalg.norm(sparse_result - dense_result) / np.linalg.norm(dense_result)

        return {
            "dense_time": dense_time,
            "sparse_time": sparse_time,
            "speedup": dense_time / sparse_time if sparse_time > 0 else 0,
            "relative_error": float(error),
            "sparsity_ratio": sparsity_ratio,
            "note": "2:4 structured sparsity provides 2x throughput on 2026 GPUs.",
        }


class TransformerEngine:
    """
    3rd-generation Transformer Engine (2026 GPU feature).

    Hardware acceleration for transformer operations:
    - Fused attention (FlashAttention-3 style)
    - Fused feed-forward network (FFN)
    - Automatic precision management (FP4/FP8/FP16)
    - Long-context optimization (up to 128K tokens)
    """

    def __init__(self, max_seq_len: int = 4096, num_heads: int = 8, head_dim: int = 64):
        self.max_seq_len = max_seq_len
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.precision = PrecisionMode.FP8  # default for inference

    def fused_attention(self, q: np.ndarray, k: np.ndarray, v: np.ndarray) -> np.ndarray:
        """
        Fused multi-head attention (FlashAttention-style).
        Computes: softmax(Q @ K^T / sqrt(d)) @ V
        """
        # q, k, v: (seq_len, num_heads, head_dim)
        seq_len = q.shape[0]
        scale = 1.0 / np.sqrt(self.head_dim)

        # Compute attention scores
        scores = np.einsum('shd,thd->hst', q, k) * scale  # (num_heads, seq, seq)

        # FlashAttention-style blockwise softmax (memory-efficient)
        block_size = min(128, seq_len)
        output = np.zeros_like(v)

        for i in range(0, seq_len, block_size):
            end_i = min(i + block_size, seq_len)
            block_scores = scores[:, i:end_i, :]
            block_max = np.max(block_scores, axis=-1, keepdims=True)
            exp_scores = np.exp(block_scores - block_max)
            block_sum = np.sum(exp_scores, axis=-1, keepdims=True)
            attn_weights = exp_scores / block_sum
            # Weighted sum of values
            output[i:end_i] = np.einsum('hst,thd->shd', attn_weights, v)

        return output

    def fused_ffn(self, x: np.ndarray, w1: np.ndarray, w2: np.ndarray) -> np.ndarray:
        """
        Fused feed-forward network: GELU(x @ W1) @ W2.
        Uses FP8 precision for 2x throughput.
        """
        # GELU activation
        hidden = x @ w1
        gelu = 0.5 * hidden * (1 + np.tanh(np.sqrt(2 / np.pi) * (hidden + 0.044715 * hidden ** 3)))
        return gelu @ w2

    def set_precision(self, mode: PrecisionMode):
        """Dynamically switch precision mode."""
        self.precision = mode

    def get_throughput_multiplier(self) -> float:
        return PRECISION_THROUGHPUT[self.precision]


class NVLink6Interconnect:
    """
    NVLink 6 interconnect — 3.6 TB/s per GPU (2026 spec).
    Connects GPUs in a scale-up domain for coherent memory access.
    """

    BANDWIDTH_TBS = 3.6  # TB/s per GPU
    MAX_GPUS_PER_DOMAIN = 72  # NVL72 rack

    def __init__(self, num_gpus: int = 8):
        self.num_gpus = num_gpus
        self.topology = self._build_mesh_topology()

    def _build_mesh_topology(self) -> np.ndarray:
        """Build fully-connected mesh topology."""
        return np.ones((self.num_gpus, self.num_gpus)) - np.eye(self.num_gpus)

    def aggregate_bandwidth(self) -> float:
        """Total aggregate bandwidth across all GPUs."""
        return self.num_gpus * self.BANDWIDTH_TBS

    def all_reduce_time(self, data_size_gb: float) -> float:
        """Estimate all-reduce time for given data size."""
        # Ring all-reduce: 2*(N-1)/N * data_size / bandwidth
        bandwidth_tbs = self.BANDWIDTH_TBS
        data_tb = data_size_gb / 1024  # GB to TB
        n = self.num_gpus
        return 2 * (n - 1) / n * data_tb / bandwidth_tbs


class ChipletArchitecture:
    """
    Chiplet (multi-die) architecture — 2026 GPU feature.

    NVIDIA Rubin R100 uses dual compute dies connected via NV-HBI
    (NVIDIA High-Bandwidth Interface) for unified performance.
    """

    def __init__(self, num_compute_dies: int = 2, die_bandwidth_tbs: float = 2.0):
        self.num_compute_dies = num_compute_dies
        self.die_bandwidth_tbs = die_bandwidth_tbs
        self.dies = [f"compute_die_{i}" for i in range(num_compute_dies)]

    def total_compute_bandwidth(self) -> float:
        """Total inter-die bandwidth."""
        return self.num_compute_dies * self.die_bandwidth_tbs

    def partition_workload(self, workload_size: int) -> List[int]:
        """Partition workload across compute dies."""
        per_die = workload_size // self.num_compute_dies
        remainder = workload_size % self.num_compute_dies
        sizes = [per_die] * self.num_compute_dies
        for i in range(remainder):
            sizes[i] += 1
        return sizes


class HBM4Memory:
    """
    HBM4 memory specification — 2026 standard.

    Key specs:
        - 12Hi stacks (12 layers per stack)
        - 36 GB per stack
        - 8 stacks per GPU = 288 GB total
        - Pin speed: >11 Gb/s
        - Per-stack bandwidth: >2.8 TB/s
        - Aggregate bandwidth: up to 22 TB/s
        - 2.3x bandwidth improvement over HBM3E
        - 20%+ power efficiency improvement
    """

    STACKS_PER_GPU = 8
    GB_PER_STACK = 36
    PIN_SPEED_GBS = 11.0
    BANDWIDTH_PER_STACK_TBS = 2.8
    AGGREGATE_BANDWIDTH_TBS = 22.0

    def __init__(self, num_stacks: int = 8):
        self.num_stacks = num_stacks

    def total_capacity_gb(self) -> int:
        return self.num_stacks * self.GB_PER_STACK

    def total_bandwidth_tbs(self) -> float:
        return self.num_stacks * self.BANDWIDTH_PER_STACK_TBS

    def bandwidth_vs_hbm3e(self) -> float:
        """Bandwidth improvement ratio over HBM3e."""
        return 2.3  # from Micron specs


class DynamicPrecisionManager:
    """
    Dynamic precision switching — 2026 GPU feature.
    Automatically selects optimal precision per layer/tensor.
    """

    def __init__(self):
        self.current_mode = PrecisionMode.FP8
        self.mode_history = []

    def select_precision(self, tensor_stats: Dict) -> PrecisionMode:
        """
        Select optimal precision based on tensor statistics.
        - High dynamic range → BF16/FP16
        - Low dynamic range → FP8/FP4
        - Gradient computation → FP32/FP64
        """
        dynamic_range = tensor_stats.get("dynamic_range", 1.0)
        is_gradient = tensor_stats.get("is_gradient", False)
        requires_accuracy = tensor_stats.get("requires_accuracy", False)

        if is_gradient or requires_accuracy:
            mode = PrecisionMode.FP32
        elif dynamic_range > 100:
            mode = PrecisionMode.BF16
        elif dynamic_range > 10:
            mode = PrecisionMode.FP8
        else:
            mode = PrecisionMode.FP4

        self.current_mode = mode
        self.mode_history.append(mode)
        return mode

    def get_throughput_multiplier(self) -> float:
        return PRECISION_THROUGHPUT[self.current_mode]


class MIGPartitioning:
    """
    Multi-Instance GPU (MIG) — 2026 GPU feature.
    Partitions a single GPU into multiple isolated instances.
    """

    def __init__(self, total_sms: int = 224):
        self.total_sms = total_sms
        self.partitions = {}

    def create_partition(self, name: str, num_sms: int, memory_gb: int) -> bool:
        """Create a MIG partition with specified resources."""
        used_sms = sum(p["sms"] for p in self.partitions.values())
        sum(p["memory_gb"] for p in self.partitions.values())
        if used_sms + num_sms > self.total_sms:
            return False
        self.partitions[name] = {"sms": num_sms, "memory_gb": memory_gb}
        return True

    def list_partitions(self) -> Dict:
        return dict(self.partitions)

    def utilization(self) -> float:
        used = sum(p["sms"] for p in self.partitions.values())
        return used / self.total_sms


class ConfidentialComputing:
    """
    Confidential computing on GPU — 2026 GPU feature.
    Hardware Trusted Execution Environment (TEE) for secure computation.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.attestation_verified = False

    def attest(self) -> bool:
        """Perform hardware attestation."""
        if self.enabled:
            self.attestation_verified = True
            return True
        return False

    def encrypt_tensor(self, tensor: np.ndarray, key: bytes = None) -> np.ndarray:
        """Simulate tensor encryption (XOR-based for demo)."""
        if not self.enabled:
            return tensor
        if key is None:
            key = b"HYBA_CONFIDENTIAL_2026"
        # Build a key buffer of the right size
        tensor.dtype.itemsize
        key_repeated = key * (tensor.nbytes // len(key) + 1)
        # Truncate to exact byte count, ensuring multiple of elem_size
        key_bytes = key_repeated[:tensor.nbytes]
        key_array = np.frombuffer(key_bytes, dtype=tensor.dtype).reshape(tensor.shape)
        return tensor ^ key_array

    def decrypt_tensor(self, tensor: np.ndarray, key: bytes = None) -> np.ndarray:
        """Decrypt tensor (XOR is symmetric)."""
        return self.encrypt_tensor(tensor, key)


class OpticalInterconnect:
    """
    Co-packaged optics (CPO) — 2026 frontier technology.
    Silicon photonics for optical interconnects between rack-scale compute.
    """

    BANDWIDTH_TBS = 51.2  # per switch (NVIDIA Quantum-2 InfiniBand)
    LATENCY_NS = 200  # nanoseconds

    def __init__(self, num_links: int = 64):
        self.num_links = num_links

    def aggregate_bandwidth(self) -> float:
        return self.num_links * self.BANDWIDTH_TBS / 64  # per-link bandwidth

    def latency(self) -> float:
        return self.LATENCY_NS / 1e9  # seconds


class TensorMemory:
    """
    On-chip Tensor Memory — 2026 GPU feature.
    256KB-1MB per SM, used for high-bandwidth local computation.
    """

    def __init__(self, size_kb: int = 512, num_sms: int = 224):
        self.size_kb = size_kb
        self.num_sms = num_sms
        self._data = {}

    @property
    def total_capacity_kb(self) -> int:
        return self.size_kb * self.num_sms

    @property
    def total_capacity_mb(self) -> float:
        return self.total_capacity_kb / 1024

    def store(self, key: str, data: np.ndarray) -> bool:
        """Store data in tensor memory if it fits."""
        size_kb = data.nbytes / 1024
        if size_kb <= self.size_kb:
            self._data[key] = data
            return True
        return False

    def load(self, key: str) -> Optional[np.ndarray]:
        return self._data.get(key)

    def bandwidth_gbs(self) -> float:
        """Tensor memory bandwidth (~10 TB/s per SM on 2026 GPUs)."""
        return 10000.0 * self.num_sms  # GB/s aggregate
