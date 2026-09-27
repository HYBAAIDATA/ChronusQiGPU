"""Verified 32-face search orchestration for PYTHIA.

This module consolidates four existing repository primitives without turning
their composition into an unproved search-advantage claim:

* the dodecahedron/icosahedron dual frame from :mod:`turing_core`;
* the 11-dimensional golden-weighted Poincare embedding;
* Cassini's exact unimodular Fibonacci identity; and
* the consensus double-SHA256 nonce predicate.

The 32 face normals define deterministic work shards and traversal order.  A
Cassini-certified affine permutation visits every nonce in a shard exactly
once.  Geometry changes ordering only; it never replaces the consensus oracle
and never permits an unsearched shard to be pruned.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

import turing_core


UINT32_SPACE = 1 << 32
SEARCH_ENGINE_ID = "poincare_cassini_32_face"


@dataclass(frozen=True)
class SearchFace:
    face_id: int
    solid: str
    local_face_id: int
    normal_3d: Tuple[float, float, float]
    direction_11d: Tuple[float, ...]
    poincare_norm_sq: float
    cassini_order: int
    cassini_determinant: int


@dataclass(frozen=True)
class Interval:
    start: int
    stop: int

    @property
    def size(self) -> int:
        return self.stop - self.start


@dataclass(frozen=True)
class CassiniSchedule:
    width: int
    stride: int
    origin: int
    cassini_order: int
    cassini_determinant: int

    def __len__(self) -> int:
        return self.width

    def offset_at(self, position: int) -> int:
        if position < 0 or position >= self.width:
            raise IndexError("schedule position out of range")
        return (self.origin + position * self.stride) % self.width

    def __iter__(self) -> Iterator[int]:
        for position in range(self.width):
            yield self.offset_at(position)


@dataclass(frozen=True)
class SearchResult:
    winner_nonce: Optional[int]
    winner_hash: Optional[bytes]
    hashes_checked: int
    nonce_space: int
    faces_selected: int
    faces_exhausted: int
    coverage_complete: bool
    coverage_fraction: float
    schedule_digest: str
    search_engine: str = SEARCH_ENGINE_ID
    truth_class: str = "computational"
    claim_boundary: str = (
        "Deterministic coverage and consensus verification only; no measured "
        "or theoretical nonce-probability advantage is asserted."
    )

    def to_dict(self) -> Dict[str, object]:
        return {
            "winner_nonce": self.winner_nonce,
            "winner_hash": self.winner_hash.hex() if self.winner_hash is not None else None,
            "hashes_checked": self.hashes_checked,
            "nonce_space": self.nonce_space,
            "faces_selected": self.faces_selected,
            "faces_exhausted": self.faces_exhausted,
            "coverage_complete": self.coverage_complete,
            "coverage_fraction": self.coverage_fraction,
            "schedule_digest": self.schedule_digest,
            "search_engine": self.search_engine,
            "truth_class": self.truth_class,
            "claim_boundary": self.claim_boundary,
        }


def _weighted_norm_sq(vector: Sequence[float]) -> float:
    return sum(
        (turing_core.PHI ** (-(index + 1))) * value * value
        for index, value in enumerate(vector)
    )


def _lift_and_fold_11d(normal: Sequence[float]) -> Tuple[Tuple[float, ...], float]:
    lifted = tuple(
        float(normal[index % 3]) * (turing_core.PHI ** (-(index // 3)))
        for index in range(11)
    )
    scale = 1.0 / math.sqrt(1.0 + _weighted_norm_sq(lifted))
    folded = tuple(value * scale for value in lifted)
    return folded, _weighted_norm_sq(folded)


def build_search_crystal() -> Tuple[SearchFace, ...]:
    """Return the complete dual set of 32 face normals.

    A regular dodecahedron's 12 face normals point toward the 12 vertices of
    its dual icosahedron.  Conversely, the 20 icosahedron face normals point
    toward the 20 dodecahedron vertices.  PYTHIA already generates both
    normalized vertex sets; interpreting them through duality avoids invented
    face indices and preserves the exact 12 + 20 construction.
    """

    groups = (
        ("dodecahedron", turing_core.generate_icosahedron_vertices()),
        ("icosahedron", turing_core.generate_dodecahedron_vertices()),
    )
    faces: List[SearchFace] = []
    for solid, normals in groups:
        for local_face_id, normal_values in enumerate(normals):
            normal = tuple(float(value) for value in normal_values)
            direction, poincare_norm_sq = _lift_and_fold_11d(normal)
            order = len(faces) + 2
            determinant = (
                turing_core.fibonacci(order + 1) * turing_core.fibonacci(order - 1)
                - turing_core.fibonacci(order) ** 2
            )
            if determinant not in (-1, 1) or not turing_core.cassini_check(order):
                raise ArithmeticError(f"Cassini invariant failed at order {order}")
            faces.append(
                SearchFace(
                    face_id=len(faces),
                    solid=solid,
                    local_face_id=local_face_id,
                    normal_3d=normal,
                    direction_11d=direction,
                    poincare_norm_sq=poincare_norm_sq,
                    cassini_order=order,
                    cassini_determinant=determinant,
                )
            )
    if len(faces) != 32:
        raise ArithmeticError(f"dual face construction produced {len(faces)} faces")
    return tuple(faces)


def partition_interval(start: int, size: int, partitions: int = 32) -> Tuple[Interval, ...]:
    """Partition ``[start, start + size)`` without gaps or overlap."""

    if start < 0 or size < 0:
        raise ValueError("start and size must be non-negative")
    if partitions < 1:
        raise ValueError("partitions must be positive")
    quotient, remainder = divmod(size, partitions)
    cursor = start
    result: List[Interval] = []
    for index in range(partitions):
        width = quotient + (1 if index < remainder else 0)
        result.append(Interval(cursor, cursor + width))
        cursor += width
    if cursor != start + size:
        raise ArithmeticError("partition coverage invariant failed")
    return tuple(result)


def cassini_permutation(width: int, face_id: int, seed: int) -> CassiniSchedule:
    """Return a coverage-complete affine permutation of one shard.

    The Fibonacci companion matrix at ``order`` supplies a Cassini determinant
    of +/-1.  Its adjacent limbs seed an affine stride; the stride is advanced
    until coprime to the shard width, which is the exact condition for a full
    permutation modulo ``width``.
    """

    if width < 1:
        raise ValueError("width must be positive")
    if face_id < 0:
        raise ValueError("face_id must be non-negative")
    order = face_id + 2
    determinant = (
        turing_core.fibonacci(order + 1) * turing_core.fibonacci(order - 1)
        - turing_core.fibonacci(order) ** 2
    )
    if determinant not in (-1, 1):
        raise ArithmeticError("Cassini determinant is not unimodular")

    stride = (turing_core.fibonacci(order + 1) + turing_core.fibonacci(order)) % width
    stride = stride or 1
    while math.gcd(stride, width) != 1:
        stride = (stride + 1) % width
        stride = stride or 1
    origin = (int(seed) + turing_core.fibonacci(order)) % width
    return CassiniSchedule(width, stride, origin, order, determinant)


def _header_direction(header_prefix: bytes) -> Tuple[float, ...]:
    digest = hashlib.sha256(header_prefix).digest()
    raw = tuple((digest[index] - 127.5) / 127.5 for index in range(11))
    scale = 1.0 / math.sqrt(1.0 + _weighted_norm_sq(raw))
    return tuple(value * scale for value in raw)


class PoincareCassiniSearchEngine:
    """Coverage-preserving 32-face nonce-search coordinator."""

    def __init__(self, total_nonce_space: int = 1_000_000, nonce_start: int = 0):
        total_nonce_space = int(total_nonce_space)
        nonce_start = int(nonce_start)
        if total_nonce_space < 1:
            raise ValueError("total_nonce_space must be positive")
        if nonce_start < 0 or nonce_start + total_nonce_space > UINT32_SPACE:
            raise ValueError("nonce interval must fit inside the uint32 space")
        self.total_nonce_space = total_nonce_space
        self.nonce_start = nonce_start
        self.faces = build_search_crystal()
        self.partitions = partition_interval(nonce_start, total_nonce_space, len(self.faces))

    def _rank_faces(self, header_prefix: bytes) -> Tuple[SearchFace, ...]:
        direction = _header_direction(header_prefix)

        def affinity(face: SearchFace) -> float:
            return sum(
                (turing_core.PHI ** (-(index + 1)))
                * direction[index]
                * face.direction_11d[index]
                for index in range(11)
            )

        return tuple(sorted(self.faces, key=lambda face: (-affinity(face), face.face_id)))

    def _candidate_stream(
        self, header_prefix: bytes, selected_faces: Sequence[SearchFace]
    ) -> Iterator[Tuple[int, int, bool]]:
        seed = int.from_bytes(hashlib.sha256(header_prefix).digest()[:8], "big")
        schedules: List[Tuple[SearchFace, Interval, CassiniSchedule, int]] = []
        for face in selected_faces:
            interval = self.partitions[face.face_id]
            if interval.size:
                schedules.append(
                    (face, interval, cassini_permutation(interval.size, face.face_id, seed), 0)
                )

        while schedules:
            next_round: List[Tuple[SearchFace, Interval, CassiniSchedule, int]] = []
            for face, interval, schedule, position in schedules:
                offset = schedule.offset_at(position)
                next_position = position + 1
                exhausted = next_position == len(schedule)
                yield face.face_id, interval.start + offset, exhausted
                if not exhausted:
                    next_round.append((face, interval, schedule, next_position))
            schedules = next_round

    def enumerate_nonces(
        self,
        header_prefix: bytes,
        selected_faces: Optional[Sequence[SearchFace]] = None,
    ) -> List[int]:
        """Return the full nonce order of ``_candidate_stream``, vectorized.

        Each face's shard walk is the affine sequence
        ``(origin + position * stride) % width``, so the round-robin stream
        can be computed as per-face arithmetic sequences plus a column-major
        interleave.  Emits the identical ordering and coverage as the
        generator — callers that materialize the whole window (e.g.
        ``stratum_bridge._poincare_11d_nonces``) should use this instead of
        iterating ~30k nonces/second through Python generator machinery.
        """
        import numpy as np

        seed = int.from_bytes(hashlib.sha256(header_prefix).digest()[:8], "big")
        faces = self.faces if selected_faces is None else selected_faces
        entries = [
            (self.partitions[face.face_id],
             cassini_permutation(self.partitions[face.face_id].size, face.face_id, seed))
            for face in faces
            if self.partitions[face.face_id].size
        ]
        if not entries:
            return []
        starts = np.array([iv.start for iv, _ in entries], dtype=np.int64)
        widths = np.array([iv.size for iv, _ in entries], dtype=np.int64)
        strides = np.array([s.stride for _, s in entries], dtype=np.int64)
        origins = np.array([s.origin for _, s in entries], dtype=np.int64)
        w_min = int(widths.min())
        positions = np.arange(w_min, dtype=np.int64)
        block = starts[:, None] + (
            (origins[:, None] + positions[None, :] * strides[:, None]) % widths[:, None]
        )
        order = block.T.ravel().tolist()
        for p in range(w_min, int(widths.max())):
            mask = widths > p
            if mask.any():
                order.extend(
                    (starts + (origins + p * strides) % widths)[mask].tolist()
                )
        return order

    def search(
        self,
        header: bytes,
        target: bytes,
        max_hashes: Optional[int] = None,
        max_faces: int = 32,
    ) -> SearchResult:
        """Search with real double-SHA256 verification and explicit coverage."""

        if len(header) not in (76, 80):
            raise ValueError("header must contain exactly 76 or 80 bytes")
        if len(target) != 32:
            raise ValueError("target must contain exactly 32 bytes")
        if max_hashes is not None and int(max_hashes) < 0:
            raise ValueError("max_hashes must be non-negative or None")
        max_faces = max(0, min(int(max_faces), len(self.faces)))

        header_prefix = bytes(header[:76])
        target_value = int.from_bytes(target, "big")
        selected_faces = self._rank_faces(header_prefix)[:max_faces]
        selected_ids = {face.face_id for face in selected_faces}
        selected_nonce_count = sum(self.partitions[face_id].size for face_id in selected_ids)
        budget = selected_nonce_count if max_hashes is None else min(int(max_hashes), selected_nonce_count)

        hashes_checked = 0
        faces_exhausted = 0
        digest = hashlib.sha256()
        for face_id, nonce, exhausted in self._candidate_stream(header_prefix, selected_faces):
            if hashes_checked >= budget:
                break
            nonce_bytes = struct.pack("<I", nonce)
            candidate_hash = turing_core.PythiaMiningEngine.double_sha256(header_prefix + nonce_bytes)
            digest.update(struct.pack("<BI", face_id, nonce))
            hashes_checked += 1
            if exhausted:
                faces_exhausted += 1
            if int.from_bytes(candidate_hash, "little") < target_value:
                coverage_complete = hashes_checked == self.total_nonce_space
                return SearchResult(
                    winner_nonce=nonce,
                    winner_hash=candidate_hash,
                    hashes_checked=hashes_checked,
                    nonce_space=self.total_nonce_space,
                    faces_selected=len(selected_faces),
                    faces_exhausted=faces_exhausted,
                    coverage_complete=coverage_complete,
                    coverage_fraction=hashes_checked / self.total_nonce_space,
                    schedule_digest=digest.hexdigest(),
                )

        coverage_complete = hashes_checked == self.total_nonce_space
        return SearchResult(
            winner_nonce=None,
            winner_hash=None,
            hashes_checked=hashes_checked,
            nonce_space=self.total_nonce_space,
            faces_selected=len(selected_faces),
            faces_exhausted=faces_exhausted,
            coverage_complete=coverage_complete,
            coverage_fraction=hashes_checked / self.total_nonce_space,
            schedule_digest=digest.hexdigest(),
        )


__all__ = [
    "SEARCH_ENGINE_ID",
    "SearchFace",
    "Interval",
    "CassiniSchedule",
    "SearchResult",
    "build_search_crystal",
    "partition_interval",
    "cassini_permutation",
    "PoincareCassiniSearchEngine",
]
