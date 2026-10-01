"""Evidence queries — deterministic filters over stored artifacts.

Invariants:
    Q1: every query returns a list.
    Q2: every query is deterministic.
"""

from __future__ import annotations

from typing import List

from ..attestation.artifact import MeasurementArtifact
from .evidence import EvidenceStore


def query_by_device(store: EvidenceStore, fingerprint: str) -> List[MeasurementArtifact]:
    return [a for a in store.artifacts.values() if a.device_fingerprint == fingerprint]


def query_by_time(store: EvidenceStore, start: str, end: str) -> List[MeasurementArtifact]:
    return sorted(
        [a for a in store.artifacts.values() if start <= a.timestamp <= end],
        key=lambda a: a.timestamp,
    )


def query_by_hashrate(store: EvidenceStore, min_hps: float) -> List[MeasurementArtifact]:
    out = []
    for a in store.artifacts.values():
        hps = (a.workloads.get("hashrate") or {}).get("hps") or {}
        if hps.get("mean", 0.0) >= min_hps:
            out.append(a)
    return out
