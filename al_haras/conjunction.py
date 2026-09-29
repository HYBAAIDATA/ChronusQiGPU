"""Fail-closed Guardian conjunction over measured evidence surfaces."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict
from dataclasses import dataclass
from enum import Enum
from typing import Any
from typing import Mapping


class SurfaceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


class OverallStatus(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    DEGRADED = "DEGRADED"
    QUARANTINE = "QUARANTINE"


MODE_IDS = ("M1_ADMISSION", "M2_POLICY", "M3_EVIDENCE", "M4_INTEGRITY", "M5_WITNESS")
TOPOLOGY_IDS = (
    "T1_GRAPH_CONNECTIVITY",
    "T2_SPECTRAL_GAP",
    "T3_HOMOLOGY",
    "T4_ROUTE_STABILITY",
    "T5_M32_CONSISTENCY",
    "T6_REPLICATION_TOPOLOGY",
    "T7_FAULT_DOMAIN_TOPOLOGY",
)
INTELLIGENCE_IDS = (
    "I1_GEOMETRIC",
    "I2_TOPOLOGICAL",
    "I3_FORWARD",
    "I4_CAUSAL",
    "I5_COUNTERFACTUAL",
    "I6_WITNESS",
)


@dataclass(frozen=True)
class SurfaceVerdict:
    surface_id: str
    status: SurfaceStatus
    evidence_hash: str | None = None
    invariants: tuple[str, ...] = ()
    residuals: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnomalyState:
    active: bool = False
    severity: str = "NONE"
    since: int | None = None


@dataclass(frozen=True)
class AttestationState:
    backend_certificate: str | None = None
    device_id: str | None = None
    measured: bool = False
    signed: bool = False


@dataclass(frozen=True)
class IntegrityState:
    cassini_ok: bool = False
    zeckendorf_ok: bool = False
    chain_ok: bool = False
    lineage_ok: bool = False


@dataclass(frozen=True)
class ConjunctionVerdict:
    overall: OverallStatus
    modes: tuple[SurfaceVerdict, ...]
    topologies: tuple[SurfaceVerdict, ...]
    intelligences: tuple[SurfaceVerdict, ...]
    anomaly: AnomalyState
    attestation: AttestationState
    integrity: IntegrityState
    reason_chain: tuple[str, ...]
    signature_algorithm: str
    signature: str

    @property
    def allowed(self) -> bool:
        return self.overall is OverallStatus.ALLOW

    def to_dict(self) -> dict[str, Any]:
        def plain(v):
            if isinstance(v, Enum):
                return v.value
            if hasattr(v, "__dataclass_fields__"):
                return {k: plain(x) for k, x in asdict(v).items()}
            if isinstance(v, (list, tuple)):
                return [plain(x) for x in v]
            return v

        return plain(self)


def _canonical(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), default=str).encode()


def _body(overall, modes, topologies, intelligences, anomaly, attestation, integrity, reasons):
    return {
        "overall": overall.value,
        "modes": [asdict(v) for v in modes],
        "topologies": [asdict(v) for v in topologies],
        "intelligences": [asdict(v) for v in intelligences],
        "anomaly": asdict(anomaly),
        "attestation": asdict(attestation),
        "integrity": asdict(integrity),
        "reason_chain": reasons,
    }


def _validate(group: tuple[SurfaceVerdict, ...], expected: tuple[str, ...], label: str) -> None:
    ids = tuple(v.surface_id for v in group)
    if ids != expected:
        raise ValueError(f"{label} must contain exactly {expected}")


def _signed(
    overall, modes, topologies, intelligences, anomaly, attestation, integrity, reasons, key
):
    body = _body(
        overall, modes, topologies, intelligences, anomaly, attestation, integrity, reasons
    )
    signature = hmac.new(key, _canonical(body), hashlib.sha256).hexdigest()
    return ConjunctionVerdict(
        overall,
        modes,
        topologies,
        intelligences,
        anomaly,
        attestation,
        integrity,
        tuple(reasons),
        "HMAC-SHA256",
        signature,
    )


def verify_conjunction_signature(verdict: ConjunctionVerdict, signing_key: bytes) -> bool:
    if verdict.signature_algorithm != "HMAC-SHA256" or len(signing_key) < 32:
        return False
    body = _body(
        verdict.overall,
        verdict.modes,
        verdict.topologies,
        verdict.intelligences,
        verdict.anomaly,
        verdict.attestation,
        verdict.integrity,
        list(verdict.reason_chain),
    )
    expected = hmac.new(signing_key, _canonical(body), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, verdict.signature)


def guardian_conjunction(
    *, modes, topologies, intelligences, anomaly, attestation, integrity, signing_key: bytes
) -> ConjunctionVerdict:
    modes = tuple(modes)
    topologies = tuple(topologies)
    intelligences = tuple(intelligences)
    _validate(modes, MODE_IDS, "modes")
    _validate(topologies, TOPOLOGY_IDS, "topologies")
    _validate(intelligences, INTELLIGENCE_IDS, "intelligences")
    if not isinstance(signing_key, bytes) or len(signing_key) < 32:
        raise ValueError("verdict signing key must be at least 32 bytes")
    reasons = []
    for label, group in (
        ("mode", modes),
        ("topology", topologies),
        ("intelligence", intelligences),
    ):
        failed = [v.surface_id for v in group if v.status is SurfaceStatus.FAIL]
        if failed:
            reasons.append(f"{label}_failure:{','.join(failed)}")
    integrity_failed = not all(
        (integrity.cassini_ok, integrity.zeckendorf_ok, integrity.chain_ok, integrity.lineage_ok)
    )
    if integrity_failed:
        reasons.append("integrity_failure")
    # Integrity failure is isolated from ordinary policy/surface denial because
    # the associated object and principal require containment and investigation.
    if integrity_failed:
        return _signed(
            OverallStatus.QUARANTINE,
            modes,
            topologies,
            intelligences,
            anomaly,
            attestation,
            integrity,
            reasons,
            signing_key,
        )
    if reasons:
        return _signed(
            OverallStatus.DENY,
            modes,
            topologies,
            intelligences,
            anomaly,
            attestation,
            integrity,
            reasons,
            signing_key,
        )
    if anomaly.active and anomaly.severity.upper() in {"HIGH", "CRITICAL"}:
        reasons.append("anomaly_high")
    if not (attestation.measured and attestation.signed):
        reasons.append("attestation_unmeasured")
    unknown = [
        v.surface_id
        for v in modes + topologies + intelligences
        if v.status in {SurfaceStatus.UNKNOWN, SurfaceStatus.UNAVAILABLE}
    ]
    if unknown:
        reasons.append("unmeasured_surface:" + ",".join(unknown))
    overall = OverallStatus.DEGRADED if reasons else OverallStatus.ALLOW
    return _signed(
        overall,
        modes,
        topologies,
        intelligences,
        anomaly,
        attestation,
        integrity,
        reasons or ["all_required_surfaces_passed"],
        signing_key,
    )


def surfaces_from_mapping(
    ids: tuple[str, ...], evidence: Mapping[str, Mapping[str, Any]]
) -> tuple[SurfaceVerdict, ...]:
    out = []
    for sid in ids:
        raw = evidence.get(sid)
        if not isinstance(raw, Mapping):
            out.append(SurfaceVerdict(sid, SurfaceStatus.UNAVAILABLE))
            continue
        try:
            status = SurfaceStatus(str(raw.get("status", "UNKNOWN")))
        except ValueError:
            status = SurfaceStatus.UNKNOWN
        out.append(
            SurfaceVerdict(
                sid,
                status,
                raw.get("evidence_hash"),
                tuple(raw.get("invariants", ())),
                tuple(raw.get("residuals", ())),
            )
        )
    return tuple(out)
