"""Agentic classical-quantum hybrid controller.

Orchestrates polyhedral solvers alongside quantum and hybrid search
paradigms. The agent's core role is state-space mapping, algorithm
selection based on search-landscape properties, and dispatching tasks to
dedicated hardware or simulators.

Architecture
------------
::

    +------------------------------------------------------------------+
    |                        AGENTIC CONTROLLER                        |
    |  - Tracks Search History & Entropy                               |
    |  - Classifies Energy Landscapes / Topologies                     |
    |  - Dynamically Selects Solver & Allocates Qubits/Threads         |
    +------------------------------------------------------------------+
                                |
          +---------------------+---------------------+
          |                     |                     |
          v                     v                     v
    +----------------+   +---------------+   +-------------------+
    | POLYHEDRAL MAP |   | QUANTUM ENGINES|  | HYBRID SWARM / SA |
    | Dodeca (20-v)  |   | Grover Search  |   | Particle Swarm    |
    | Icosa  (12-v)  |   | Quantum Walks  |   | Simulated Anneal. |
    +----------------+   +---------------+   +-------------------+
          |                     |                     |
          +---------------------+---------------------+
                                |
                                v
    +------------------------------------------------------------------+
    |                      VERIFICATION / ORACLE                       |
    |  - Evaluates Target Constraints (Hash Bit-Depth / Objective)     |
    |  - Feeds Results & Gradients Back to Agent Memory                |
    +------------------------------------------------------------------+

The 32-node dual overlay (icosahedron 12 vertices + dodecahedron 20
vertices) from ``turing_core`` is the polyhedral substrate.  The canonical
nonce path interprets those dual vertices as 32 face normals, partitions the
work interval without gaps, and applies the consensus oracle to every probed
candidate.  The solver taxonomy below remains available for non-consensus
experiments and API compatibility; it is not used to infer gradients or prune
regions of a cryptographic hash search:

- **Quantum Walk** → structured polyhedral network graphs.
- **Grover's Amplitude Amplification** → unstructured, non-linear
  sub-spaces with zero geometric gradient.
- **Quantum Annealing & Tunneling** → rugged energy landscapes with high
  potential barriers.
- **Classical Swarm Intelligence (PSO)** → continuous parameter tuning
  across geometric faces (smooth gradients).

The agent maintains an explicit control loop in working memory:
partition → entropy assessment → job dispatch → feedback & pruning.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: step

from __future__ import annotations

import hashlib
import logging
import math
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .search_crystal import PoincareCassiniSearchEngine

try:
    import turing_core as _turing
except ImportError:  # pragma: no cover
    _turing = None  # type: ignore[assignment]

logger = logging.getLogger("Intelligence.agentic_controller")

PHI = (1 + math.sqrt(5)) / 2
PSI = (1 - math.sqrt(5)) / 2


# ---------------------------------------------------------------------------
# Solver types and landscape classification
# ---------------------------------------------------------------------------


class SolverType(Enum):
    """The available solver paradigms."""

    QUANTUM_WALK = "quantum_walk"
    GROVER_AMPLIFICATION = "grover_amplitude_amplification"
    QUANTUM_ANNEALING = "quantum_annealing"
    PARTICLE_SWARM = "particle_swarm"
    SIMULATED_ANNEALING = "simulated_annealing"
    HYBRID_ENSEMBLE = "hybrid_ensemble_search"
    VERIFIED_EXHAUSTIVE = "verified_exhaustive"


class LandscapeType(Enum):
    """Classified energy landscape topology."""

    SMOOTH_GRADIENT = "smooth_gradient"  # low variance → swarm/SA
    RUGGED_BARRIERS = "rugged_barriers"  # high barriers → annealing
    UNSTRUCTURED_FLAT = "unstructured_flat"  # no gradient → Grover
    STRUCTURED_GRAPH = "structured_graph"  # polyhedral graph → quantum walk


@dataclass
class LandscapeAssessment:
    """Assessment of a sub-domain's energy landscape."""

    landscape_type: LandscapeType
    entropy: float  # Shannon entropy of the nonce distribution
    variance: float  # local variance of hash values
    gradient_magnitude: float  # |∇f| estimate
    barrier_height: float  # max potential barrier estimate
    recommended_solver: SolverType
    qubit_allocation: int  # how many qubits to allocate (if quantum)
    thread_allocation: int  # how many threads (if classical)


# ---------------------------------------------------------------------------
# Polyhedral state-space discretization
# ---------------------------------------------------------------------------


@dataclass
class PolyhedralFace:
    """One face of the polyhedral discretization."""

    face_id: int
    vertices: List[int]  # vertex indices
    centroid: np.ndarray  # centroid in R^3
    normal: np.ndarray  # face normal
    nonce_range: Tuple[int, int]  # [start, end) nonce range mapped to this face
    assessed: Optional[LandscapeAssessment] = None
    pruned: bool = False  # pruned if zero target probability


class PolyhedralMapping:
    """Polyhedral state-space discretization on the 32-node dual overlay.

    The repo's ``turing_core.generate_dual_overlay_frame()`` produces the
    32-node compound frame: 12 icosahedron vertices + 20 dodecahedron
    vertices on S². We use:

    - **Icosahedral mapping (12 vertices / 20 faces)**: coarse-grained
      partitioning. Each face gets a major sub-space or seed parameter.
    - **Dodecahedral mapping (20 vertices / 12 faces)**: dual connectivity.
      Neighboring vertices define short-path state transitions for local
      graph traversal.

    The total nonce search space is partitioned across the 20 icosahedral
    faces, each face getting a contiguous nonce range. The dodecahedral
    adjacency defines the traversal graph for quantum walks.
    """

    def __init__(self, total_nonce_space: int = 1_000_000):
        self.total_space = int(total_nonce_space)
        self.frame = (
            _turing.generate_dual_overlay_frame()
            if _turing is not None
            else [[math.cos(i * PHI), math.sin(i * PHI), 0.0] for i in range(32)]
        )
        # Icosahedron: first 12 vertices of the 32-node frame.
        self.icosahedron_vertices = self.frame[:12]
        # Dodecahedron: next 20 vertices.
        self.dodecahedron_vertices = self.frame[12:]
        # Build the 20 icosahedral faces (each is a triangle of 3 vertices).
        self.faces: List[PolyhedralFace] = self._build_icosahedral_faces()
        # Build dodecahedral adjacency (graph for quantum walks).
        self.adjacency: Dict[int, List[int]] = self._build_dodecahedral_adjacency()

    def _build_icosahedral_faces(self) -> List[PolyhedralFace]:
        """Build the 20 triangular faces of the icosahedron.

        Each face gets a contiguous nonce range from the total search space.
        """
        # The 20 faces of an icosahedron (by vertex index triples).
        # Standard icosahedron face indices.
        face_indices = [
            (0, 1, 2),
            (0, 2, 3),
            (0, 3, 4),
            (0, 4, 5),
            (0, 5, 1),
            (1, 2, 6),
            (2, 3, 7),
            (3, 4, 8),
            (4, 5, 9),
            (5, 1, 10),
            (6, 2, 7),
            (7, 3, 8),
            (8, 4, 9),
            (9, 5, 10),
            (10, 1, 6),
            (6, 7, 11),
            (7, 8, 11),
            (8, 9, 11),
            (9, 10, 11),
            (10, 6, 11),
        ]
        faces: List[PolyhedralFace] = []
        face_size = self.total_space // len(face_indices)
        for i, (a, b, c) in enumerate(face_indices):
            va = np.asarray(self.icosahedron_vertices[a], dtype=float)
            vb = np.asarray(self.icosahedron_vertices[b], dtype=float)
            vc = np.asarray(self.icosahedron_vertices[c], dtype=float)
            centroid = (va + vb + vc) / 3.0
            # Face normal: (vb - va) × (vc - va).
            normal = np.cross(vb - va, vc - va)
            norm = np.linalg.norm(normal)
            if norm > 0:
                normal = normal / norm
            nonce_start = i * face_size
            nonce_end = (i + 1) * face_size if i < len(face_indices) - 1 else self.total_space
            faces.append(
                PolyhedralFace(
                    face_id=i,
                    vertices=[a, b, c],
                    centroid=centroid,
                    normal=normal,
                    nonce_range=(nonce_start, nonce_end),
                )
            )
        return faces

    def _build_dodecahedral_adjacency(self) -> Dict[int, List[int]]:
        """Build the dodecahedral adjacency graph (20 vertices, 3-regular).

        Neighboring vertices define short-path state transitions for local
        graph traversal (quantum walks). The dodecahedron graph is the
        standard 20-vertex 3-regular graph.
        """
        # Standard dodecahedron adjacency (each vertex has 3 neighbors).
        # Vertex indices 0-19 (mapped to dodecahedron_vertices[0:20]).
        adj = {
            0: [1, 4, 5],
            1: [0, 2, 7],
            2: [1, 3, 9],
            3: [2, 4, 11],
            4: [0, 3, 13],
            5: [0, 6, 14],
            6: [5, 7, 16],
            7: [1, 6, 8],
            8: [7, 9, 17],
            9: [2, 8, 10],
            10: [9, 11, 18],
            11: [3, 10, 12],
            12: [11, 13, 19],
            13: [4, 12, 14],
            14: [5, 13, 15],
            15: [14, 16, 19],
            16: [6, 15, 17],
            17: [8, 16, 18],
            18: [10, 17, 19],
            19: [12, 15, 18],
        }
        return adj

    def get_face_for_nonce(self, nonce: int) -> PolyhedralFace:
        """Return the icosahedral face that a nonce maps to."""
        for face in self.faces:
            if face.nonce_range[0] <= nonce < face.nonce_range[1]:
                return face
        return self.faces[-1]

    def get_neighbor_faces(self, face_id: int) -> List[int]:
        """Return the face IDs adjacent to a given face (via shared vertices)."""
        face = self.faces[face_id]
        neighbors: set[int] = set()
        for v in face.vertices:
            for other_id, other in enumerate(self.faces):
                if other_id == face_id:
                    continue
                if v in other.vertices:
                    neighbors.add(other_id)
        return sorted(neighbors)

    def status(self) -> Dict[str, Any]:
        return {
            "n_vertices": len(self.frame),
            "n_icosahedron_vertices": len(self.icosahedron_vertices),
            "n_dodecahedron_vertices": len(self.dodecahedron_vertices),
            "n_faces": len(self.faces),
            "n_adjacency_edges": sum(len(v) for v in self.adjacency.values()) // 2,
            "total_nonce_space": self.total_space,
            "pruned_faces": sum(1 for f in self.faces if f.pruned),
            "assessed_faces": sum(1 for f in self.faces if f.assessed is not None),
        }


# ---------------------------------------------------------------------------
# Agentic controller — the classical-quantum hybrid brain
# ---------------------------------------------------------------------------


@dataclass
class SearchJob:
    """One dispatched search job."""

    job_id: int
    face_id: int
    solver: SolverType
    nonce_range: Tuple[int, int]
    qubits: int
    threads: int
    result_nonce: Optional[int] = None
    hashes_computed: int = 0
    time_elapsed: float = 0.0
    success: bool = False


@dataclass
class ControllerState:
    """The agentic controller's working state."""

    total_jobs_dispatched: int = 0
    total_hashes_computed: int = 0
    total_nonces_found: int = 0
    pruned_faces: int = 0
    solver_usage: Dict[str, int] = field(default_factory=dict)
    search_history: List[SearchJob] = field(default_factory=list)
    entropy_history: List[float] = field(default_factory=list)


class AgenticController:
    """The classical-quantum hybrid controller.

    Coordinates the verified search crystal and retains the experimental
    landscape-dispatch methods for compatibility.

    Canonical control loop:
    1. Partition the interval across all 32 dual face normals.
    2. Rank shards through the 11D Poincare embedding (ordering only).
    3. Traverse each shard with a Cassini-certified full permutation.
    4. Verify every candidate with double-SHA256 and report exact coverage.
    """

    def __init__(
        self,
        total_nonce_space: int = 1_000_000,
        max_qubits: int = 30,
        max_threads: int = 8,
    ):
        self.mapping = PolyhedralMapping(total_nonce_space)
        self._verified_search = PoincareCassiniSearchEngine(total_nonce_space)
        self.max_qubits = min(max_qubits, 30)  # practical simulation limit
        self.max_threads = max_threads
        self.state = ControllerState()
        self._next_job_id = 0
        # The quantum accelerator (iGPU / Turing core via quantum_cuda).
        self._sim = None
        try:
            from core_engine import quantum_cuda

            self._sim = quantum_cuda.create_simulator(0)
        except Exception:  # pragma: no cover
            pass

    # -- 1. Entropy assessment & landscape classification ----------------

    def assess_landscape(
        self,
        face: PolyhedralFace,
        header: bytes,
        target: bytes,
        sample_size: int = 64,
    ) -> LandscapeAssessment:
        """Classify the energy landscape of a polyhedral face.

        Samples ``sample_size`` nonces from the face's range, computes
        their double-SHA256 hashes, and measures:
        - **Entropy** (Shannon entropy of hash bit distribution).
        - **Variance** (local variance of hash values).
        - **Gradient magnitude** (|∇f| — how fast the landscape changes).
        - **Barrier height** (max potential barrier — max-min hash gap).

        Based on these metrics, classifies the landscape and recommends a
        solver.
        """
        start, end = face.nonce_range
        if end <= start:
            return LandscapeAssessment(
                landscape_type=LandscapeType.UNSTRUCTURED_FLAT,
                entropy=0.0,
                variance=0.0,
                gradient_magnitude=0.0,
                barrier_height=0.0,
                recommended_solver=SolverType.GROVER_AMPLIFICATION,
                qubit_allocation=0,
                thread_allocation=1,
            )
        # Sample nonces evenly across the face's range.
        step = max(1, (end - start) // sample_size)
        sample_nonces = list(range(start, end, step))[:sample_size]
        # Compute hashes and measure landscape properties.
        chunk1 = header[:76] if len(header) >= 76 else header + b"\x00" * (76 - len(header))
        bytes(target)
        hash_values: List[int] = []
        bits_set: List[int] = []
        for nonce in sample_nonces:
            nonce_bytes = struct.pack("<I", nonce)
            h = hashlib.sha256(hashlib.sha256(chunk1 + nonce_bytes).digest()).digest()
            # Leading bits as integer (the "energy" — lower is better).
            energy = int.from_bytes(h[::-1], "big")
            hash_values.append(energy)
            bits_set.append(bin(h[0]).count("1"))
        if not hash_values:
            return LandscapeAssessment(
                landscape_type=LandscapeType.UNSTRUCTURED_FLAT,
                entropy=0.0,
                variance=0.0,
                gradient_magnitude=0.0,
                barrier_height=0.0,
                recommended_solver=SolverType.GROVER_AMPLIFICATION,
                qubit_allocation=0,
                thread_allocation=1,
            )
        arr = np.array(hash_values, dtype=float)
        # Shannon entropy of bit distribution.
        p1 = np.mean(bits_set) / 8.0
        p0 = 1.0 - p1
        entropy = 0.0
        if 0 < p1 < 1:
            entropy = -(p1 * math.log2(p1) + p0 * math.log2(p0))
        # Variance.
        variance = float(np.var(arr))
        # Gradient magnitude: average |f(n+1) - f(n)|.
        if len(arr) > 1:
            gradient = float(np.mean(np.abs(np.diff(arr))))
        else:
            gradient = 0.0
        # Barrier height: max - min.
        barrier = float(np.max(arr) - np.min(arr))
        # Classify landscape.
        # Normalise metrics to [0, 1] for comparison.
        max_energy = 2**256
        norm_variance = variance / (max_energy**2) if max_energy > 0 else 0.0
        norm_gradient = gradient / max_energy if max_energy > 0 else 0.0
        norm_barrier = barrier / max_energy if max_energy > 0 else 0.0
        # -- Lucas 15 attractor resonance check --------------------------------
        # If a significant fraction of sampled nonces resonate with the Lucas
        # 15 attractor (L_15 = 1364), classify as structured_graph regardless
        # of the hash landscape metrics.  This reflects the ontology's claim
        # that the golden metric concentrates search near phi-powers.
        try:
            from Intelligence.lucas_attractor import LucasAttractor

            _att = LucasAttractor(n=15)
            resonant = sum(1 for n in sample_nonces if _att.total_score(float(n)) > 0.4)
            if resonant / max(len(sample_nonces), 1) > 0.15:
                landscape_type = LandscapeType.STRUCTURED_GRAPH
                solver = SolverType.QUANTUM_WALK
        except Exception:
            pass  # fall through to hash-based classification

        # Dispatch rules (hash-based classification if Lucas check did not fire):
        # - Structured graph (polyhedral adjacency) → quantum walk.
        # - High barrier / rugged → quantum annealing.
        # - Unstructured flat (low gradient, high entropy) → Grover.
        # - Smooth gradient (low entropy, low variance) → swarm/SA.
        if "landscape_type" not in dir():
            pass  # already classified by Lucas check above
        if norm_barrier > 0.3:
            landscape_type = LandscapeType.RUGGED_BARRIERS
            solver = SolverType.QUANTUM_ANNEALING
        elif norm_gradient < 1e-10 and entropy > 0.95:
            landscape_type = LandscapeType.UNSTRUCTURED_FLAT
            solver = SolverType.GROVER_AMPLIFICATION
        elif norm_variance < 1e-15:
            landscape_type = LandscapeType.SMOOTH_GRADIENT
            solver = SolverType.PARTICLE_SWARM
        elif "solver" not in dir():
            # Default: use the polyhedral graph structure for quantum walk.
            landscape_type = LandscapeType.STRUCTURED_GRAPH
            solver = SolverType.QUANTUM_WALK

        # Qubit allocation: log2(face size), capped at max_qubits.
        face_size = end - start
        qubits = min(self.max_qubits, max(1, int(math.log2(max(face_size, 2)))))
        # Thread allocation: more threads for classical solvers.
        if solver in (SolverType.PARTICLE_SWARM, SolverType.SIMULATED_ANNEALING):
            threads = self.max_threads
        else:
            threads = 1  # quantum solvers run on the simulator
        assessment = LandscapeAssessment(
            landscape_type=landscape_type,
            entropy=entropy,
            variance=variance,
            gradient_magnitude=gradient,
            barrier_height=barrier,
            recommended_solver=solver,
            qubit_allocation=qubits,
            thread_allocation=threads,
        )
        face.assessed = assessment
        self.state.entropy_history.append(entropy)
        return assessment

    # -- 2. Job dispatch -------------------------------------------------

    def dispatch_job(
        self,
        face: PolyhedralFace,
        header: bytes,
        target: bytes,
        solver: Optional[SolverType] = None,
    ) -> SearchJob:
        """Dispatch a search job to the appropriate solver backend.

        The solver is chosen from the face's landscape assessment (or
        overridden by the caller). The job is sent to the quantum_cuda
        iGPU/Turing accelerator for quantum solvers, or run classically
        for swarm/SA.
        """
        if face.pruned:
            return SearchJob(
                job_id=self._next_job_id,
                face_id=face.face_id,
                solver=SolverType.GROVER_AMPLIFICATION,
                nonce_range=face.nonce_range,
                qubits=0,
                threads=0,
                result_nonce=-1,
                success=False,
            )
        if solver is None:
            if face.assessed is None:
                self.assess_landscape(face, header, target)
            solver = (
                face.assessed.recommended_solver
                if face.assessed
                else SolverType.GROVER_AMPLIFICATION
            )
        start, end = face.nonce_range
        num_nonces = end - start
        qubits = face.assessed.qubit_allocation if face.assessed else 1
        threads = face.assessed.thread_allocation if face.assessed else 1
        job = SearchJob(
            job_id=self._next_job_id,
            face_id=face.face_id,
            solver=solver,
            nonce_range=(start, end),
            qubits=qubits,
            threads=threads,
        )
        self._next_job_id += 1
        t0 = time.time()
        # Execute the search.
        winner = -1
        hashes = 0
        if solver in (
            SolverType.GROVER_AMPLIFICATION,
            SolverType.QUANTUM_WALK,
            SolverType.QUANTUM_ANNEALING,
            SolverType.HYBRID_ENSEMBLE,
        ):
            # Quantum solvers: dispatch to the iGPU / Turing core.
            if self._sim is not None:
                winner = self._sim.submit_kernel(
                    "",
                    solver.value,
                    min(num_nonces, 10000),
                    header + b"\x00" * max(0, 80 - len(header)),
                    target,
                    -1,
                )
                hashes = min(num_nonces, 10000)
            else:
                # Fallback: classical scan.
                winner, hashes = self._classical_scan(header, target, start, end)
        elif solver in (SolverType.PARTICLE_SWARM, SolverType.SIMULATED_ANNEALING):
            # Classical solvers: swarm / SA.
            winner, hashes = self._classical_scan(header, target, start, end, threads=threads)
        else:
            winner, hashes = self._classical_scan(header, target, start, end)
        job.time_elapsed = time.time() - t0
        job.result_nonce = winner
        job.hashes_computed = hashes
        job.success = winner >= 0
        # Update controller state.
        self.state.total_jobs_dispatched += 1
        self.state.total_hashes_computed += hashes
        if job.success:
            self.state.total_nonces_found += 1
        self.state.solver_usage[solver.value] = self.state.solver_usage.get(solver.value, 0) + 1
        self.state.search_history.append(job)
        return job

    def _classical_scan(
        self,
        header: bytes,
        target: bytes,
        start: int,
        end: int,
        threads: int = 1,
        max_hashes: int = 10000,
    ) -> Tuple[int, int]:
        """Classical nonce scan (fallback when quantum sim unavailable)."""
        chunk1 = header[:76] if len(header) >= 76 else header + b"\x00" * (76 - len(header))
        target_int = int.from_bytes(bytes(target), "big")
        hashes = 0
        for nonce in range(start, min(end, start + max_hashes)):
            h = hashlib.sha256(hashlib.sha256(chunk1 + struct.pack("<I", nonce)).digest()).digest()
            hashes += 1
            if int.from_bytes(h, "little") <= target_int:
                return nonce, hashes
        return -1, hashes

    # -- 3. Feedback & pruning -------------------------------------------

    def prune_face(self, face: PolyhedralFace) -> None:
        """Prune a face with zero target probability."""
        face.pruned = True
        self.state.pruned_faces += 1

    def reallocate(self, from_face: PolyhedralFace, to_face: PolyhedralFace) -> None:
        """Re-allocate nonce space from a pruned face to a high-salience face."""
        pruned_size = from_face.nonce_range[1] - from_face.nonce_range[0]
        from_face.nonce_range = (0, 0)  # zero out
        to_face.nonce_range = (
            to_face.nonce_range[0],
            to_face.nonce_range[1] + pruned_size,
        )

    # -- 4. Full control loop --------------------------------------------

    def search(
        self,
        header: bytes,
        target: bytes,
        max_faces: int = 32,
        max_hashes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run the canonical coverage-preserving 32-face search.

        The dual geometry orders and shards work; Cassini-certified affine
        permutations cover each selected shard without duplication.  Every
        candidate is accepted only by the real double-SHA256 target predicate.
        Hash samples are not treated as a differentiable landscape and an
        unsearched face is never reported as pruned.
        """
        result = self._verified_search.search(
            header=header,
            target=target,
            max_hashes=max_hashes,
            max_faces=max_faces,
        )
        solver_name = SolverType.VERIFIED_EXHAUSTIVE.value
        self.state.total_jobs_dispatched += result.faces_selected
        self.state.total_hashes_computed += result.hashes_checked
        self.state.solver_usage[solver_name] = self.state.solver_usage.get(solver_name, 0) + 1
        if result.winner_nonce is not None:
            self.state.total_nonces_found += 1

        payload = result.to_dict()
        payload.update(
            {
                "jobs_dispatched": result.faces_selected,
                "winners_found": int(result.winner_nonce is not None),
                "faces_pruned": 0,
                "total_hashes": result.hashes_checked,
                "solver_usage": dict(self.state.solver_usage),
                "controller_state": self.status(),
            }
        )
        return payload

    # -- Status ----------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        return {
            "total_jobs": self.state.total_jobs_dispatched,
            "total_hashes": self.state.total_hashes_computed,
            "total_nonces_found": self.state.total_nonces_found,
            "pruned_faces": self.state.pruned_faces,
            "solver_usage": dict(self.state.solver_usage),
            "avg_entropy": (
                sum(self.state.entropy_history) / len(self.state.entropy_history)
                if self.state.entropy_history
                else 0.0
            ),
            "polyhedral_mapping": self.mapping.status(),
            "verified_search_crystal": {
                "engine": "poincare_cassini_32_face",
                "faces": len(self._verified_search.faces),
                "dodecahedron_faces": sum(
                    face.solid == "dodecahedron" for face in self._verified_search.faces
                ),
                "icosahedron_faces": sum(
                    face.solid == "icosahedron" for face in self._verified_search.faces
                ),
                "nonce_space": self._verified_search.total_nonce_space,
            },
            "quantum_sim_available": self._sim is not None,
        }


__all__ = [
    "AgenticController",
    "PolyhedralMapping",
    "PolyhedralFace",
    "SolverType",
    "LandscapeType",
    "LandscapeAssessment",
    "SearchJob",
    "ControllerState",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (step_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("step_kernel")({"states": 8}, n)
    result["module"] = __name__
    return result
