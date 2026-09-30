"""UnifiedSubstrate — all five compute layers plus topological storage."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import numpy as np

from .cassini import CassiniVerifier
from .chronus import ChronusContext
from .compute import (
    ComputeUnitPool,
    DependencyDAG,
    DAGNode,
    DistributedDataflowGraph,
    MicroKernelLibrary,
    SPMDExecutor,
)
from .manifold import ManifoldCurvature, ManifoldSector, PrimeStorageManifold


class UnifiedSubstrate:
    """The complete unified substrate.

    Turing remains the compute substrate; Chronus owns the hardware-facing
    iGPU offering used by the projection/storage path.
    """

    def __init__(
        self,
        n_primes: int = 25,
        n_sms: int = 8,
        punch_host=None,
        require_gpu: bool = False,
    ):
        self.cu_pool = ComputeUnitPool(n_sms=n_sms, threads_per_sm=256)
        self.spmd = SPMDExecutor(n_lanes=32)
        self.microkernels = MicroKernelLibrary()
        self.cluster = DistributedDataflowGraph(n_actors=4)
        self.dag = DependencyDAG()
        self.chronus = ChronusContext(
            punch_host=punch_host,
            require_gpu=require_gpu,
        )
        self.manifold = PrimeStorageManifold(
            self.chronus,
            n_primes,
            punch_host=self.chronus.punch_host,
            require_gpu=require_gpu,
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

    def register_dag_node(self, node: DAGNode) -> None:
        self.dag.add_node(node)

    def execute_dag(self) -> None:
        self.dag.execute()

    def gemm(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        return self.microkernels.gemm(A, B)

    def all_reduce(self, data: np.ndarray) -> np.ndarray:
        return self.cluster.all_reduce(data)

    def vectorize(self, fn: Callable, data: np.ndarray) -> np.ndarray:
        return self.spmd.vectorize(fn, data)

    def verify_cassini(self, n: int) -> bool:
        return CassiniVerifier.verify(n)

    def shutdown(self) -> None:
        self.cu_pool.shutdown()
        self.chronus.shutdown()

    def overhead_report(self) -> Dict[str, Any]:
        """Measured CPU/memory overhead of the substrate's metered layers."""
        return {
            "manifold": self.manifold.overhead_report(),
            "truth": "measured",
        }

    def stats(self) -> Dict[str, Any]:
        return {
            "product": "Chronus",
            "compute_substrate": "Turing",
            "manifold": self.manifold.stats(),
            "compute": self.cu_pool.stats(),
            "spmd": {"n_warps": len(self.spmd.warps)},
            "cluster": self.cluster.stats(),
            "dag": {"n_nodes": len(self.dag.nodes)},
            "overhead": self.overhead_report(),
        }


HardenedUnifiedSubstrate = UnifiedSubstrate
