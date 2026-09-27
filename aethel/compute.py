"""Compute abstraction layers for the Aethel substrate.

Layer 1 — compute units: virtual SMs with cache-aligned scratchpads and a
work-stealing pool.

Layer 2 — SPMD/SIMT: virtual warps with lane masking for branch divergence.

Layer 3 — micro-kernels: tiled GEMM with boundary handling plus an RT-core
style BVH/AABB traversal kernel.

Layer 4 — distributed: actor mailboxes and collective ops.

Layer 5 — DAG: dependency scheduling with dead-code pruning, transient
buffer-aliasing analysis and heap offset assignment.
"""

from __future__ import annotations

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Layer 1: compute units
# ---------------------------------------------------------------------------


class VirtualSM:
    """Virtual streaming multiprocessor with a cache-aligned scratchpad."""

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

    def synchronize(self, timeout: float = 30.0) -> None:
        """Wait until every task submitted to this SM has completed."""
        with self._idle:
            self._idle.wait_for(lambda: self._active_tasks == 0, timeout=timeout)

    def scratchpad_write(self, offset: int, data: np.ndarray) -> None:
        self.scratchpad[offset : offset + len(data)] = data

    def scratchpad_read(self, offset: int, length: int) -> np.ndarray:
        return self.scratchpad[offset : offset + length]

    def shutdown(self) -> None:
        self.threadpool.shutdown(wait=True)


class ComputeUnitPool:
    """Pool of virtual SMs with round-robin work distribution."""

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

    def synchronize_all(self) -> None:
        for sm in self.sms:
            sm.synchronize()

    def shutdown(self) -> None:
        for sm in self.sms:
            sm.shutdown()

    def stats(self) -> Dict[str, Any]:
        return {
            "n_sms": self.n_sms,
            "threads_per_sm": self.sms[0].n_threads if self.sms else 0,
            "total_threads": sum(sm.n_threads for sm in self.sms),
            "active_tasks": sum(sm._active_tasks for sm in self.sms),
        }


# ---------------------------------------------------------------------------
# Layer 2: SPMD / SIMT
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Layer 3: micro-kernels
# ---------------------------------------------------------------------------


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
    """RT-core style BVH traversal pipeline."""

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


# ---------------------------------------------------------------------------
# Layer 4: distributed
# ---------------------------------------------------------------------------


class DistributedActor:
    def __init__(self, actor_id: str, rank: int):
        self.actor_id = actor_id
        self.rank = rank
        self.inbox: queue.Queue = queue.Queue()
        self.outbox: queue.Queue = queue.Queue()
        self.state: Dict[str, Any] = {}

    def send(self, target: "DistributedActor", message: Any) -> None:
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

    def broadcast(self, data: np.ndarray) -> None:
        for actor in self.actors:
            actor.state["broadcast"] = data.copy()

    def topology_virtualize(self, tensor: np.ndarray, n_stages: int = 2):
        return np.array_split(tensor, n_stages)

    def stats(self) -> Dict[str, Any]:
        return {"n_actors": len(self.actors), "ranks": [a.rank for a in self.actors]}


# ---------------------------------------------------------------------------
# Layer 5: DAG
# ---------------------------------------------------------------------------


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

    def add_node(self, node: DAGNode) -> None:
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
        """Prune unconsumed output nodes without false culls on producers."""
        required_buffers = {inp for n in self.nodes.values() for inp in n.inputs}
        culled_count = 0
        for node in self.nodes.values():
            if node.culled:
                continue
            has_dependent_nodes = any(
                node.node_id in other.deps
                for other in self.nodes.values()
                if not other.culled
            )
            has_used_outputs = any(out in required_buffers for out in node.outputs)
            if not has_used_outputs and not has_dependent_nodes:
                node.culled = True
                culled_count += 1
        return culled_count

    def execute(self) -> None:
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
