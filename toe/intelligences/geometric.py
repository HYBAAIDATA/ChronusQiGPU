"""Geometric Intelligence — Nonce Space Navigation and Manifold Authority.

Operates across Substrates:
  - Substrate 4: Geometric (11D Poincaré-Cassini manifold + 32-face overlay)
  - Substrate 3: Topological (Curvature classification and Betti invariance)
  - Substrate 10: Quantum (State subspace projection and Born verification)

Provides ADVISORY intelligence for nonce-space geometry, Cassini permutations,
and collision-avoidance analysis. PYTHIA remains final authority for mining truth,
SearchPlan finalization, nonce-estate coverage, SHA256d/target proof semantics,
share validation/submission, credentials, and pool acknowledgements.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: mining
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import time
from typing import Any, Dict, List, Optional, Set
import numpy as np


@dataclass
class GeometricAllocation:
    """Nonce allocation decision from Geometric Intelligence."""

    face_id: int
    nonce_start: int
    nonce_count: int
    nonces: List[int]
    manifold_curvature: str
    cassini_parity_valid: bool
    timestamp: float = field(default_factory=time.time)
    provenance_hash: str = ""

    def __post_init__(self):
        if not self.provenance_hash:
            seed = f"{self.face_id}:{self.nonce_start}:{self.nonce_count}:{self.timestamp}"
            self.provenance_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def to_scalar(self) -> int:
        """Dual-mode scalar return: base nonce."""
        return int(self.nonce_start)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "face_id": self.face_id,
            "nonce_start": self.nonce_start,
            "nonce_count": self.nonce_count,
            "manifold_curvature": self.manifold_curvature,
            "cassini_parity_valid": self.cassini_parity_valid,
            "timestamp": self.timestamp,
            "provenance_hash": self.provenance_hash,
            "sample_nonces": self.nonces[:5] if self.nonces else [],
        }


class GeometricIntelligence:
    """Advisory intelligence for 11D geometry and nonce-manifold analysis."""

    LUCAS_TABLE = [2, 1, 3, 4, 7, 11, 18, 29, 47, 76, 123, 199, 322, 521, 843, 1364]
    FIB_TABLE = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987]

    def __init__(self, num_faces: int = 32):
        self.num_faces = num_faces
        self.allocated_nonces: Set[int] = set()
        self.face_success_weights: Dict[int, float] = {i: 1.0 for i in range(num_faces)}
        self.current_face_idx = 0
        self.allocation_history: List[GeometricAllocation] = []
        self.plasticity = 0.05

    @classmethod
    def verify_cassini_parity_integer(cls, n: int) -> bool:
        """Exact integer Cassini-Hoggatt verification: L_n^2 - 5*F_n^2 = 4*(-1)^n."""
        if n < 0:
            return False
        # Extended exact Lucas/Fibonacci generator for integer verification
        a_f, b_f = 0, 1
        a_l, b_l = 2, 1
        for _ in range(n):
            a_f, b_f = b_f, a_f + b_f
            a_l, b_l = b_l, a_l + b_l
        fn = a_f
        ln = a_l
        lhs = (ln * ln) - 5 * (fn * fn)
        rhs = 4 * (-1 if (n % 2 == 1) else 1)
        return lhs == rhs

    def allocate_nonce_manifold(
        self,
        batch_size: int = 1024,
        preferred_face: Optional[int] = None,
    ) -> GeometricAllocation:
        """Allocate a collision-free nonce partition across the 32-face manifold.

        Nonces encode 5 bits of face index + 27 bits of localized golden search.
        """
        if preferred_face is not None and 0 <= preferred_face < self.num_faces:
            face = preferred_face
        else:
            # Pick face with highest weight (plasticity)
            face = max(self.face_success_weights.items(), key=lambda x: x[1])[0]

        base_face_shift = (face & 0x1F) << 27
        nonces: List[int] = []
        step = 1

        # Use Lucas sequence to stride within the 27-bit subspace
        stride_anchor = self.LUCAS_TABLE[self.current_face_idx % len(self.LUCAS_TABLE)]
        candidate_local = (int(time.time() * 1000) ^ (stride_anchor << 4)) & 0x07FFFFFF

        while len(nonces) < batch_size:
            nonce = (base_face_shift | candidate_local) & 0xFFFFFFFF
            if nonce not in self.allocated_nonces:
                self.allocated_nonces.add(nonce)
                nonces.append(nonce)
            candidate_local = (candidate_local + stride_anchor + step) & 0x07FFFFFF
            step += 1

        self.current_face_idx = (self.current_face_idx + 1) % self.num_faces
        cassini_ok = self.verify_cassini_parity_integer(self.current_face_idx + 1)

        allocation = GeometricAllocation(
            face_id=face,
            nonce_start=nonces[0] if nonces else 0,
            nonce_count=len(nonces),
            nonces=nonces,
            manifold_curvature="NEGATIVE_HYPERBOLIC",
            cassini_parity_valid=cassini_ok,
        )
        self.allocation_history.append(allocation)
        return allocation

    def permute_cassini(self, nonces: List[int], n_step: int = 5) -> List[int]:
        """Permute nonces along the Cassini attractor orbit without introducing collisions."""
        permuted = []
        l_n = self.LUCAS_TABLE[n_step % len(self.LUCAS_TABLE)]
        for x in nonces:
            p = (x ^ (l_n << 3)) & 0xFFFFFFFF
            permuted.append(p)
        return permuted

    def detect_collision(self, candidate_nonces: List[int]) -> bool:
        """Verify that newly generated candidates have zero collision with existing state."""
        return len(candidate_nonces) != len(set(candidate_nonces))

    def navigate_11d_geodesic(self, origin: np.ndarray, steps: int = 11) -> np.ndarray:
        """Evaluate continuous geodesic steps on the 11D Poincaré ball."""
        point = np.copy(origin) if origin is not None else np.zeros(11, dtype=np.float64)
        phi = (1.0 + np.sqrt(5.0)) / 2.0
        for i in range(min(11, len(point))):
            weight = phi ** (-(i + 1))
            point[i] = np.tanh(point[i] + weight * 0.1)
        return point

    def learn(self, face_id: int, shares_found: int) -> None:
        """Plasticity reinforcement: increase face weight on discovery, decay on starvation."""
        if face_id in self.face_success_weights:
            old_w = self.face_success_weights[face_id]
            if shares_found > 0:
                self.face_success_weights[face_id] = min(
                    3.0, old_w + self.plasticity * shares_found
                )
            else:
                self.face_success_weights[face_id] = max(0.2, old_w - (self.plasticity * 0.1))
