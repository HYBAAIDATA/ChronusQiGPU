"""Lucas-weighted nonce partitioner — deterministic, auditable, total.

The 32-face winding frame divides ``[0, total_span)`` into face segments.
Each segment's span is proportional to its *predicted yield*: the
Lucas/phi alignment of the face times the winning device's measured
throughput, discounted by the face's historical miss rate. Each segment
is owned by the device with the highest weight *for that face*, so
high-yield faces land on the fastest substrate.

Properties (enforced by construction and re-checkable from the
certificate):

- **Total** — the union of emitted windows is exactly ``[0, total_span)``.
- **Disjoint** — ranges are contiguous, assigned in face order, and never
  overlap.
- **Non-empty** — faces that receive zero span under the largest-remainder
  apportionment are folded into the next emitted window, so no emitted
  window is empty.
- **Deterministic** — the same ``(total_span, devices, history)`` input
  produces the byte-identical assignment; the certificate digest pins it.

Lucas alignment is exact integer arithmetic from ``lucas.core``
(``lucas(f) / lucas(31)``); the only float crossing is the measured
hashes-per-second figure reported by each device — which is what it is.

Substrate route: hybrid coordinator. This module *consumes* the lucas/
scales; it does not define new tensor or Lucas math.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
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


def _lucas_exact(n: int) -> int:
    """L_n via kellogg.scales when present, else exact integer recurrence."""
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


# ---------------------------------------------------------------------------
# History — append-only, attested per dispatch
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TraversalRecord:
    face: int
    device_id: str
    hit: bool
    nonces_tried: int


class TraversalHistory:
    """Append-only record of per-face outcomes. Feeds yield prediction."""

    def __init__(self) -> None:
        self._records: List[TraversalRecord] = []

    def append(self, face: int, device_id: str, hit: bool, nonces_tried: int) -> None:
        if not (0 <= int(face) < FACE_COUNT):
            raise ValueError(f"face out of range: {face}")
        self._records.append(
            TraversalRecord(int(face), str(device_id), bool(hit), int(nonces_tried))
        )

    def records(self) -> List[TraversalRecord]:
        return list(self._records)

    def miss_rate(self, face: int) -> float:
        """Fraction of recorded windows on this face that found no share."""
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


# ---------------------------------------------------------------------------
# Weight model
# ---------------------------------------------------------------------------


def lucas_alignment(face: int) -> float:
    """|L_f| / L_31 normalized to (0, 1] — exact integers, one float crossing."""
    if not (0 <= face < FACE_COUNT):
        raise ValueError(f"face out of range: {face}")
    return _lucas_exact(face) / _lucas_exact(FACE_COUNT - 1)


def lucas_weight(face: int, device_hps: float, miss_rate: float) -> float:
    """Predicted yield of (face, device): alignment * throughput / (1 + miss)."""
    return lucas_alignment(face) * float(device_hps) / (1.0 + float(miss_rate))


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpanAssignment:
    """One emitted window range (job context is attached by the caller)."""

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
    """Auditable proof the assignment is total, disjoint and deterministic."""

    total_span: int
    spans: Tuple[SpanAssignment, ...]
    digest: str
    folded_faces: Tuple[int, ...] = ()
    strategy: str = "lucas"
    kellogg_source: str = _KELLOGG_SOURCE

    def verify(self) -> bool:
        """Re-check totality + disjointness + digest integrity."""
        cursor = 0
        for s in self.spans:
            if s.span <= 0 or s.base_nonce != cursor:
                return False
            cursor += s.span
        if cursor != self.total_span:
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
        }


def _certificate_digest(cert: CoverageCertificate) -> str:
    payload = {
        "total_span": cert.total_span,
        "spans": [s.as_dict() for s in cert.spans],
        "folded_faces": list(cert.folded_faces),
        "strategy": cert.strategy,
    }
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def _largest_remainder(total: int, shares: Sequence[float]) -> List[int]:
    """Integer apportionment: sum of allocations equals ``total`` exactly."""
    raw = list(shares)
    denom = sum(raw)
    if denom <= 0:
        out = [0] * len(raw)
        if raw:
            out[0] = total
        return out
    floors = [int(total * w / denom) for w in raw]
    remainder = total - sum(floors)
    order = sorted(
        range(len(raw)),
        key=lambda i: (-(total * raw[i] / denom - floors[i]), i),
    )
    for i in order[:remainder]:
        floors[i] += 1
    return floors


def partition(
    total_span: int,
    devices: Sequence[NonceScheduler],
    history: Optional[TraversalHistory] = None,
    *,
    strategy: str = "lucas",
) -> Tuple[List[SpanAssignment], CoverageCertificate]:
    """Assign ``[0, total_span)`` to devices by predicted yield.

    ``strategy="lucas"`` uses per-face weighted ownership;
    ``strategy="even"`` splits the span equally across devices;
    ``strategy="weighted"`` apportions the span in proportion to each
    device's measured hps, so every joined substrate receives work —
    required for compositions whose purpose is combined throughput
    (lucas argmax would award every face to the single fastest device).
    Returns ``(spans, certificate)`` where ``certificate.verify()``
    re-proves totality and disjointness.
    """
    total_span = int(total_span)
    if total_span <= 0:
        raise ValueError(f"total_span must be > 0, got {total_span}")
    if not devices:
        raise ValueError("partition requires at least one device")
    if strategy not in ("lucas", "even", "weighted"):
        raise ValueError(f"unknown partition strategy: {strategy}")

    history = history or TraversalHistory()
    caps: List[DeviceCapability] = [d.capability() for d in devices]
    usable = [(d, c) for d, c in zip(devices, caps) if c.supported]
    if not usable:
        raise ValueError("no supported device in partition input")
    # Deterministic device order regardless of caller order.
    usable.sort(key=lambda t: t[1].device_id)
    device_ids = [c.device_id for _, c in usable]
    hps = {c.device_id: max(float(c.measured_hashes_per_sec), 0.0) for _, c in usable}

    face_spans: List[Tuple[str, int, int]] = []  # (device_id, face, span)

    if strategy in ("even", "weighted"):
        if strategy == "even":
            shares = [1.0] * len(usable)
        else:
            shares = [max(hps[d], 0.0) for d in device_ids]
            if not any(s > 0 for s in shares):
                # No device has a measurement yet — equal apportionment is
                # the honest fallback, not a fabricated weighting.
                shares = [1.0] * len(device_ids)
        allocations = _largest_remainder(total_span, shares)
        for dev_id, span in zip(device_ids, allocations):
            if span > 0:
                face_spans.append((dev_id, 0, span))
    else:
        # Weight matrix W[d][f]; face owned by argmax over devices.
        weights: List[List[float]] = []
        for dev_id in device_ids:
            row = [lucas_weight(f, hps[dev_id], history.miss_rate(f)) for f in range(FACE_COUNT)]
            weights.append(row)
        owners: List[str] = []
        yields_: List[float] = []
        for f in range(FACE_COUNT):
            best_idx = max(
                range(len(device_ids)),
                key=lambda i: (weights[i][f], -i),
            )
            owners.append(device_ids[best_idx])
            yields_.append(weights[best_idx][f])
        allocations = _largest_remainder(total_span, yields_)
        folded: List[int] = []
        for f, (dev_id, span) in enumerate(zip(owners, allocations)):
            if span <= 0:
                folded.append(f)
                continue
            face_spans.append((dev_id, f, span))

    # Merge contiguous runs owned by the same device (never merge across a
    # face boundary tag for lucas mode — face provenance is kept per span).
    spans: List[SpanAssignment] = []
    cursor = 0
    for dev_id, face, span in face_spans:
        spans.append(SpanAssignment(device_id=dev_id, base_nonce=cursor, span=span, face=face))
        cursor += span
    assert cursor == total_span, "partition must cover the span exactly"

    cert = CoverageCertificate(
        total_span=total_span,
        spans=tuple(spans),
        digest="",
        folded_faces=tuple(folded if strategy == "lucas" else ()),
        strategy=strategy,
    )
    cert = CoverageCertificate(
        total_span=total_span,
        spans=tuple(spans),
        digest=_certificate_digest(cert),
        folded_faces=cert.folded_faces,
        strategy=strategy,
        kellogg_source=cert.kellogg_source,
    )
    return spans, cert


__all__ = [
    "CoverageCertificate",
    "FACE_COUNT",
    "SpanAssignment",
    "TraversalHistory",
    "TraversalRecord",
    "lucas_alignment",
    "lucas_weight",
    "partition",
]
