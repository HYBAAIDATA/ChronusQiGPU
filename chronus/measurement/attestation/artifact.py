"""Content-addressed measurement artifact.

Invariants:
    ART1: every artifact has a digest.
    ART2: the digest is content-addressed — sha256 of the canonical payload.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .._common import canonical_json, to_payload

_PAYLOAD_KEYS = (
    "baseline",
    "topology",
    "profiling",
    "roofline",
    "workloads",
    "efficiency",
    "stability",
)


@dataclass
class MeasurementArtifact:
    id: str
    timestamp: str
    device_fingerprint: str
    baseline: Dict[str, Any]
    topology: Dict[str, Any]
    profiling: Dict[str, Any]
    roofline: Dict[str, Any]
    workloads: Dict[str, Any]
    efficiency: Dict[str, Any]
    stability: Dict[str, Any]
    digest: str
    attestation: str

    def payload(self) -> Dict[str, Any]:
        return {
            "baseline": to_payload(self.baseline),
            "topology": to_payload(self.topology),
            "profiling": to_payload(self.profiling),
            "roofline": to_payload(self.roofline),
            "workloads": to_payload(self.workloads),
            "efficiency": to_payload(self.efficiency),
            "stability": to_payload(self.stability),
        }

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "device_fingerprint": self.device_fingerprint,
            "digest": self.digest,
            "attestation": self.attestation,
            **self.payload(),
        }


def _digest(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def build_artifact(
    measurements: Dict[str, Any],
    *,
    device_fingerprint: Optional[str] = None,
) -> MeasurementArtifact:
    """Content-address the payload; id is the first 16 hex of the digest.

    ``device_fingerprint`` may explicitly identify the physical execution
    device proven by workload provenance. Existing callers that omit it retain
    the historical baseline-primary behavior.
    """
    sections = {k: to_payload(measurements.get(k, {})) for k in _PAYLOAD_KEYS}
    digest = _digest(sections)
    fingerprints = sections["baseline"].get("fingerprints") or []
    if device_fingerprint is None:
        device_fingerprint = fingerprints[0].get("digest", "") if fingerprints else ""
    return MeasurementArtifact(
        id=digest[:16],
        timestamp=datetime.now(timezone.utc).isoformat(),
        device_fingerprint=str(device_fingerprint or ""),
        baseline=sections["baseline"],
        topology=sections["topology"],
        profiling=sections["profiling"],
        roofline=sections["roofline"],
        workloads=sections["workloads"],
        efficiency=sections["efficiency"],
        stability=sections["stability"],
        digest=digest,
        attestation="",
    )
