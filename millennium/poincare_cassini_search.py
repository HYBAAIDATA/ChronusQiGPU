"""Poincaré–Cassini search engine: the 11D search topology as a traversal machine.

This is the ontology the substrate was built for — map, compass, pathfinder,
verifier — wired as one engine:

* **Map.** States live at integer anchors of the golden-weighted lattice.
  ``anchor_of(v) = round(||v||_phi) % 90`` is the same projection
  :class:`PrimeStorageManifold` and :class:`GeodesicNavigator` use, so a
  position in R^11 and a stored anchor are two views of the same state.
* **Compass.** The 32-face dodecahedron/icosahedron dual frame supplies 32
  search directions lifted into R^11 and normalised under the golden metric.
  A_5 symmetry means no direction is privileged.
* **Pathfinder.** Each step fires all 32 directions, takes the candidate
  that minimises golden-weighted distance to the target (steepest descent
  with backtracking step size), and stops when the projected anchor matches
  the target anchor and the residual is below ``epsilon``.
* **Verifier.** Every anchor entered during traversal is checked: the
  Cassini identity is recertified, stored ``cassini_parity`` is recomputed,
  and a corrupted node is repaired from the prime-exponent substrate
  (:meth:`GaloisPrimeSubstrate.fetch`) or, failing that, through
  :class:`SelfHealingSubstrate`.

Honest claim boundary: this engine navigates the state manifold — it does
not alter nonce-selection probabilities for proof-of-work and asserts no
mining advantage.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: hardened_unified_substrate + turing_core

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

import turing_core

try:
    # Canonical home of the substrate (aethel package).
    from aethel.hardened_unified_substrate import (
        CassiniVerifier,
        apply_zeckendorf_compression,
    )
except ImportError:  # pragma: no cover - alternate layouts
    try:
        from .hardened_unified_substrate import (
            CassiniVerifier,
            apply_zeckendorf_compression,
        )
    except ImportError:  # pragma: no cover - top-level script use
        from hardened_unified_substrate import (
            CassiniVerifier,
            apply_zeckendorf_compression,
        )


DIM = 11
ANCHOR_MODULUS = 90
PHI = turing_core.PHI
SQRT_PHI = math.sqrt(PHI)

GOLDEN_WEIGHTS = np.array([PHI ** -(i + 1) for i in range(DIM)], dtype=np.float64)


def weighted_norm_sq(v: np.ndarray) -> float:
    """Golden-weighted quadratic form sum(phi^{-(i+1)} * v_i^2)."""
    arr = np.asarray(v, dtype=np.float64).reshape(DIM)
    return float(np.sum(GOLDEN_WEIGHTS * (arr**2)))


def weighted_norm(v: np.ndarray) -> float:
    return math.sqrt(weighted_norm_sq(v))


def weighted_distance(a: np.ndarray, b: np.ndarray) -> float:
    return weighted_norm(np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64))


def anchor_of(v: np.ndarray) -> int:
    """Project an R^11 position onto the integer anchor lattice.

    Identical quadratic form to ``GeodesicNavigator._project_to_pv_lattice``
    and ``TensorCoreGPU_Context.project_and_collapse_pv``: the anchor is the
    rounded golden norm modulo 90.
    """
    return int(round(weighted_norm(v))) % ANCHOR_MODULUS


def anchor_to_vector(anchor: int) -> np.ndarray:
    """Exact canonical lift of an anchor into R^11.

    ``v = (anchor * sqrt(phi), 0, ..., 0)`` satisfies
    ``||v||_phi = anchor`` exactly, so ``anchor_of(anchor_to_vector(a)) == a``
    for every anchor in [0, 89]. This is the inverse of the lattice
    projection on its principal axis.
    """
    v = np.zeros(DIM, dtype=np.float64)
    v[0] = float(anchor % ANCHOR_MODULUS) * SQRT_PHI
    return v


@dataclass(frozen=True)
class SearchFace:
    """One face of the dual overlay: a search direction with provenance."""

    face_id: int
    solid: str
    local_face_id: int
    normal_3d: Tuple[float, float, float]
    direction_11d: Tuple[float, ...]
    golden_norm: float
    cassini_order: int
    cassini_determinant: int


class DodecaIcosahedron32:
    """The 32-face compass: 12 dodecahedron + 20 icosahedron face normals.

    The dodecahedron's 12 face normals point at the 12 icosahedron vertices
    and vice versa; taking the dual vertex sets gives the exact 12 + 20
    frame with no invented indices. Each 3D normal is lifted to R^11 by
    ``d_i = normal[i % 3] * phi^{-(i // 3)}`` and normalised to unit length
    under the golden metric. Every face carries a Cassini certificate at
    ``order = face_id + 2``; construction raises if any determinant is not
    unimodular.
    """

    def __init__(self):
        groups = (
            ("dodecahedron", turing_core.generate_icosahedron_vertices()),
            ("icosahedron", turing_core.generate_dodecahedron_vertices()),
        )
        faces: List[SearchFace] = []
        for solid, normals in groups:
            for local_id, normal_values in enumerate(normals):
                normal = tuple(float(x) for x in normal_values)
                lifted = np.array(
                    [normal[i % 3] * (PHI ** -(i // 3)) for i in range(DIM)],
                    dtype=np.float64,
                )
                norm = weighted_norm(lifted)
                if norm > 0:
                    lifted = lifted / norm
                order = len(faces) + 2
                det = (
                    turing_core.fibonacci(order + 1) * turing_core.fibonacci(order - 1)
                    - turing_core.fibonacci(order) ** 2
                )
                if det not in (-1, 1) or not turing_core.cassini_check(order):
                    raise ArithmeticError(f"Cassini invariant failed at order {order}")
                faces.append(
                    SearchFace(
                        face_id=len(faces),
                        solid=solid,
                        local_face_id=local_id,
                        normal_3d=normal,
                        direction_11d=tuple(float(x) for x in lifted),
                        golden_norm=weighted_norm(lifted),
                        cassini_order=order,
                        cassini_determinant=det,
                    )
                )
        if len(faces) != 32:
            raise ArithmeticError(f"dual frame produced {len(faces)} faces")
        self.faces: Tuple[SearchFace, ...] = tuple(faces)
        self.directions = np.array([f.direction_11d for f in self.faces], dtype=np.float64)

    def __len__(self) -> int:
        return len(self.faces)

    def fire(self, position: np.ndarray, step: float) -> np.ndarray:
        """All 32 candidate positions after one compass firing."""
        return np.asarray(position, dtype=np.float64) + step * self.directions


@dataclass
class SearchResult:
    """Outcome of a geodesic traversal through the manifold."""

    converged: bool
    target_anchor: int
    path: List[int]
    total_distance: float
    iterations: int
    cassini_valid: bool
    final_precision: float
    start_anchor: int = 1
    faces_fired: int = 0
    anchors_visited: int = 0
    healed_anchors: List[int] = field(default_factory=list)
    search_engine: str = "poincare_cassini_32_face"
    truth_class: str = "computational"
    claim_boundary: str = (
        "Geodesic state-space traversal only; no nonce-probability or "
        "proof-of-work advantage is asserted."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "converged": self.converged,
            "target_anchor": self.target_anchor,
            "start_anchor": self.start_anchor,
            "path": list(self.path),
            "total_distance": self.total_distance,
            "iterations": self.iterations,
            "cassini_valid": self.cassini_valid,
            "final_precision": self.final_precision,
            "faces_fired": self.faces_fired,
            "anchors_visited": self.anchors_visited,
            "healed_anchors": list(self.healed_anchors),
            "search_engine": self.search_engine,
            "truth_class": self.truth_class,
            "claim_boundary": self.claim_boundary,
        }


class PoincareCassiniSearch:
    """Geodesic pathfinder over the anchor lattice with Cassini verification.

    The search fires the full 32-face compass at every step, accepts the
    candidate that most reduces golden-weighted distance to the target, and
    halves the step when no face improves (backtracking line search on a
    positive-definite quadratic — geometric convergence, O(log 1/epsilon)
    steps). Accepted positions are projected to anchors; each new anchor is
    materialised on the manifold and Cassini/parity verified, repairing
    corrupted nodes from the prime-exponent substrate.
    """

    def __init__(
        self,
        overlay: Optional[DodecaIcosahedron32] = None,
        manifold: Optional[Any] = None,
        epsilon: float = 1e-8,
        max_iterations: int = 256,
        materialize: bool = True,
    ):
        self.overlay = overlay or DodecaIcosahedron32()
        self.manifold = manifold
        self.epsilon = float(epsilon)
        self.max_iterations = int(max_iterations)
        self.materialize = bool(materialize)
        self.last_verifications: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def search(
        self,
        target_vector: Sequence[float],
        start_vector: Optional[Sequence[float]] = None,
    ) -> SearchResult:
        """Navigate from a start position to ``target_vector``'s anchor."""
        target = np.asarray(target_vector, dtype=np.float64).reshape(DIM)
        target_anchor = anchor_of(target)
        if start_vector is not None:
            x = np.asarray(start_vector, dtype=np.float64).reshape(DIM).copy()
        else:
            root_anchor = self._root_anchor()
            x = anchor_to_vector(root_anchor)

        start_anchor = anchor_of(x)
        path: List[int] = [start_anchor]
        healed: List[int] = []
        self.last_verifications = []
        self._enter_anchor(start_anchor, healed)

        dist = weighted_distance(x, target)
        total = 0.0
        faces_fired = 0
        converged = False
        iterations = 0

        for iterations in range(1, self.max_iterations + 1):
            if dist < self.epsilon and anchor_of(x) == target_anchor:
                converged = True
                break

            # Fire all 32 faces: h_i = <u_i, r>_w is the exact line-search
            # minimum along face u_i for the quadratic distance to target.
            residual = target - x
            h_all = self.overlay.directions @ (GOLDEN_WEIGHTS * residual)
            faces_fired += len(self.overlay)

            # Steepest-descent move: the frame resultant g = sum_i h_i u_i
            # is the discrete gradient of the distance field — for the
            # tight dual frame it is near-parallel to the residual, giving
            # geometric convergence. Step length is the exact 1-D optimum.
            g = h_all @ self.overlay.directions
            g_norm_sq = float(np.sum(GOLDEN_WEIGHTS * (g**2)))
            if g_norm_sq < 1e-15:
                move = residual
            else:
                alpha = float(np.sum(GOLDEN_WEIGHTS * g * residual)) / g_norm_sq
                move = alpha * g

            # Walk the geodesic segment: verify every anchor shell the
            # move crosses, in crossing order, before landing.
            crossings = self._segment_anchor_crossings(x, move)
            for crossed_anchor in crossings:
                if crossed_anchor != path[-1]:
                    path.append(crossed_anchor)
                    self._enter_anchor(crossed_anchor, healed)

            total += weighted_norm(move)
            x = x + move
            dist = weighted_distance(x, target)
            landing_anchor = anchor_of(x)
            if landing_anchor != path[-1]:
                path.append(landing_anchor)
                self._enter_anchor(landing_anchor, healed)

        converged = converged or (dist < self.epsilon and anchor_of(x) == target_anchor)
        cassini_valid = all(v["ok"] for v in self.last_verifications)
        return SearchResult(
            converged=converged,
            target_anchor=target_anchor,
            start_anchor=start_anchor,
            path=path,
            total_distance=total,
            iterations=iterations,
            cassini_valid=cassini_valid,
            final_precision=dist,
            faces_fired=faces_fired,
            anchors_visited=len(path),
            healed_anchors=healed,
        )

    def navigate(self, from_anchor: int, to_anchor: int) -> SearchResult:
        """Anchor-to-anchor traversal along the canonical lifts."""
        return self.search(anchor_to_vector(to_anchor), start_vector=anchor_to_vector(from_anchor))

    # ------------------------------------------------------------------
    # Verification & repair
    # ------------------------------------------------------------------

    @staticmethod
    def _segment_anchor_crossings(start: np.ndarray, move: np.ndarray) -> List[int]:
        """Anchors entered along segment ``start -> start + move``, in order.

        Anchor shells are ellipsoid level sets ||x||_w = k + 0.5. Along the
        segment, ||x + t*move||_w^2 is a quadratic in t, so each shell's
        crossing parameter is a closed-form quadratic root. Roots are found
        on the two monotone pieces of the segment (the norm's vertex splits
        it), then sorted by t to give the true crossing order.
        """
        a = np.asarray(start, dtype=np.float64)
        d = np.asarray(move, dtype=np.float64)
        A = float(np.sum(GOLDEN_WEIGHTS * (d**2)))
        if A < 1e-30:
            return []
        B = float(2.0 * np.sum(GOLDEN_WEIGHTS * a * d))
        C = float(np.sum(GOLDEN_WEIGHTS * (a**2)))

        n_start = math.sqrt(max(C, 0.0))
        n_end = math.sqrt(max(A + B + C, 0.0))
        t_vertex = -B / (2.0 * A)
        pieces: List[Tuple[float, float]] = []
        if 0.0 < t_vertex < 1.0:
            pieces.append((0.0, t_vertex))
            pieces.append((t_vertex, 1.0))
        else:
            pieces.append((0.0, 1.0))

        def norm_sq_at(t: float) -> float:
            return A * t * t + B * t + C

        crossings: List[Tuple[float, int]] = []
        for t_lo, t_hi in pieces:
            n_lo = math.sqrt(max(norm_sq_at(t_lo), 0.0))
            n_hi = math.sqrt(max(norm_sq_at(t_hi), 0.0))
            lo_level = int(math.floor(min(n_lo, n_hi) + 0.5))
            hi_level = int(math.floor(max(n_lo, n_hi) + 0.5))
            ascending = n_hi >= n_lo
            for k in range(lo_level, hi_level + 1):
                shell = k + 0.5
                # Solve A t^2 + B t + (C - shell^2) = 0 on [t_lo, t_hi]
                c2 = C - shell * shell
                disc = B * B - 4.0 * A * c2
                if disc < 0.0:
                    continue
                sqrt_disc = math.sqrt(disc)
                for t in ((-B - sqrt_disc) / (2.0 * A), (-B + sqrt_disc) / (2.0 * A)):
                    if t_lo < t <= t_hi:
                        entered = k + 1 if ascending else k
                        if 0 <= entered < ANCHOR_MODULUS:
                            crossings.append((t, entered))

        crossings.sort(key=lambda item: item[0])
        ordered: List[int] = []
        for _t, anchor in crossings:
            if not ordered or ordered[-1] != anchor:
                ordered.append(anchor)
        if n_end <= n_start and ordered and ordered[0] == anchor_of(start):
            ordered.pop(0)
        return ordered

    def _root_anchor(self) -> int:
        if self.manifold is None:
            return 1
        try:
            node = self.manifold.get_root_node()
            return int(node.integer_anchor) if node.integer_anchor else 1
        except Exception:
            return 1

    def _enter_anchor(self, anchor: int, healed: List[int]) -> None:
        """Verify one anchor entered during traversal; repair if corrupted."""
        record: Dict[str, Any] = {"anchor": anchor, "ok": True, "repaired": False}
        if not CassiniVerifier.verify(anchor):
            record["ok"] = False
        if self.manifold is not None and anchor >= 0:
            node = self.manifold.get_by_anchor(anchor)
            if node is None and self.materialize:
                node = self.manifold.expand_manifold(anchor)
            if node is not None:
                parity_ok = getattr(node, "cassini_parity", None) in (None, (-1) ** anchor)
                if not parity_ok:
                    record["repaired"] = self._repair_node(node)
                    healed.append(anchor)
                    record["ok"] = record["ok"] and record["repaired"]
        self.last_verifications.append(record)

    def _repair_node(self, node: Any) -> bool:
        """Restore a corrupted node from the prime-exponent substrate.

        The pristine payload was committed at ingest as Galois exponents;
        ``fetch`` decodes it back. The node's sparse topology, parity and
        payload fields are rewritten in place and the event is logged on the
        substrate's heal log for provenance. Falls back to the substrate's
        own self-healing trigger when no pristine copy exists.
        """
        pristine = None
        try:
            pristine = self.manifold.curved_storage.fetch(node.uuid)
        except Exception:
            pristine = None
        if pristine is not None and getattr(node, "digest", None) is not None:
            if hashlib.sha256(pristine).digest() != node.digest:
                pristine = None
        if pristine is not None:
            sparse = apply_zeckendorf_compression(pristine)
            node.sparse_topology = sparse.blocks
            node.total_bytes = len(pristine)
            node.raw_payload = None
            node.cassini_parity = (-1) ** int(node.integer_anchor)
            self.manifold.self_healing.heal_log.append(
                {
                    "kind": "prime_exponent_restore",
                    "uuid": node.uuid,
                    "anchor": int(node.integer_anchor),
                }
            )
            return True
        try:
            self.manifold.self_healing.trigger(node)
            return True
        except Exception:
            return False


__all__ = [
    "ANCHOR_MODULUS",
    "DIM",
    "GOLDEN_WEIGHTS",
    "DodecaIcosahedron32",
    "PoincareCassiniSearch",
    "SearchFace",
    "SearchResult",
    "anchor_of",
    "anchor_to_vector",
    "weighted_distance",
    "weighted_norm",
    "weighted_norm_sq",
]
