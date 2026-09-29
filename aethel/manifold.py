"""Prime storage manifold — topological tensor store with self-healing.

Tensors are committed under a pv-lattice integer anchor (in [0, 89]) that
must satisfy the Cassini invariant.  Payloads are folded by Zeckendorf
compression into sparse topology, persisted into the Galois prime
substrate, and integrity-pinned by the SHA-256 digest recorded at ingest.
Reads digest-verify, attempt one self-heal from a redundant copy, and
re-verify before returning bytes.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

from .constants import DIM, PHI, SQRT5
from .costs import OverheadMeter, container_bytes, metered
from .gpu import TensorCoreGPU_Context
from .primes import GaloisPrimeSubstrate
from .zeckendorf import (
    PUNCH_MANIFOLD_COMPUTE,
    apply_zeckendorf_compression,
    reverse_zeckendorf_expansion,
    sparse_from_blocks,
)


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


class SelfHealingSubstrate:
    def __init__(self, manifold: "PrimeStorageManifold"):
        self.manifold = manifold
        self.heal_log: List[Dict[str, Any]] = []

    def trigger(self, corrupted_node: TopologicalTensor) -> Optional[str]:
        """Repair a corrupted node in place from a verified redundant copy.

        Candidate copies, in order: the node's sparse Zeckendorf topology,
        the prime-exponent substrate (``uuid_index``), and any raw payload
        still attached.  A copy is trusted only when its SHA-256 matches the
        digest committed at ingest.  Returns the node uuid on repair, else
        None after logging an ``unrecoverable`` event.
        """
        valid_anchor = (
            self._find_nearest_valid(corrupted_node.integer_anchor)
            if corrupted_node.integer_anchor is not None
            else None
        )

        candidates: List[tuple] = []
        if corrupted_node.sparse_topology:
            sparse = sparse_from_blocks(
                corrupted_node.sparse_topology,
                getattr(corrupted_node, "total_bytes", 0),
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
        """Nearest anchor inside the 90-slot manifold domain.

        ``CassiniVerifier.verify`` is a theorem identity that holds for
        every fresh input, so it cannot select anything; the real
        constraint on an anchor is the manifold's own domain ``[0, 90)``.
        """
        for offset in range(1, 100):
            for candidate in (anchor - offset, anchor + offset):
                if 0 < candidate < 90:
                    return candidate
        return anchor


class GeodesicNavigator:
    def __init__(self, manifold: "PrimeStorageManifold"):
        self.manifold = manifold
        self.hop_count = 0  # hops used by the current/last query
        self.total_hops = 0  # lifetime hops across all queries

    def query(self, search_vector: np.ndarray) -> Optional[bytes]:
        current = self.manifold.get_root_node()
        target_anchor = self._project_to_pv_lattice(search_vector)
        max_hops = 1000  # per-query budget; hop_count resets each query
        self.hop_count = 0
        while current.integer_anchor != target_anchor and self.hop_count < max_hops:
            self.hop_count += 1
            self.total_hops += 1
            next_anchor = self._steepest_gradient(current.integer_anchor, target_anchor)
            next_node = self.manifold.get_by_anchor(next_anchor)
            if next_node is None:
                next_node = self.manifold.expand_manifold(next_anchor)
            if not 0 <= next_node.integer_anchor < 90:
                self.manifold.self_healing.trigger(next_node)
            current = next_node
        return self.manifold.read_payload(current)

    def _project_to_pv_lattice(self, v: np.ndarray) -> int:
        norm_sq = sum(PHI ** -(i + 1) * v[i] ** 2 for i in range(min(len(v), DIM)))
        return int(round(np.sqrt(norm_sq))) % 90

    def batch_project(self, vectors: np.ndarray) -> np.ndarray:
        """Project a batch of search vectors to pv-lattice anchors.

        Dispatches punch 0x15 (manifold_compute) to the bound OpenCL device
        when the manifold has a usable punch host; otherwise runs the
        identical NumPy computation and reports "cpu".  Either way the
        backend that ran is recorded in ``manifold.stage_evidence["index"]``.
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
            try:
                res = host.run_punch_batch(PUNCH_MANIFOLD_COMPUTE, n=n, in_float=in_float)
            except NotImplementedError:
                # 0x15 is not in OpenClPunchHost's opcode set (0x02/0x1C);
                # fall through to the identical CPU computation instead
                # of crashing with PunchUnsupported.
                pass
            else:
                norm_sq = res["float"].reshape(n, DIM)[:, 0]
                anchors = np.rint(np.sqrt(np.maximum(norm_sq, 0.0))).astype(np.int64) % 90
                self.manifold.stage_evidence["index"] = getattr(
                    host, "last_dispatch_backend", "opencl"
                )
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
        """32-face frame geodesic query with Lucas-15 attractor bias.

        Uses the Pathfinder for 11-D navigation, then falls back to the
        original 1-D bisection ``query()`` if the pathfinder is unavailable.
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


class PrimeStorageManifold:
    def __init__(
        self,
        gpu: TensorCoreGPU_Context,
        n_primes: int = 25,
        punch_host=None,
        require_gpu: bool = False,
    ):
        self.gpu = gpu
        self.punch_host = (
            punch_host if punch_host is not None else getattr(gpu, "punch_host", None)
        )
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
        self._costs = OverheadMeter()

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

    @metered("manifold.measure_throughput")
    def measure_throughput(
        self, n_payloads: int = 64, payload_size: int = 128
    ) -> Dict[str, float]:
        """Measure encode/decode round-trip throughput on the bound backend."""
        payloads = [os.urandom(payload_size) for _ in range(n_payloads)]
        t0 = time.perf_counter()
        sparses = [
            apply_zeckendorf_compression(p, host=self.punch_host) for p in payloads
        ]
        t1 = time.perf_counter()
        decoded = [
            reverse_zeckendorf_expansion(s, host=self.punch_host) for s in sparses
        ]
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

    @metered("manifold.ingest")
    def ingest_sync(
        self,
        payload: bytes,
        curvature: ManifoldCurvature,
        sector: ManifoldSector = ManifoldSector.P_VS_NP,
    ) -> str:
        self._tick += 1
        self._costs.record_bytes("manifold.ingest", len(payload))
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
        data_array = np.frombuffer(
            payload[: DIM * 4].ljust(DIM * 4, b"\x00"), dtype=np.float32
        )
        tensor.integer_anchor = self.gpu.project_and_collapse_pv(data_array, pv_root)
        self.stage_evidence["index"] = self.gpu.projection_backend

        # CassiniVerifier.verify is a theorem identity on fresh values, so
        # it can never fail; the real ingest gate is the 90-slot domain.
        if not 0 <= tensor.integer_anchor < 90:
            raise RuntimeError("anchor outside the 90-slot manifold domain")

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
        return [
            self.tensors[u] for u in self.anchor_index.get(anchor, []) if u in self.tensors
        ]

    def decode_payload(self, tensor: TopologicalTensor) -> Optional[bytes]:
        if tensor.raw_payload:
            return tensor.raw_payload
        if tensor.sparse_topology:
            sparse = sparse_from_blocks(
                tensor.sparse_topology, getattr(tensor, "total_bytes", 0)
            )
            data = reverse_zeckendorf_expansion(sparse, host=self.punch_host)
            self.stage_evidence["decode"] = self._host_backend()
            return data
        return None

    @metered("manifold.read_payload")
    def read_payload(self, tensor: TopologicalTensor) -> Optional[bytes]:
        """Decode with integrity: digest-verify, repair once, re-verify.

        Returns None when no copy of the payload verifies against the digest
        committed at ingest.
        """
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

    @metered("manifold.query")
    def query(self, search_vector: np.ndarray) -> Optional[bytes]:
        return self.geodesic.query(search_vector)

    def structural_bytes(self) -> int:
        """Measured structural memory: tensors + triple-redundant payload
        copies (raw payload, Zeckendorf sparse topology, prime-substrate
        commit) — a floor, not RSS."""
        tensors = container_bytes(self.tensors)
        payloads = sum(
            (len(t.raw_payload) if t.raw_payload else 0)
            + container_bytes(t.sparse_topology or {})
            for t in self.tensors.values()
        )
        return tensors + payloads + container_bytes(self.anchor_index)

    def overhead_report(self) -> Dict[str, Any]:
        """Measured CPU/wall cost per manifold op plus structural memory."""
        return {
            "operations": self._costs.snapshot(),
            "structural_bytes": self.structural_bytes(),
            "total_cpu_ns": self._costs.total_cpu_ns,
            "truth": "measured",
        }

    def stats(self) -> Dict[str, Any]:
        return {
            "total_tensors": len(self.tensors),
            "flat_tensors": len(self.flat_storage),
            "anchor_index_size": len(self.anchor_index),
            "prime_substrate": self.curved_storage.stats(),
            "heal_events": len(self.self_healing.heal_log),
            "geodesic_hops": self.geodesic.hop_count,
            "geodesic_total_hops": self.geodesic.total_hops,
            "overhead_bytes": self.structural_bytes(),
        }
