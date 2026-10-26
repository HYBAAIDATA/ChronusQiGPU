"""HYBA Data — sealed metric card (code elevated to documentation).

Board: M1 is BOUNDED with sealed production harness test_hash. M2/M3 remain INTERNAL.
M2/M3 remain INTERNAL and cannot be returned for external release lanes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hyba_data.sealed_claims import ClaimLane


@dataclass(frozen=True)
class MetricRow:
    metric_id: str
    mode: str
    ratio: float
    data_class: str
    loss: str
    lane: ClaimLane
    notes: str
    test_hash: str = ""
    throughput_mbs: Optional[float] = None
    max_error: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["lane"] = self.lane.value
        return d


# Single source of truth — must match Sealed Claims Register / Capabilities doc
METRIC_CARD: List[MetricRow] = [
    MetricRow(
        metric_id="M1",
        mode="depth1_phi2_working_set",
        ratio=2.62,
        data_class="structured_numerical",
        loss="near_lossless_with_kernels",
        lane=ClaimLane.BOUNDED,
        notes="BOUNDED external with method + data class; harness sealed test_hash attached",
        test_hash="02b3c4ac40c7aad51b118cff9eed3c5fc81dadc0ed0c818333d332825709cf19",
        max_error=1.715610487007524e-09,
    ),
    MetricRow(
        metric_id="M2",
        mode="depth4_phi4",
        ratio=6.94,
        data_class="structured_workloads_docs",
        loss="claimed_lossless_in_some_packs",
        lane=ClaimLane.INTERNAL,
        notes="Unreconciled with M1 for external use — INTERNAL",
    ),
    MetricRow(
        metric_id="M3",
        mode="commercial_multiplier",
        ratio=7.155,
        data_class="savings_framing",
        loss="n/a",
        lane=ClaimLane.INTERNAL,
        notes="Requires customer seal (T3) — INTERNAL",
    ),
]


def get_metric(metric_id: str) -> MetricRow:
    for m in METRIC_CARD:
        if m.metric_id == metric_id:
            return m
    raise KeyError(f"Unknown metric_id: {metric_id}")


def list_metrics(*, external_only: bool = False) -> List[Dict[str, Any]]:
    rows = METRIC_CARD
    if external_only:
        rows = [m for m in METRIC_CARD if m.lane in (ClaimLane.EXTERNAL, ClaimLane.BOUNDED)]
    return [m.to_dict() for m in rows]


def get_external_metric(metric_id: str = "M1") -> Dict[str, Any]:
    """Return a metric only if it may leave the ecosystem (EXTERNAL/BOUNDED)."""
    m = get_metric(metric_id)
    if m.lane not in (ClaimLane.EXTERNAL, ClaimLane.BOUNDED):
        raise PermissionError(
            f"Metric {metric_id} is {m.lane.value} and cannot leave the ecosystem"
        )
    return {
        **m.to_dict(),
        "external_sentence": (
            "PULVINI applies φ-folding to structured numerical working sets. "
            f"Cited ratio ~{m.ratio}× is {m.lane.value} for mode={m.mode}; "
            "customer savings require production measurement under gain-share."
        ),
        "sealed": bool(m.test_hash),
        "elevation_rule": "The code must always be elevated to meet documentation.",
    }


def seal_metric(
    metric_id: str,
    *,
    test_hash: str,
    max_error: Optional[float] = None,
    throughput_mbs: Optional[float] = None,
    promote_to_external: bool = False,
) -> Dict[str, Any]:
    """Attach evidence hash to a metric row (immutable card rebuild).

    Note: METRIC_CARD is module-level frozen policy; this returns a sealed
    snapshot dict for artifacts — it does not silently promote M2/M3.
    """
    m = get_metric(metric_id)
    if m.lane == ClaimLane.INTERNAL and promote_to_external:
        raise PermissionError(
            f"Cannot promote {metric_id} to EXTERNAL without board/engineering policy change"
        )
    snapshot = m.to_dict()
    snapshot.update(
        {
            "test_hash": test_hash,
            "max_error": max_error if max_error is not None else m.max_error,
            "throughput_mbs": throughput_mbs if throughput_mbs is not None else m.throughput_mbs,
            "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
            "sealed": True,
        }
    )
    return snapshot


def card_fingerprint() -> str:
    payload = json.dumps([m.to_dict() for m in METRIC_CARD], sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def metric_card_report() -> Dict[str, Any]:
    return {
        "company": "HYBA Data",
        "product": "HERMES",
        "engine": "PULVINI",
        "fingerprint_sha256": card_fingerprint(),
        "metrics": list_metrics(),
        "external_metrics": list_metrics(external_only=True),
        "board_rule": (
            "Until engineering signs one external row with test hash, "
            "customer numbers use sensitivity 1.5×/2.0×/2.6× not freeze mega-claims."
        ),
    }
