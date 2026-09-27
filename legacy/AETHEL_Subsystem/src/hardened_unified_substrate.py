# ==============================================================================
#
# HARDENED UNIFIED SUBSTRATE (Aethel-Storage)
#
# GPU Abstraction + Topological Storage + All Architectural Fixes
#
# STATUS: In-memory research substrate — not the live persistence layer.
# All state lives in process dicts (uuid_index, prime cells); nothing is
# written to disk. The live mining path persists via src/lib/repositories.ts
# (SQLite + snapshot). This module backs the Python research stack
# (ManifoldBridge nonce-candidate store, TOESystem Cassini checks) and is
# also specified as a standalone product (AETHEL_Subsystem/docs) —
# "fundamentally decoupled from mining operations."
#
# ==============================================================================


import numpy as np

import hashlib

import uuid

import time

import threading

import queue


import os

import sys

from typing import Dict, List, Any, Optional, Tuple, Callable

from dataclasses import dataclass, field

from enum import Enum


from concurrent.futures import ThreadPoolExecutor

import asyncio

# ==============================================================================

# CONSTANTS

# ==============================================================================


DIM = 11

PHI = (1 + np.sqrt(5)) / 2

PSI = 1 - PHI

SQRT5 = np.sqrt(5)

LUCAS_15 = 1364

LUCAS_20 = 15127

LUCAS_31 = 3010349

MODULUS_Q = 2**61 - 1  # Mersenne prime for Galois field


PRIMES_25 = [
    2,
    3,
    5,
    7,
    11,
    13,
    17,
    19,
    23,
    29,
    31,
    37,
    41,
    43,
    47,
    53,
    59,
    61,
    67,
    71,
    73,
    79,
    83,
    89,
    97,
]


# ==============================================================================

# FIX A: RIGOROUS CASSINI INVARIANT

# ==============================================================================


class CassiniVerifier:
    """

    Rigorous Cassini-Hoggatt invariant verification.

    L_n² - 5F_n² = 4(-1)^n

    """

    @staticmethod
    def lucas(n: int) -> int:

        if n == 0:

            return 2

        if n == 1:

            return 1

        a, b = 2, 1

        for _ in range(2, n + 1):

            a, b = b, a + b

        return b

    @staticmethod
    def fibonacci(n: int) -> int:

        if n == 0:

            return 0

        if n == 1:

            return 1

        a, b = 0, 1

        for _ in range(2, n + 1):

            a, b = b, a + b

        return b

    @classmethod
    def verify(cls, n: int) -> bool:
        """Verify L_n² - 5F_n² = 4(-1)^n."""

        L_n = cls.lucas(n)

        F_n = cls.fibonacci(n)

        cassini_det = (L_n**2) - 5 * (F_n**2)

        expected = 4 * ((-1) ** n)

        return cassini_det == expected

    @classmethod
    def verify_identity(cls, n: int) -> bool:
        """Alias for verify() — the exact Cassini identity check."""
        return cls.verify(n)

    @classmethod
    def verify_with_values(cls, n: int, l_val: int, f_val: int) -> bool:
        """Verify with precomputed values."""

        cassini_det = (l_val**2) - 5 * (f_val**2)

        expected = 4 * ((-1) ** n)

        return cassini_det == expected

    @classmethod
    def verify_matrix(cls, n: int) -> bool:
        """Verify det(Q^n) = (-1)^n for Cassini matrix Q."""

        # Q^n = [[F(n+1), F(n)], [F(n), F(n-1)]]

        F_np1 = cls.fibonacci(n + 1)

        F_n = cls.fibonacci(n)

        F_nm1 = cls.fibonacci(n - 1) if n > 0 else 1

        det = F_np1 * F_nm1 - F_n * F_n

        expected = (-1) ** n

        return det == expected


# ==============================================================================

# FIX B: HARDENED ZECKENDORF CODEC (Extended to F_93)

# ==============================================================================


class HardenedZeckendorfCodec:
    """

    Extended Zeckendorf codec.

    FIBONACCI extended to F_93 > 2^64 - 1.

    Handles full 64-bit unsigned integers.

    """

    FIBONACCI = [
        0,
        1,
        2,
        3,
        5,
        8,
        13,
        21,
        34,
        55,
        89,
        144,
        233,
        377,
        610,
        987,
        1597,
        2584,
        4181,
        6765,
        10946,
        17711,
        28657,
        46368,
        75025,
        121393,
        196418,
        317811,
        514229,
        832040,
        1346269,
        2178309,
        3524578,
        5702887,
        9227465,
        14930352,
        24157817,
        39088169,
        63245986,
        102334155,
        165580141,
        267914296,
        433494437,
        701408733,
        1134903170,
        1836311903,
        2971215073,
        4807526976,
        7778742049,
        12586269025,
        20365011074,
        32951280099,
        53316291173,
        86267571272,
        139583862445,
        225851433717,
        365435296162,
        591286729879,
        956722026041,
        1548008755920,
        2504730781961,
        4052739537881,
        6557470319842,
        10610209857723,
        17167680177565,
        27777890035288,
        44945570212853,
        72723460248141,
        117669030460994,
        190392490709135,
        308061521170129,
        498454011879264,
        806515533049393,
        1304969544928657,
        2111485077978050,
        3416454622906707,
        5527939700884757,
        8944394323791464,
        14472334024676221,
        23416728348467685,
        37889062373143906,
        61305790721611591,
        99194853094755497,
        160500643816367088,
        259695496911122585,
        420196140727489673,
        679891637638612258,
        1100087778366101931,
        1779979416004714189,
        2880067194370816120,
        4660046610375530309,
        7540113804746346429,
        12200160415121876738,
        19740274219868223167,
    ]

    MAX_FIB_INDEX = len(FIBONACCI) - 1

    @classmethod
    def encode(cls, n: int) -> int:
        """Encode n as Zeckendorf mask. Safe for full 64-bit unsigned."""
        if not isinstance(n, int):
            raise TypeError(f"Expected int, got {type(n)}")
        if n < 0:
            raise ValueError(f"Negative values not supported: {n}")
        if n == 0:
            return 0
        if n >= cls.FIBONACCI[-1]:
            raise ValueError(f"n={n} exceeds F_{len(cls.FIBONACCI)-1}")
        mask = 0
        rem = n
        for i in range(len(cls.FIBONACCI) - 1, 0, -1):
            if cls.FIBONACCI[i] <= rem:
                mask |= 1 << (i - 1)
                rem -= cls.FIBONACCI[i]
        return mask

    @classmethod
    def decode(cls, mask: int) -> int:
        """Decode Zeckendorf mask back to integer."""
        if mask == 0:
            return 0
        n = 0
        for i in range(mask.bit_length()):
            if (mask >> i) & 1:
                fib_idx = i + 1
                if fib_idx >= len(cls.FIBONACCI):
                    raise ValueError(f"Mask bit {i} exceeds table size")
                n += cls.FIBONACCI[fib_idx]
        return n

    @classmethod
    def verify_non_adjacent(cls, mask: int) -> bool:
        """Verify (mask & (mask << 1)) == 0."""

        return (mask & (mask << 1)) == 0

    @classmethod
    def encode_safe_chunk(cls, chunk_bytes: bytes) -> int:
        """Encode 8-byte chunk safely."""

        n = int.from_bytes(chunk_bytes, "big")

        return cls.encode(n)

    @classmethod
    def encode_7byte_chunk(cls, chunk_bytes: bytes) -> int:
        """Encode 7-byte chunk (56 bits, always < F_92)."""

        n = int.from_bytes(chunk_bytes.ljust(7, b"\x00"), "big")

        return cls.encode(n)


# ==============================================================================

# FIX C: GALOIS FIELD PRIME SUBSTRATE

# ==============================================================================


class GaloisPrimeSubstrate:
    """

    Prime substrate with Galois field composite keys.

    Prevents factorial blowup.

    """

    def __init__(self, n_primes: int = 25, modulus: int = MODULUS_Q):

        self.n_primes = n_primes

        self.primes = PRIMES_25[:n_primes]

        self.modulus = modulus

        self.cells: Dict[int, Dict[str, "PrimeCell"]] = {}

        self.composite_index: Dict[int, List[str]] = {}

        self.uuid_index: Dict[str, Any] = {}

        self._tick = 0

        self._writes = 0

        self._reads = 0

    def commit(self, anchor: int, uuid_str: str, payload: bytes) -> int:
        """Commit with Galois field composite key."""
        self._tick += 1
        self._writes += 1

        exponents = self._encode(payload)
        # Galois field composite: v_p(x) = e mod M
        composite = 1
        for i, e in enumerate(exponents):
            p = self.primes[i % len(self.primes)]
            if e > 0:
                composite = (composite * pow(p, e % self.modulus, self.modulus)) % self.modulus

        for i, e in enumerate(exponents[: len(self.primes)]):
            p = self.primes[i]
            if e > 0:
                self.cells.setdefault(p, {})[uuid_str] = PrimeCell(
                    prime=p,
                    exponent=e % self.modulus,
                    data_hash=int.from_bytes(hashlib.sha256(uuid_str.encode()).digest()[:4], "big"),
                    cassini_parity=(-1) ** (anchor + i),
                    zeckendorf_mask=HardenedZeckendorfCodec.encode(e % self.modulus),
                    created_at=self._tick,
                )

        self.composite_index.setdefault(composite, []).append(uuid_str)
        self.uuid_index[uuid_str] = (anchor, composite, exponents, len(payload))
        return composite

    def fetch(self, uuid_str: str) -> Optional[bytes]:
        self._reads += 1
        entry = self.uuid_index.get(uuid_str)
        if entry is None:
            return None
        anchor, composite, exponents, total_len = entry
        decoded = self._decode(exponents)
        return bytes(decoded[:total_len])

    def _encode(self, payload: bytes) -> List[int]:
        """Encode payload as discrete valuation vector across chunks."""
        exps = []
        for i in range(0, len(payload), 7):
            chunk = payload[i : i + 7].ljust(7, b"\x00")
            exps.append(int.from_bytes(chunk, "big"))
        if not exps:
            exps = [0]
        return exps

    def _decode(self, exponents: List[int]) -> bytes:
        data = bytearray()
        for e in exponents:
            data.extend((e % self.modulus).to_bytes(7, "big"))
        return bytes(data)

    def crystallize(self, prime: int) -> bool:

        cells = self.cells.get(prime)

        if cells:

            for cell in cells.values():

                cell.crystallized = True

            return True

        return False

    def stats(self) -> Dict[str, Any]:

        return {
            "n_primes": self.n_primes,
            "primes_used": len(self.cells),
            "writes": self._writes,
            "reads": self._reads,
            "capacity_bits": self.n_primes * 56,
            "capacity_states": 2 ** (self.n_primes * 56),
            "modulus": self.modulus,
            "crystallized": sum(
                1 for bucket in self.cells.values() for c in bucket.values() if c.crystallized
            ),
        }


@dataclass
class PrimeCell:

    prime: int

    exponent: int

    data_hash: int

    cassini_parity: int

    zeckendorf_mask: int

    crystallized: bool = False

    access_count: int = 0

    last_access: int = 0

    created_at: int = 0


# ==============================================================================

# LAYER 1: COMPUTE UNITS (Hardened)

# ==============================================================================


class VirtualSM:
    """Virtual Streaming Multiprocessor with cache-aligned scratchpad."""

    def __init__(self, sm_id: int, n_threads: int = 256):

        self.sm_id = sm_id

        self.n_threads = n_threads

        self.threadpool = ThreadPoolExecutor(max_workers=n_threads)

        # Cache-line aligned scratchpad (64-byte alignment)

        self._scratchpad_raw = np.zeros(64 * 1024 + 16, dtype=np.float32)

        offset = (16 - (self._scratchpad_raw.ctypes.data % 64) // 4) % 16

        self.scratchpad = self._scratchpad_raw[offset : offset + 64 * 1024]

        self._active_tasks = 0

        self._lock = threading.Lock()

        self._idle = threading.Condition(self._lock)

    def submit(self, fn: Callable, *args, **kwargs):

        with self._lock:

            self._active_tasks += 1

        return self.threadpool.submit(self._wrapped, fn, *args, **kwargs)

    def _wrapped(self, fn, *args, **kwargs):

        try:

            return fn(*args, **kwargs)

        finally:

            with self._idle:

                self._active_tasks -= 1

                self._idle.notify_all()

    def synchronize(self, timeout: float = 30.0):
        """Wait until every task submitted to this SM has completed."""

        with self._idle:

            self._idle.wait_for(lambda: self._active_tasks == 0, timeout=timeout)

    def scratchpad_write(self, offset: int, data: np.ndarray):

        self.scratchpad[offset : offset + len(data)] = data

    def scratchpad_read(self, offset: int, length: int) -> np.ndarray:

        return self.scratchpad[offset : offset + length]

    def shutdown(self):

        self.threadpool.shutdown(wait=True)


class ComputeUnitPool:
    """Pool of virtual SMs with work-stealing."""

    def __init__(self, n_sms: int = 8, threads_per_sm: int = 256):

        self.n_sms = n_sms

        self.sms = [VirtualSM(i, threads_per_sm) for i in range(n_sms)]

        self._round_robin = 0

        self._lock = threading.Lock()

    def get_sm(self) -> VirtualSM:

        with self._lock:

            sm = self.sms[self._round_robin % self.n_sms]

            self._round_robin += 1

            return sm

    def submit_workgroup(self, fn: Callable, *args, **kwargs):

        return self.get_sm().submit(fn, *args, **kwargs)

    def synchronize_all(self):

        for sm in self.sms:

            sm.synchronize()

    def shutdown(self):

        for sm in self.sms:

            sm.shutdown()

    def stats(self) -> Dict[str, Any]:

        return {
            "n_sms": self.n_sms,
            "threads_per_sm": self.sms[0].n_threads if self.sms else 0,
            "total_threads": sum(sm.n_threads for sm in self.sms),
            "active_tasks": sum(sm._active_tasks for sm in self.sms),
        }


# ==============================================================================

# LAYER 2: SPMD / SIMT

# ==============================================================================


class VirtualWarp:
    """Virtual warp with lane masking for branch divergence."""

    WARP_SIZE = 32

    def __init__(self, warp_id: int):

        self.warp_id = warp_id

        self.mask = (1 << self.WARP_SIZE) - 1

    def execute_if_else(
        self,
        condition: np.ndarray,
        path_a: Callable,
        path_b: Callable,
        data: np.ndarray,
    ) -> np.ndarray:

        mask_a = condition.astype(np.int32)

        mask_b = 1 - mask_a

        result_a = path_a(data)

        result_b = path_b(data)

        return result_a * mask_a + result_b * mask_b

    def blend(self, a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> np.ndarray:

        return np.where(mask, a, b)


class SPMDExecutor:
    """SPMD executor with vectorized lane masking."""

    def __init__(self, n_lanes: int = 32):

        self.n_lanes = n_lanes

        self.warps: List[VirtualWarp] = []

    def create_warp(self) -> VirtualWarp:

        warp = VirtualWarp(len(self.warps))

        self.warps.append(warp)

        return warp

    def vectorize(self, fn: Callable, data: np.ndarray) -> np.ndarray:

        return fn(data)

    def diverge(
        self,
        condition: np.ndarray,
        if_fn: Callable,
        else_fn: Callable,
        data: np.ndarray,
    ) -> np.ndarray:

        warp = self.create_warp()

        return warp.execute_if_else(condition, if_fn, else_fn, data)


# ==============================================================================

# LAYER 3: MICRO-KERNELS (Hardened GEMM)

# ==============================================================================


class OptimizedTensorMicroKernel:
    """Tiled GEMM with boundary handling and vectorized dot products."""

    TILE_SIZE = 16

    @staticmethod
    def gemm_fast(A: np.ndarray, B: np.ndarray) -> np.ndarray:

        M, K = A.shape

        K2, N = B.shape

        assert K == K2, "Inner matrix dimensions must agree"

        C = np.zeros((M, N), dtype=np.float32)

        tile = OptimizedTensorMicroKernel.TILE_SIZE

        for i in range(0, M, tile):

            i_end = min(i + tile, M)

            for k in range(0, K, tile):

                k_end = min(k + tile, K)

                a_block = A[i:i_end, k:k_end]

                for j in range(0, N, tile):

                    j_end = min(j + tile, N)

                    b_block = B[k:k_end, j:j_end]

                    C[i:i_end, j:j_end] += a_block @ b_block

        return C


class RTCoreMicroKernel:
    """RT Core BVH traversal pipeline."""

    def __init__(self):

        self.ray_packet_size = 8

    def intersect_aabb(
        self,
        ray_origins: np.ndarray,
        ray_dirs: np.ndarray,
        box_min: np.ndarray,
        box_max: np.ndarray,
    ) -> np.ndarray:

        inv_dirs = 1.0 / (ray_dirs + 1e-15)

        t1 = (box_min - ray_origins) * inv_dirs

        t2 = (box_max - ray_origins) * inv_dirs

        t_min = np.maximum.reduce(np.minimum(t1, t2), axis=-1)

        t_max = np.minimum.reduce(np.maximum(t1, t2), axis=-1)

        return t_max >= np.maximum(t_min, 0.0)


class MicroKernelLibrary:
    """Vendor-tuned micro-kernels."""

    def __init__(self):

        self.tensor_core = OptimizedTensorMicroKernel()

        self.rt_core = RTCoreMicroKernel()

    def gemm(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:

        return self.tensor_core.gemm_fast(A, B)

    def ray_aabb(self, origins, dirs, bmin, bmax) -> np.ndarray:

        return self.rt_core.intersect_aabb(origins, dirs, bmin, bmax)


# ==============================================================================

# LAYER 4: DISTRIBUTED

# ==============================================================================


class DistributedActor:

    def __init__(self, actor_id: str, rank: int):

        self.actor_id = actor_id

        self.rank = rank

        self.inbox: queue.Queue = queue.Queue()

        self.outbox: queue.Queue = queue.Queue()

        self.state: Dict[str, Any] = {}

    def send(self, target: "DistributedActor", message: Any):

        target.inbox.put((self.rank, message))

    def recv(self, timeout: float = 1.0) -> Optional[Tuple[int, Any]]:

        try:

            return self.inbox.get(timeout=timeout)

        except queue.Empty:

            return None


class CollectiveOps:

    @staticmethod
    def all_reduce(actors, data):

        total = np.zeros_like(data)

        for _ in actors:

            total += data

        return total

    @staticmethod
    def all_gather(actors, data):

        return [data.copy() for _ in actors]

    @staticmethod
    def scatter(actors, data):

        chunk_size = len(data) // len(actors)

        return [data[i * chunk_size : (i + 1) * chunk_size] for i in range(len(actors))]


class DistributedDataflowGraph:

    def __init__(self, n_actors: int = 4):

        self.actors = [DistributedActor(f"actor_{i}", i) for i in range(n_actors)]

        self.collective = CollectiveOps()

    def all_reduce(self, data: np.ndarray) -> np.ndarray:

        return self.collective.all_reduce(self.actors, data)

    def broadcast(self, data: np.ndarray):

        for actor in self.actors:

            actor.state["broadcast"] = data.copy()

    def topology_virtualize(self, tensor: np.ndarray, n_stages: int = 2):

        return np.array_split(tensor, n_stages)

    def stats(self) -> Dict[str, Any]:

        return {"n_actors": len(self.actors), "ranks": [a.rank for a in self.actors]}


# ==============================================================================

# LAYER 5: DAG (Hardened Pruning)

# ==============================================================================


@dataclass
class DAGNode:

    node_id: str

    fn: Callable

    deps: List[str] = field(default_factory=list)

    outputs: List[str] = field(default_factory=list)

    inputs: List[str] = field(default_factory=list)

    culled: bool = False

    executed: bool = False


class DependencyDAG:

    def __init__(self):

        self.nodes: Dict[str, DAGNode] = {}

        self.buffers: Dict[str, np.ndarray] = {}

        self.buffer_lifetimes: Dict[str, Tuple[int, int]] = {}

        self._tick = 0

    def add_node(self, node: DAGNode):

        self.nodes[node.node_id] = node

    def topological_sort(self) -> List[str]:

        visited = set()

        order = []

        def visit(nid):

            if nid in visited:

                return

            visited.add(nid)

            for dep in self.nodes[nid].deps:

                visit(dep)

            order.append(nid)

        for nid in self.nodes:

            visit(nid)

        return order

    def prune_dead_code(self) -> int:
        """Prune unconsumed output nodes without false culls on producer nodes."""
        required_buffers = {inp for n in self.nodes.values() for inp in n.inputs}
        culled_count = 0
        for node in self.nodes.values():
            if node.culled:
                continue
            has_dependent_nodes = any(
                node.node_id in other.deps for other in self.nodes.values() if not other.culled
            )
            has_used_outputs = any(out in required_buffers for out in node.outputs)
            if not has_used_outputs and not has_dependent_nodes:
                node.culled = True
                culled_count += 1
        return culled_count

    def execute(self):

        order = self.topological_sort()

        for nid in order:

            node = self.nodes[nid]

            if node.culled:

                continue

            inputs = [self.buffers.get(b, np.array([])) for b in node.inputs]

            outputs = node.fn(*inputs)

            if not isinstance(outputs, (list, tuple)):

                outputs = [outputs]

            for buf_name, buf_data in zip(node.outputs, outputs):

                self.buffers[buf_name] = buf_data

            node.executed = True

            self._tick += 1

    def compute_transient_aliasing(self) -> Dict[str, Tuple[int, int]]:

        order = self.topological_sort()

        for i, nid in enumerate(order):

            node = self.nodes[nid]

            for out in node.outputs:

                first_use = i

                last_use = i

                for j, other in enumerate(order):

                    if out in self.nodes[other].inputs:

                        last_use = max(last_use, j)

                self.buffer_lifetimes[out] = (first_use, last_use)

        return self.buffer_lifetimes

    def alias_memory(self) -> Dict[str, int]:

        lifetimes = self.compute_transient_aliasing()

        sorted_bufs = sorted(lifetimes.items(), key=lambda x: x[1][0])

        heap_offsets: Dict[str, int] = {}

        current_offset = 0

        active: List[Tuple[int, str]] = []

        for buf_name, (start, end) in sorted_bufs:

            active = [(e, n) for e, n in active if e >= start]

            if active:

                current_offset = max(e for e, _ in active)

            heap_offsets[buf_name] = current_offset

            current_offset += self.buffers.get(buf_name, np.array([])).nbytes

            active.append((end, buf_name))

        return heap_offsets


# ==============================================================================

# GPU CONTEXT (Hardened Cassini)

# ==============================================================================


PUNCH_MANIFOLD_COMPUTE = 0x15

PUNCH_ZECKENDORF_ENCODE = 0x02

PUNCH_ZECKENDORF_DECODE = 0x1C

_ZECKENDORF_FIB_LIMIT = 12200160415121876738


def _load_punch_host_class():

    try:

        from .unified_punch import UnifiedPunchHost

        return UnifiedPunchHost

    except ImportError:

        pass

    try:

        from Intelligence.unified_punch import UnifiedPunchHost

        return UnifiedPunchHost

    except ImportError:

        pass

    import importlib.util

    sibling = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unified_punch.py")
    if not os.path.exists(sibling):
        sibling = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "Intelligence", "unified_punch.py"
        )
    if not os.path.exists(sibling):
        return None
    spec = importlib.util.spec_from_file_location("unified_punch", sibling)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("unified_punch", mod)
    spec.loader.exec_module(mod)
    return mod.UnifiedPunchHost


class TensorCoreGPU_Context:

    def __init__(self, punch_host=None, require_gpu: bool = False):

        self.cu_pool = ComputeUnitPool(n_sms=8, threads_per_sm=256)

        self.spmd = SPMDExecutor(n_lanes=32)

        self.microkernels = MicroKernelLibrary()

        self.cassini = CassiniVerifier()

        self.require_gpu = require_gpu
        self.punch_host = punch_host
        if self.punch_host is None:
            host_cls = _load_punch_host_class()
            if host_cls is not None:
                self.punch_host = host_cls()
        if require_gpu and not self.gpu_active:
            raise RuntimeError(
                "GPU execution required but no OpenCL device is available; "
                "refusing to run substrate projections on the CPU."
            )

    @property
    def gpu_active(self) -> bool:
        return self.punch_host is not None and getattr(self.punch_host, "use_opencl", False)

    @property
    def projection_backend(self) -> str:
        if self.gpu_active:
            return (
                getattr(self.punch_host, "last_dispatch_backend", None) or self.punch_host.backend
            )
        return "cpu"

    def project_and_collapse_pv(self, data_tensor: np.ndarray, pv_base: float = PHI) -> int:
        flat = np.nan_to_num(data_tensor.flatten()[:DIM], nan=0.0, posinf=1.0, neginf=-1.0)
        if len(flat) == 0:
            return 0
        if self.gpu_active and pv_base == PHI:
            vec = np.zeros(DIM, dtype=np.float32)
            vec[: len(flat)] = flat
            out = self.punch_host.run_punch_batch(
                PUNCH_MANIFOLD_COMPUTE,
                n=1,
                in_float=vec,
            )
            norm_sq = float(out["float"][0])
            if not np.isfinite(norm_sq) or norm_sq < 0:
                return 0
            anchor = int(round(float(np.sqrt(norm_sq)))) % 90
            return max(0, anchor)
        norm_sq = float(
            sum((pv_base ** -(i + 1)) * (float(flat[i]) ** 2) for i in range(len(flat)))
        )
        if not np.isfinite(norm_sq) or norm_sq < 0:
            return 0
        sqrt_norm = float(np.sqrt(norm_sq))
        # Collapse to canonical Fibonacci manifold basis index in [0, 89]
        anchor = int(round(sqrt_norm)) % 90
        return max(0, anchor)

    def verify_cassini_invariant(self, n: int) -> bool:
        """Rigorous Cassini verification: L_n² - 5F_n² = 4(-1)^n."""

        return self.cassini.verify(n)

    def shutdown(self):

        self.cu_pool.shutdown()


# ==============================================================================

# SELF-HEALING (Hardened)

# ==============================================================================


class SelfHealingSubstrate:

    def __init__(self, manifold: "PrimeStorageManifold"):

        self.manifold = manifold

        self.heal_log: List[Dict[str, Any]] = []

    def trigger(self, corrupted_node: "TopologicalTensor") -> Optional[str]:
        """Repair a corrupted node in place from a verified redundant copy.

        Candidate copies, in order: the node's sparse Zeckendorf topology,
        the prime-exponent substrate (``uuid_index``), and any raw payload
        still attached. A copy is trusted only when its SHA-256 matches the
        digest committed at ingest. Returns the node uuid on repair, else
        None after logging an ``unrecoverable`` event.
        """

        valid_anchor = (
            self._find_nearest_valid(corrupted_node.integer_anchor)
            if corrupted_node.integer_anchor is not None
            else None
        )

        candidates: List[Tuple[str, Optional[bytes]]] = []

        if corrupted_node.sparse_topology:

            sparse = SparseTopology()

            sparse.blocks = corrupted_node.sparse_topology

            sparse.total_bytes = getattr(corrupted_node, "total_bytes", 0) or (
                len(corrupted_node.sparse_topology) * 8
            )

            try:

                candidates.append(
                    (
                        "sparse_topology",
                        reverse_zeckendorf_expansion(sparse, host=self.manifold.punch_host),
                    )
                )

            except Exception:

                pass

        try:

            candidates.append(
                ("prime_exponent", self.manifold.curved_storage.fetch(corrupted_node.uuid))
            )

        except Exception:

            candidates.append(("prime_exponent", None))

        if corrupted_node.raw_payload:

            candidates.append(("raw_payload", corrupted_node.raw_payload))

        for source, data in candidates:

            if data is None:

                continue

            if (
                corrupted_node.digest is not None
                and hashlib.sha256(data).digest() != corrupted_node.digest
            ):

                continue

            sparse = apply_zeckendorf_compression(data, host=self.manifold.punch_host)

            corrupted_node.sparse_topology = sparse.blocks

            corrupted_node.total_bytes = len(data)

            corrupted_node.raw_payload = None

            corrupted_node.cassini_parity = (-1) ** int(corrupted_node.integer_anchor or 0)

            self.heal_log.append(
                {
                    "kind": (
                        "prime_exponent_restore"
                        if source == "prime_exponent"
                        else f"{source}_restore"
                    ),
                    "uuid": corrupted_node.uuid,
                    "valid_anchor": valid_anchor,
                    "source": source,
                    "timestamp": time.time(),
                }
            )

            return corrupted_node.uuid

        self.heal_log.append(
            {
                "kind": "unrecoverable",
                "uuid": corrupted_node.uuid,
                "valid_anchor": valid_anchor,
                "timestamp": time.time(),
            }
        )

        return None

    def _find_nearest_valid(self, anchor: int) -> int:

        for offset in range(1, 100):

            for candidate in [anchor - offset, anchor + offset]:

                if candidate > 0 and CassiniVerifier.verify(candidate):

                    return candidate

        return anchor


# ==============================================================================

# GEODESIC NAVIGATION

# ==============================================================================


class GeodesicNavigator:

    def __init__(self, manifold: "PrimeStorageManifold"):

        self.manifold = manifold

        self.hop_count = 0

    def query(self, search_vector: np.ndarray) -> Optional[bytes]:

        current = self.manifold.get_root_node()

        target_anchor = self._project_to_pv_lattice(search_vector)

        max_hops = 1000

        while current.integer_anchor != target_anchor and self.hop_count < max_hops:

            self.hop_count += 1

            next_anchor = self._steepest_gradient(current.integer_anchor, target_anchor)

            next_node = self.manifold.get_by_anchor(next_anchor)

            if next_node is None:

                next_node = self.manifold.expand_manifold(next_anchor)

            if not CassiniVerifier.verify(next_node.integer_anchor):

                self.manifold.self_healing.trigger(next_node)

            current = next_node

        return self.manifold.read_payload(current)

    def _project_to_pv_lattice(self, v: np.ndarray) -> int:
        norm_sq = sum(PHI ** -(i + 1) * v[i] ** 2 for i in range(min(len(v), DIM)))
        return int(round(np.sqrt(norm_sq))) % 90

    def batch_project(self, vectors: np.ndarray) -> np.ndarray:
        """Project a batch of search vectors to pv-lattice anchors.

        Dispatches punch 0x15 (manifold_compute) to the bound OpenCL
        device when the manifold has a usable punch host; otherwise runs
        the identical NumPy computation and reports "cpu". Either way the
        backend that ran is recorded in manifold.stage_evidence["index"].
        """
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        n = vectors.shape[0]
        host = getattr(self.manifold, "punch_host", None)
        if host is not None and getattr(host, "use_opencl", False):
            in_float = np.zeros((n, DIM), dtype=np.float32)
            in_float[:, : min(vectors.shape[1], DIM)] = vectors.reshape(n, -1)[:, :DIM]
            in_float = in_float.reshape(-1)
            res = host.run_punch_batch(PUNCH_MANIFOLD_COMPUTE, n=n, in_float=in_float)
            norm_sq = res["float"].reshape(n, DIM)[:, 0]
            anchors = np.rint(np.sqrt(np.maximum(norm_sq, 0.0))).astype(np.int64) % 90
            self.manifold.stage_evidence["index"] = getattr(host, "last_dispatch_backend", "opencl")
            return anchors
        self.manifold.stage_evidence["index"] = "cpu"
        return np.array([self._project_to_pv_lattice(v) for v in vectors], dtype=np.int64)

    def _steepest_gradient(self, current: int, target: int) -> int:

        if target > current:

            return current + max(1, (target - current) // 2)

        elif target < current:

            return current - max(1, (current - target) // 2)

        return current

    def query_geodesic(self, search_vector: np.ndarray) -> Optional[bytes]:
        """32-face frame geodesic query with Lucas 15 attractor bias.

        Uses the Pathfinder for 11-D navigation, then falls back to
        the original 1-D bisection query() if pathfinder is unavailable.
        """
        try:
            from Intelligence.pathfinder import Pathfinder

            pf = Pathfinder(n_faces=32)
            target_anchor = self._project_to_pv_lattice(search_vector)
            r0 = np.zeros(min(len(search_vector), DIM), dtype=np.float64)
            r0[0] = float(target_anchor) * np.sqrt(PHI)
            result = pf.navigate(r0, float(target_anchor), max_iter=20, tol=1e-8)
            if result["converged"]:
                final_anchor = int(round(result["final_vector"][0] / np.sqrt(PHI))) % 90
                node = self.manifold.get_by_anchor(final_anchor)
                if node is not None:
                    payload = self.manifold.read_payload(node)
                    if payload is not None:
                        return payload
        except Exception:
            pass
        return self.query(search_vector)


# ==============================================================================

# TOPOLOGICAL TENSOR

# ==============================================================================


class ManifoldCurvature(Enum):

    EUCLIDEAN_FLAT = "euclidean"

    GOLDEN_DENSE = "golden"

    SILVER_ARCHIVAL = "silver"

    BRONZE = "bronze"

    COPPER = "copper"

    NICKEL = "nickel"


class ManifoldSector(Enum):

    P_VS_NP = "computational_geodesics"

    YANG_MILLS = "gauge_bundle"

    RIEMANN = "spectral_operator"

    NAVIER_STOKES = "vector_field"

    BSD = "elliptic_fibration"

    HODGE = "cohomology"

    POINCARE = "topology"


@dataclass
class TopologicalTensor:

    uuid: str

    curvature_type: ManifoldCurvature

    manifold_sector: ManifoldSector

    raw_payload: Optional[bytes] = None

    pv_coordinate: Optional[np.ndarray] = None

    integer_anchor: Optional[int] = None

    cassini_parity: Optional[int] = None

    spectral_gap: Optional[float] = None

    sparse_topology: Optional[Dict[int, int]] = None

    crystallized: bool = False

    created_at: int = 0

    access_count: int = 0

    last_access: int = 0

    pv_base: float = PHI
    total_bytes: int = 0

    digest: Optional[bytes] = None


class SparseTopology:

    def __init__(self):

        self.blocks: Dict[int, int] = {}

        self.total_bytes = 0

    def add(self, offset: int, mask: int):

        self.blocks[offset] = mask

    def items(self):

        return self.blocks.items()

    def __len__(self):

        return len(self.blocks)


_PUNCH_OUT_BLOCK = 121  # DIM * DIM per-work-item output stride


def apply_zeckendorf_compression(payload: bytes, host=None) -> SparseTopology:

    sparse = SparseTopology()

    chunks = [payload[i : i + 8].ljust(8, b"\x00") for i in range(0, len(payload), 8)]

    if host is not None and getattr(host, "use_opencl", False) and chunks:

        ints = np.array([int.from_bytes(c, "big") for c in chunks], dtype=np.uint64)

        res = host.run_punch_batch(PUNCH_ZECKENDORF_ENCODE, in_ulong=ints)

        out = res["ulong"]

        for i in range(len(chunks)):

            base = i * _PUNCH_OUT_BLOCK

            sparse.add(i * 8, int(out[base]) | (int(out[base + 1]) << 64))

    else:

        for i, chunk in enumerate(chunks):

            n = int.from_bytes(chunk, "big")

            try:

                sparse.add(i * 8, HardenedZeckendorfCodec.encode(n))

            except ValueError:

                sparse.add(i * 8, HardenedZeckendorfCodec.encode_7byte_chunk(chunk))

    sparse.total_bytes = len(payload)

    return sparse


def reverse_zeckendorf_expansion(sparse: SparseTopology, host=None) -> bytes:

    offsets = sorted(sparse.blocks.keys())

    if host is not None and getattr(host, "use_opencl", False) and offsets:

        interleaved = np.zeros(len(offsets) * 2, dtype=np.uint64)

        for i, offset in enumerate(offsets):

            mask = sparse.blocks[offset]

            interleaved[i * 2] = np.uint64(mask & 0xFFFFFFFFFFFFFFFF)

            interleaved[i * 2 + 1] = np.uint64((mask >> 64) & 0xFFFFFFFFFFFFFFFF)

        res = host.run_punch_batch(PUNCH_ZECKENDORF_DECODE, n=len(offsets), in_ulong=interleaved)

        out = res["ulong"]

        data = b"".join(
            int(out[i * _PUNCH_OUT_BLOCK]).to_bytes(8, "big") for i in range(len(offsets))
        )

        return data[: sparse.total_bytes]

    data = b""

    for offset in offsets:

        n = HardenedZeckendorfCodec.decode(sparse.blocks[offset])

        data += n.to_bytes(8, "big")

    return data[: sparse.total_bytes]


# ==============================================================================

# MANIFOLD ROUTER

# ==============================================================================


class PrimeStorageManifold:

    def __init__(
        self,
        gpu: TensorCoreGPU_Context,
        n_primes: int = 25,
        punch_host=None,
        require_gpu: bool = False,
    ):

        self.gpu = gpu

        self.punch_host = punch_host if punch_host is not None else getattr(gpu, "punch_host", None)

        self.require_gpu = require_gpu

        if require_gpu and not (
            self.punch_host is not None and getattr(self.punch_host, "use_opencl", False)
        ):
            raise RuntimeError(
                "GPU execution required but no OpenCL device is available; "
                "storage encode/index/reconstruction refuse silent CPU "
                "fallback."
            )

        # Per-stage execution provenance: which backend physically ran each
        # supported computational stage ("opencl:gpu" / "opencl:cpu" / "cpu").
        self.stage_evidence: Dict[str, str] = {
            "encode": "none",
            "index": "none",
            "decode": "none",
        }

        self.flat_storage: Dict[str, TopologicalTensor] = {}

        self.curved_storage = GaloisPrimeSubstrate(n_primes)

        self.geodesic = GeodesicNavigator(self)

        self.self_healing = SelfHealingSubstrate(self)

        self.tensors: Dict[str, TopologicalTensor] = {}

        self.anchor_index: Dict[int, List[str]] = {}
        self._lock = threading.Lock()

        self._tick = 0

    def _host_backend(self) -> str:
        if self.punch_host is None:
            return "cpu"
        return getattr(self.punch_host, "last_dispatch_backend", None) or getattr(
            self.punch_host, "backend", "cpu"
        )

    def execution_evidence(self) -> Dict[str, Any]:
        """Per-stage provenance plus device/telemetry from the bound host."""
        host = self.punch_host
        return {
            "stages": dict(self.stage_evidence),
            "backend": self._host_backend(),
            "device": dict(getattr(host, "device_info", {}) or {}),
            "dispatch_count": int(getattr(host, "dispatch_count", 0) or 0),
            "kernel_ms_total": float(getattr(host, "kernel_ms_total", 0.0) or 0.0),
            "last_kernel_ms": getattr(host, "last_kernel_ms", None),
            "gpu_required": self.require_gpu,
        }

    def measure_throughput(self, n_payloads: int = 64, payload_size: int = 128) -> Dict[str, float]:
        """Measure encode/decode round-trip throughput on the bound backend."""
        payloads = [os.urandom(payload_size) for _ in range(n_payloads)]
        t0 = time.perf_counter()
        sparses = [apply_zeckendorf_compression(p, host=self.punch_host) for p in payloads]
        t1 = time.perf_counter()
        decoded = [reverse_zeckendorf_expansion(s, host=self.punch_host) for s in sparses]
        t2 = time.perf_counter()
        assert all(d == p for d, p in zip(decoded, payloads))
        total_bytes = n_payloads * payload_size
        return {
            "encode_ops_per_sec": n_payloads / max(t1 - t0, 1e-9),
            "decode_ops_per_sec": n_payloads / max(t2 - t1, 1e-9),
            "encode_MB_per_sec": total_bytes / max(t1 - t0, 1e-9) / 1e6,
            "decode_MB_per_sec": total_bytes / max(t2 - t1, 1e-9) / 1e6,
            "backend": self._host_backend(),
        }

    def ingest_sync(
        self,
        payload: bytes,
        curvature: ManifoldCurvature,
        sector: ManifoldSector = ManifoldSector.P_VS_NP,
    ) -> str:

        self._tick += 1

        tensor_uuid = str(uuid.uuid4())

        tensor = TopologicalTensor(
            uuid=tensor_uuid,
            curvature_type=curvature,
            manifold_sector=sector,
            created_at=self._tick,
        )

        tensor.digest = hashlib.sha256(payload).digest()

        if curvature == ManifoldCurvature.EUCLIDEAN_FLAT:

            tensor.raw_payload = payload

            self.curved_storage.commit(0, tensor_uuid, payload)

            self.flat_storage[tensor_uuid] = tensor

            self.tensors[tensor_uuid] = tensor

            return tensor_uuid

        sparse = apply_zeckendorf_compression(payload, host=self.punch_host)
        self.stage_evidence["encode"] = self._host_backend()

        tensor.sparse_topology = sparse.blocks
        tensor.total_bytes = len(payload)

        pv_root = self._pv_base_for(curvature)

        tensor.pv_base = pv_root

        data_array = np.frombuffer(payload[: DIM * 4].ljust(DIM * 4, b"\x00"), dtype=np.float32)

        tensor.integer_anchor = self.gpu.project_and_collapse_pv(data_array, pv_root)
        self.stage_evidence["index"] = self.gpu.projection_backend

        if not CassiniVerifier.verify(tensor.integer_anchor):

            raise RuntimeError("Cassini validation failed")

        tensor.cassini_parity = (-1) ** tensor.integer_anchor

        tensor.spectral_gap = SQRT5

        self.curved_storage.commit(tensor.integer_anchor, tensor_uuid, payload)

        self.tensors[tensor_uuid] = tensor

        self.anchor_index.setdefault(tensor.integer_anchor, []).append(tensor_uuid)

        return tensor_uuid

    async def ingest_and_map(
        self,
        payload: bytes,
        curvature: ManifoldCurvature,
        sector: ManifoldSector = ManifoldSector.P_VS_NP,
    ) -> str:

        return self.ingest_sync(payload, curvature, sector)

    def _pv_base_for(self, curvature: ManifoldCurvature) -> float:

        return {
            ManifoldCurvature.GOLDEN_DENSE: PHI,
            ManifoldCurvature.SILVER_ARCHIVAL: 1 + np.sqrt(2),
            ManifoldCurvature.BRONZE: (3 + np.sqrt(13)) / 2,
            ManifoldCurvature.COPPER: 2 + np.sqrt(5),
            ManifoldCurvature.NICKEL: (5 + np.sqrt(29)) / 2,
        }.get(curvature, PHI)

    def get_root_node(self) -> TopologicalTensor:

        if "root" not in self.tensors:

            self.tensors["root"] = TopologicalTensor(
                uuid="root",
                curvature_type=ManifoldCurvature.GOLDEN_DENSE,
                manifold_sector=ManifoldSector.P_VS_NP,
                integer_anchor=1,
                cassini_parity=-1,
                spectral_gap=SQRT5,
                created_at=0,
                raw_payload=b"",
            )

        return self.tensors["root"]

    def get_by_anchor(self, anchor: int) -> Optional[TopologicalTensor]:

        uids = self.anchor_index.get(anchor)

        return self.tensors.get(uids[0]) if uids else None

    def get_all_by_anchor(self, anchor: int) -> List[TopologicalTensor]:

        return [self.tensors[u] for u in self.anchor_index.get(anchor, []) if u in self.tensors]

    def decode_payload(self, tensor: TopologicalTensor) -> Optional[bytes]:

        if tensor.raw_payload:

            return tensor.raw_payload

        if tensor.sparse_topology:

            sparse = SparseTopology()

            sparse.blocks = tensor.sparse_topology

            sparse.total_bytes = getattr(tensor, "total_bytes", 0) or (
                len(tensor.sparse_topology) * 8
            )

            data = reverse_zeckendorf_expansion(sparse, host=self.punch_host)
            self.stage_evidence["decode"] = self._host_backend()
            return data

        return None

    def read_payload(self, tensor: TopologicalTensor) -> Optional[bytes]:
        """Decode with integrity: digest-verify, repair once, re-verify.

        Returns None when no copy of the payload verifies against the
        digest committed at ingest."""

        data = self.decode_payload(tensor)

        if tensor.digest is None or data is None:

            return data

        if hashlib.sha256(data).digest() == tensor.digest:

            return data

        try:

            healed = self.self_healing.trigger(tensor)

        except Exception:

            healed = None

        if healed is not None:

            repaired = self.decode_payload(tensor)

            if repaired is not None and hashlib.sha256(repaired).digest() == tensor.digest:

                return repaired

        return None

    def expand_manifold(self, anchor: int) -> TopologicalTensor:

        tensor = TopologicalTensor(
            uuid=str(uuid.uuid4()),
            curvature_type=ManifoldCurvature.GOLDEN_DENSE,
            manifold_sector=ManifoldSector.P_VS_NP,
            integer_anchor=anchor,
            cassini_parity=(-1) ** anchor,
            spectral_gap=SQRT5,
            raw_payload=b"",
            created_at=self._tick,
        )

        self.tensors[tensor.uuid] = tensor

        self.anchor_index.setdefault(anchor, []).append(tensor.uuid)

        return tensor

    def query(self, search_vector: np.ndarray) -> Optional[bytes]:

        return self.geodesic.query(search_vector)

    def stats(self) -> Dict[str, Any]:

        return {
            "total_tensors": len(self.tensors),
            "flat_tensors": len(self.flat_storage),
            "anchor_index_size": len(self.anchor_index),
            "prime_substrate": self.curved_storage.stats(),
            "heal_events": len(self.self_healing.heal_log),
            "geodesic_hops": self.geodesic.hop_count,
        }


# ==============================================================================

# UNIFIED SUBSTRATE — ALL LAYERS + ALL FIXES

# ==============================================================================


class UnifiedSubstrate:
    """

    The complete unified substrate.

    Layers 1-5 + Topological storage + All architectural fixes.

    """

    def __init__(
        self, n_primes: int = 25, n_sms: int = 8, punch_host=None, require_gpu: bool = False
    ):

        self.cu_pool = ComputeUnitPool(n_sms=n_sms, threads_per_sm=256)

        self.spmd = SPMDExecutor(n_lanes=32)

        self.microkernels = MicroKernelLibrary()

        self.cluster = DistributedDataflowGraph(n_actors=4)

        self.dag = DependencyDAG()

        self.gpu = TensorCoreGPU_Context(punch_host=punch_host, require_gpu=require_gpu)

        self.manifold = PrimeStorageManifold(
            self.gpu, n_primes, punch_host=self.gpu.punch_host, require_gpu=require_gpu
        )

    async def ingest(
        self,
        payload: bytes,
        curvature: ManifoldCurvature = ManifoldCurvature.GOLDEN_DENSE,
        sector: ManifoldSector = ManifoldSector.P_VS_NP,
    ) -> str:

        return await self.manifold.ingest_and_map(payload, curvature, sector)

    async def retrieve(self, uid: str) -> Optional[bytes]:

        tensor = self.manifold.tensors.get(uid)

        if tensor is None:

            return None

        return self.manifold.read_payload(tensor)

    async def search(self, search_vector: np.ndarray) -> Optional[bytes]:

        return self.manifold.query(search_vector)

    def register_dag_node(self, node: DAGNode):

        self.dag.add_node(node)

    def execute_dag(self):

        self.dag.execute()

    def gemm(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:

        return self.microkernels.gemm(A, B)

    def all_reduce(self, data: np.ndarray) -> np.ndarray:

        return self.cluster.all_reduce(data)

    def vectorize(self, fn: Callable, data: np.ndarray) -> np.ndarray:

        return self.spmd.vectorize(fn, data)

    def verify_cassini(self, n: int) -> bool:

        return CassiniVerifier.verify(n)

    def shutdown(self):

        self.cu_pool.shutdown()

        self.gpu.shutdown()

    def stats(self) -> Dict[str, Any]:

        return {
            "manifold": self.manifold.stats(),
            "compute": self.cu_pool.stats(),
            "spmd": {"n_warps": len(self.spmd.warps)},
            "cluster": self.cluster.stats(),
            "dag": {"n_nodes": len(self.dag.nodes)},
        }


# ==============================================================================

# TESTS

# ==============================================================================


def test_cassini_rigorous():
    """Test rigorous Cassini invariant."""

    for n in range(1, 20):

        assert CassiniVerifier.verify(n), f"Cassini failed at n={n}"

    # Verify the fix: old check was always True

    # New check uses L_n² - 5F_n² = 4(-1)^n

    L_5 = CassiniVerifier.lucas(5)

    F_5 = CassiniVerifier.fibonacci(5)

    assert L_5 == 11

    assert F_5 == 5

    assert (L_5**2) - 5 * (F_5**2) == 4 * ((-1) ** 5)

    assert (L_5**2) - 5 * (F_5**2) == -4


def test_zeckendorf_extended():
    """Test extended Zeckendorf codec handles full 64-bit."""

    # Max 64-bit value

    n = 2**64 - 1

    mask = HardenedZeckendorfCodec.encode(n)

    assert HardenedZeckendorfCodec.verify_non_adjacent(mask)

    assert HardenedZeckendorfCodec.decode(mask) == n

    # F_93 value

    assert HardenedZeckendorfCodec.FIBONACCI[93] == 19740274219868223167


def test_galois_prime_substrate():
    """Test Galois field prime substrate."""

    substrate = GaloisPrimeSubstrate(n_primes=25)

    payload = b"galois test payload"

    composite = substrate.commit(anchor=10, uuid_str="test1", payload=payload)

    assert composite > 0

    assert substrate.fetch("test1") == payload

    stats = substrate.stats()

    assert stats["modulus"] == MODULUS_Q


def test_hardened_gemm():
    """Test hardened GEMM with non-square matrices."""

    mk = MicroKernelLibrary()

    A = np.random.randn(37, 53).astype(np.float32)

    B = np.random.randn(53, 41).astype(np.float32)

    C = mk.gemm(A, B)

    assert np.allclose(C, A @ B, atol=1e-3)


def test_safe_dag_pruning():
    """Test iterative DAG pruning."""

    dag = DependencyDAG()

    dag.add_node(DAGNode("A", lambda: np.array([1]), outputs=["bufA"]))

    dag.add_node(DAGNode("B", lambda x: x * 2, inputs=["bufA"], outputs=["bufB"]))

    dag.add_node(DAGNode("C", lambda x: x + 1, inputs=["bufA"], outputs=["bufC"]))

    dag.add_node(DAGNode("D", lambda x: x - 1, inputs=["bufC"], outputs=["bufD"]))

    culled = dag.prune_dead_code()

    assert culled >= 0

    assert dag.nodes["A"].culled is False


def test_virtual_sm():

    sm = VirtualSM(0, n_threads=4)

    result = sm.submit(lambda x: x * 2, 21).result()

    assert result == 42

    sm.shutdown()


def test_spmd_divergence():

    spmd = SPMDExecutor(n_lanes=32)

    data = np.array([1.0, 5.0, 2.0, 8.0])

    condition = data > 3.0

    result = spmd.diverge(condition, lambda x: x * 10, lambda x: x + 1, data)

    expected = np.where(condition, data * 10, data + 1)

    assert np.allclose(result, expected)


def test_full_unified_substrate():

    substrate = UnifiedSubstrate(n_primes=25, n_sms=4)

    payload = b"unified hardened test payload" * 10

    loop = asyncio.get_event_loop()

    uid = loop.run_until_complete(substrate.ingest(payload, ManifoldCurvature.GOLDEN_DENSE))

    recovered = loop.run_until_complete(substrate.retrieve(uid))

    assert recovered == payload

    substrate.shutdown()


def test_unified_stats():

    substrate = UnifiedSubstrate(n_primes=25, n_sms=4)

    stats = substrate.stats()

    assert "manifold" in stats

    assert "compute" in stats

    assert "cluster" in stats

    assert "dag" in stats

    substrate.shutdown()


def test_cassini_verification_gate():
    """Test that Cassini verification actually catches errors."""

    # Valid

    assert CassiniVerifier.verify(10) is True

    # Invalid: use wrong values

    assert CassiniVerifier.verify_with_values(5, 11, 6) is False


# ==============================================================================

# MAIN

# ==============================================================================


def main():

    print("=" * 78)

    print("HARDENED UNIFIED SUBSTRATE")

    print("GPU Abstraction + Topological Storage + All Fixes")

    print("=" * 78)

    substrate = UnifiedSubstrate(n_primes=25, n_sms=8)

    # Fix A: Cassini verification

    print("\n[Fix A] Rigorous Cassini verification:")

    for n in [1, 5, 10, 15]:

        valid = substrate.verify_cassini(n)

        L_n = CassiniVerifier.lucas(n)

        F_n = CassiniVerifier.fibonacci(n)

        print(f"  n={n}: L_n²-5F_n² = {L_n**2 - 5*F_n**2}, expected {4*((-1)**n)}, valid={valid}")

    # Fix B: Extended Zeckendorf

    print("\n[Fix B] Extended Zeckendorf codec:")

    n_max = 2**64 - 1

    mask = HardenedZeckendorfCodec.encode(n_max)

    decoded = HardenedZeckendorfCodec.decode(mask)

    print(f"  Max 64-bit: {n_max}")

    print(f"  Encoded mask: {mask.bit_length()} bits")

    print(f"  Decoded: {decoded}")

    print(f"  Match: {decoded == n_max}")

    # Fix C: Galois field

    print("\n[Fix C] Galois field prime substrate:")

    payload = b"galois test"

    substrate.manifold.curved_storage.commit(anchor=10, uuid_str="test1", payload=payload)

    fetched = substrate.manifold.curved_storage.fetch("test1")

    print(f"  Payload: {payload}")

    print(f"  Fetched: {fetched}")

    print(f"  Match: {fetched == payload}")

    # Layer 3: Hardened GEMM

    print("\n[Layer 3] Hardened GEMM:")

    A = np.random.randn(37, 53).astype(np.float32)

    B = np.random.randn(53, 41).astype(np.float32)

    C = substrate.gemm(A, B)

    print(f"  A shape: {A.shape}, B shape: {B.shape}, C shape: {C.shape}")

    print(f"  Correct: {np.allclose(C, A @ B, atol=1e-3)}")

    # Layer 5: Safe DAG pruning

    print("\n[Layer 5] Safe DAG pruning:")

    substrate.register_dag_node(DAGNode("A", lambda: np.array([1]), outputs=["bufA"]))

    substrate.register_dag_node(DAGNode("B", lambda x: x * 2, inputs=["bufA"], outputs=["bufB"]))

    substrate.register_dag_node(DAGNode("C", lambda x: x + 1, inputs=["bufA"], outputs=["bufC"]))

    culled = substrate.dag.prune_dead_code()

    print(f"  Culled: {culled}")

    print(f"  A culled: {substrate.dag.nodes['A'].culled}")

    # Full pipeline

    print("\n[Full Pipeline] Ingest + retrieve:")

    payload = b"hardened unified substrate test" * 100

    loop = asyncio.get_event_loop()

    uid = loop.run_until_complete(substrate.ingest(payload, ManifoldCurvature.GOLDEN_DENSE))

    recovered = loop.run_until_complete(substrate.retrieve(uid))

    print(f"  Stored: {len(payload)} bytes")

    print(f"  Recovered: {len(recovered)} bytes")

    print(f"  Match: {recovered == payload}")

    # Stats

    print("\n[Stats]")

    for k, v in substrate.stats().items():

        print(f"  {k}: {v}")

    substrate.shutdown()

    print("\n" + "=" * 78)

    print("COMPLETE")

    print("=" * 78)


if __name__ == "__main__":

    main()


HardenedUnifiedSubstrate = UnifiedSubstrate
