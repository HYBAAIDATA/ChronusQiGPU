"""Deterministic nonce partitioning for the Chronus mining fleet.

The historical ``lucas`` and ``weighted`` strategies are retained unchanged as
compatibility surfaces. The explicit ``h4_600`` strategy is the canonical
production mining topology: it materialises the repository's H4/600-cell
frame, treats its 600 cell-normal R^11 frames as 600 logical search vertices,
partitions the exact nonce lease across those vertices, and assigns those
shards across every joined execution substrate in proportion to measured
throughput.

The partitioner never changes Bitcoin work or validity. It only assigns an
already-authorised half-open nonce interval. Every returned certificate is
re-checkable for totality, disjointness and digest integrity.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

from hyba.hybrid.nonce_scheduler import (
    DeviceCapability,
    NonceScheduler,
    canonical_json,
)

try:
    from lucas.core import lucas as _kellogg_lucas

    _KELLOGG_SOURCE = "lucas.core"
except Exception:  # pragma: no cover - lucas is part of this repo
    _kellogg_lucas = None
    _KELLOGG_SOURCE = "local Zphi fallback"

FACE_COUNT = 32
H4_FACE_COUNT = 600
MAX_FACE_COUNT = H4_FACE_COUNT


def _lucas_exact(n: int) -> int:
    if _kellogg_lucas is not None:
        return _kellogg_lucas(n)
    if n < 0:
        raise ValueError("lucas is defined for n >= 0")
    a, b = 2, 1
    if n == 0:
        return a
    for _ in range(n - 1):
        a, b = b, a + b
    return b


@lru_cache(maxsize=1)
def _verify_h4_topology() -> Tuple[int, int, int]:
    """Execute the real H4 constructor and refuse topology drift."""
    from chronus.h4_600 import build_600_frame

    frame = build_600_frame()
    vertices = int(frame.get("vertices", -1))
    cells = int(frame.get("cells", -1))
    frames = tuple(frame.get("frames_11d", ()))
    n_faces = int(frame.get("n_faces", -1))
    if vertices != 120 or cells != H4_FACE_COUNT or n_faces != H4_FACE_COUNT:
        raise RuntimeError(
            "Chronus H4 topology drift: expected 120 vertices / 600 cells / "
            f"600 frames, got {vertices} / {cells} / {n_faces}"
        )
    if len(frames) != H4_FACE_COUNT or any(len(vector) != 11 for vector in frames):
        raise RuntimeError("Chronus H4 topology must expose exactly 600 eleven-dimensional frames")
    return vertices, cells, n_faces


@dataclass(frozen=True)
class TraversalRecord:
    face: int
    device_id: str
    hit: bool
    nonces_tried: int


class TraversalHistory:
    """Append-only record of per-search-vertex outcomes."""

    def __init__(self) -> None:
        self._records: List[TraversalRecord] = []

    def append(self, face: int, device_id: str, hit: bool, nonces_tried: int) -> None:
        if not (0 <= int(face) < MAX_FACE_COUNT):
            raise ValueError(f"face/search-vertex out of range: {face}")
        self._records.append(
            TraversalRecord(int(face), str(device_id), bool(hit), int(nonces_tried))
        )

    def records(self) -> List[TraversalRecord]:
        return list(self._records)

    def miss_rate(self, face: int) -> float:
        trials = [r for r in self._records if r.face == face]
        if not trials:
            return 0.0
        misses = sum(1 for r in trials if not r.hit)
        return misses / len(trials)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "records": [
                {
                    "face": r.face,
                    "device_id": r.device_id,
                    "hit": r.hit,
                    "nonces_tried": r.nonces_tried,
                }
                for r in self._records
            ]
        }


def lucas_alignment(face: int) -> float:
    if not (0 <= face < FACE_COUNT):
        raise ValueError(f"face out of range: {face}")
    return _lucas_exact(face) / _lucas_exact(FACE_COUNT - 1)


def lucas_weight(face: int, device_hps: float, miss_rate: float) -> float:
    return lucas_alignment(face) * float(device_hps) / (1.0 + float(miss_rate))


@dataclass(frozen=True)
class SpanAssignment:
    device_id: str
    base_nonce: int
    span: int
    face: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "base_nonce": self.base_nonce,
            "span": self.span,
            "face": self.face,
        }


@dataclass(frozen=True)
class CoverageCertificate:
    total_span: int
    spans: Tuple[SpanAssignment, ...]
    digest: str
    folded_faces: Tuple[int, ...] = ()
    strategy: str = "lucas"
    kellogg_source: str = _KELLOGG_SOURCE
    topology: str = "legacy_32"

    def verify(self) -> bool:
        cursor = 0
        for span in self.spans:
            if span.span <= 0 or span.base_nonce != cursor:
                return False
            cursor += span.span
        if cursor != self.total_span:
            return False
        if self.strategy == "h4_600" and self.topology != "chronus_h4_600_11d":
            return False
        return self.digest == _certificate_digest(self)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "total_span": self.total_span,
            "spans": [s.as_dict() for s in self.spans],
            "digest": self.digest,
            "folded_faces": list(self.folded_faces),
            "strategy": self.strategy,
            "kellogg_source": self.kellogg_source,
            "topology": self.topology,
            "logical_vertex_count": H4_FACE_COUNT if self.topology == "chronus_h4_600_11d" else FACE_COUNT,
        }


def _certificate_digest(cert: CoverageCertificate) -> str:
    payload = {
        "total_span": cert.total_span,
        "spans": [s.as_dict() for s in cert.spans],
        "folded_faces": list(cert.folded_faces),
        "strategy": cert.strategy,
        "topology": cert.topology,
    }
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def _largest_remainder(total: int, shares: Sequence[float]) -> List[int]:
    raw = [max(0.0, float(value)) for value in shares]
    denom = sum(raw)
    if denom <= 0:
        out = [0] * len(raw)
        if raw:
            out[0] = total
        return out
    exact = [total * weight / denom for weight in raw]
    floors = [int(value) for value in exact]
    remainder = total - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: (-(exact[i] - floors[i]), i))
    for index in order[:remainder]:
        floors[index] += 1
    return floors


def _fair_owner_sequence(device_ids: Sequence[str], quotas: Sequence[int]) -> List[str]:
    total = sum(int(q) for q in quotas)
    if total <= 0:
        return []
    remaining = [int(q) for q in quotas]
    original = [max(1, int(q)) for q in quotas]
    emitted: List[str] = []
    for _ in range(total):
        candidates = [i for i, value in enumerate(remaining) if value > 0]
        best = max(candidates, key=lambda i: (remaining[i] / original[i], -i))
        emitted.append(device_ids[best])
        remaining[best] -= 1
    return emitted


def _h4_weighted_face_spans(
    total_span: int,
    device_ids: Sequence[str],
    measured_hps: Sequence[float],
) -> Tuple[List[Tuple[str, int, int]], List[int]]:
    """Build 600 logical H4 shards and assign them by measured fleet capacity."""
    _verify_h4_topology()
    if not device_ids:
        raise ValueError("H4 partition requires at least one device")

    weights = [max(0.0, float(value)) for value in measured_hps]
    if not any(value > 0 for value in weights):
        weights = [1.0] * len(device_ids)

    device_nonce_budget = _largest_remainder(total_span, weights)
    active_faces = min(H4_FACE_COUNT, total_span)
    face_quotas = _largest_remainder(active_faces, weights)

    excess = 0
    for i in range(len(face_quotas)):
        allowed = device_nonce_budget[i]
        if face_quotas[i] > allowed:
            excess += face_quotas[i] - allowed
            face_quotas[i] = allowed
    while excess:
        moved = False
        for i in range(len(face_quotas)):
            if face_quotas[i] < device_nonce_budget[i]:
                face_quotas[i] += 1
                excess -= 1
                moved = True
                if excess == 0:
                    break
        if not moved:
            raise ArithmeticError("unable to assign non-empty H4 vertices to fleet")

    owners = _fair_owner_sequence(device_ids, face_quotas)
    if len(owners) != active_faces:
        raise ArithmeticError("H4 owner sequence did not cover every active vertex")

    per_device_widths: Dict[str, List[int]] = {}
    per_device_cursor: Dict[str, int] = {}
    for device_id, budget, quota in zip(device_ids, device_nonce_budget, face_quotas):
        widths = _largest_remainder(budget, [1.0] * quota) if quota else []
        if any(width <= 0 for width in widths):
            raise ArithmeticError("active H4 vertex received an empty nonce shard")
        per_device_widths[device_id] = widths
        per_device_cursor[device_id] = 0

    emitted: List[Tuple[str, int, int]] = []
    for face in range(active_faces):
        device_id = owners[face]
        cursor = per_device_cursor[device_id]
        width = per_device_widths[device_id][cursor]
        per_device_cursor[device_id] = cursor + 1
        emitted.append((device_id, face, width))

    folded = list(range(active_faces, H4_FACE_COUNT))
    if sum(width for _, _, width in emitted) != total_span:
        raise ArithmeticError("H4 shards do not cover the requested nonce span")
    return emitted, folded


def partition(
    total_span: int,
    devices: Sequence[NonceScheduler],
    history: Optional[TraversalHistory] = None,
    *,
    strategy: str = "lucas",
) -> Tuple[List[SpanAssignment], CoverageCertificate]:
    """Assign ``[0,total_span)`` to devices with a replayable certificate.

    ``lucas`` is the historical 32-face weighted ownership.
    ``even`` splits the span equally across devices.
    ``weighted`` preserves the historical measured-H/s device apportionment.
    ``h4_600`` is the canonical 600-cell/11D logical-vertex partition.
    """
    total_span = int(total_span)
    if total_span <= 0:
        raise ValueError(f"total_span must be > 0, got {total_span}")
    if not devices:
        raise ValueError("partition requires at least one device")
    if strategy not in ("lucas", "even", "weighted", "h4_600"):
        raise ValueError(f"unknown partition strategy: {strategy}")

    history = history or TraversalHistory()
    caps: List[DeviceCapability] = [device.capability() for device in devices]
    usable = [(device, cap) for device, cap in zip(devices, caps) if cap.supported]
    if not usable:
        raise ValueError("no supported device in partition input")
    usable.sort(key=lambda item: item[1].device_id)
    device_ids = [cap.device_id for _, cap in usable]
    hps = [max(float(cap.measured_hashes_per_sec), 0.0) for _, cap in usable]

    face_spans: List[Tuple[str, int, int]] = []
    folded: List[int] = []
    topology = "legacy_32"

    if strategy == "h4_600":
        face_spans, folded = _h4_weighted_face_spans(total_span, device_ids, hps)
        topology = "chronus_h4_600_11d"
    elif strategy in ("even", "weighted"):
        shares = [1.0] * len(device_ids) if strategy == "even" else hps
        if strategy == "weighted" and not any(value > 0 for value in shares):
            shares = [1.0] * len(device_ids)
        allocations = _largest_remainder(total_span, shares)
        for device_id, span in zip(device_ids, allocations):
            if span > 0:
                face_spans.append((device_id, 0, span))
    else:
        hps_by_id = {device_id: value for device_id, value in zip(device_ids, hps)}
        weights: List[List[float]] = []
        for device_id in device_ids:
            row = [
                lucas_weight(face, hps_by_id[device_id], history.miss_rate(face))
                for face in range(FACE_COUNT)
            ]
            weights.append(row)
        owners: List[str] = []
        yields_: List[float] = []
        for face in range(FACE_COUNT):
            best_idx = max(range(len(device_ids)), key=lambda i: (weights[i][face], -i))
            owners.append(device_ids[best_idx])
            yields_.append(weights[best_idx][face])
        allocations = _largest_remainder(total_span, yields_)
        for face, (device_id, span) in enumerate(zip(owners, allocations)):
            if span <= 0:
                folded.append(face)
                continue
            face_spans.append((device_id, face, span))

    spans: List[SpanAssignment] = []
    cursor = 0
    for device_id, face, span in face_spans:
        spans.append(
            SpanAssignment(device_id=device_id, base_nonce=cursor, span=span, face=face)
        )
        cursor += span
    if cursor != total_span:
        raise ArithmeticError(
            f"partition must cover span exactly: covered={cursor}, requested={total_span}"
        )

    cert = CoverageCertificate(
        total_span=total_span,
        spans=tuple(spans),
        digest="",
        folded_faces=tuple(folded),
        strategy=strategy,
        topology=topology,
    )
    cert = CoverageCertificate(
        total_span=cert.total_span,
        spans=cert.spans,
        digest=_certificate_digest(cert),
        folded_faces=cert.folded_faces,
        strategy=cert.strategy,
        kellogg_source=cert.kellogg_source,
        topology=cert.topology,
    )
    return spans, cert


__all__ = [
    "CoverageCertificate",
    "FACE_COUNT",
    "H4_FACE_COUNT",
    "SpanAssignment",
    "TraversalHistory",
    "TraversalRecord",
    "lucas_alignment",
    "lucas_weight",
    "partition",
]
