"""Enterprise capability bridge — mining proof ground → HYBA Intelligence.

Rule 7 (Strict Honest Measurement): every capability is READY / PARTIAL /
ABSENT / EXTERNAL. No synthetic benchmarks. No unearned endorsements.

Intelligence (or any enterprise host) should import this module to:

1. Discover which triad capabilities are actually ready to migrate.
2. Emit response envelopes with ``truth_class`` + ``provenance_hash``.
3. Refuse to advertise EXTERNAL/ABSENT IDs as local production features.

Mining remains the first proof ground. Solutions API, MRI clinical stacks,
and the 10-service commercial suite live in the Intelligence enterprise
repo unless explicitly re-homed with measured tests.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional


class CapStatus(str, Enum):
    READY = "READY"  # measured in this repo
    PARTIAL = "PARTIAL"  # primitives exist; product surface incomplete
    ABSENT = "ABSENT"  # not in this tree
    EXTERNAL = "EXTERNAL"  # belongs to Intelligence / other system
    STRETCH = "STRETCH"  # rhetorical / unmeasured roofline — do not ship


class TruthClass(str, Enum):
    MEASURED = "measured"
    MATHEMATICAL = "mathematical"
    UNVERIFIED = "unverified"
    EXTERNAL_CLAIM = "external_claim"
    NON_CLAIM = "non_claim"


@dataclass(frozen=True)
class Capability:
    id: str
    title: str
    status: CapStatus
    owner: str
    surface: str
    notes: str = ""
    pillar: str = ""  # Pulvini | Compass | Accel | Cortex | Governance | API


# Canonical enterprise migration catalogue (mining-proven + honest gaps)
CAPABILITIES: tuple[Capability, ...] = (
    # Pulvini / fold / store
    Capability(
        "E.FOLD.WORKING_FORM",
        "Folded form is the working form",
        CapStatus.READY,
        "ovid",
        "aethel.ovid",
        "Ovid metamorphose/materialise; unfold is egress only",
        "Pulvini",
    ),
    Capability(
        "E.FOLD.INVERTIBLE",
        "Lossless invertible fold with digest pin",
        CapStatus.READY,
        "ovid",
        "aethel.ovid / aethel.encoding",
        "Zeckendorf round-trip + SHA-256 digest",
        "Pulvini",
    ),
    Capability(
        "E.STORE.PRIME_KEY",
        "Galois prime-key custody",
        CapStatus.READY,
        "theseus",
        "aethel.primes + aethel.theseus",
        "Composite GF keys; not infinite prime-gap continuum",
        "Pulvini",
    ),
    Capability(
        "E.STORE.PHYLLOTAXIS",
        "Sunflower/Vogel packing (M32 lanes)",
        CapStatus.READY,
        "theseus",
        "aethel.phyllotaxis",
        "GOLDEN_ANGLE = π(3−√5); packing ≠ biotech compiler",
        "Pulvini",
    ),
    Capability(
        "E.STORE.SELF_HEAL",
        "Theseus self-heal from replica",
        CapStatus.READY,
        "theseus",
        "aethel.theseus",
        "Primary + replica; fail-closed after one heal",
        "Pulvini",
    ),
    Capability(
        "E.STORE.CASSINI",
        "Fibonacci address + Cassini ledger",
        CapStatus.READY,
        "theseus",
        "aethel.storage",
        "Measured ledger verify",
        "Pulvini",
    ),
    Capability(
        "E.STORE.DURABLE",
        "Durable snapshot/attach journal",
        CapStatus.READY,
        "theseus",
        "aethel.storage.AddressSpace",
        "Software durable path",
        "Pulvini",
    ),
    Capability(
        "E.STORE.HYPERSCALER_SKU",
        "Hyperscaler folded working-form SKU",
        CapStatus.PARTIAL,
        "theseus",
        "aethel.hyperscaler.HyperscalerSku",
        "H1–H4 contracts in module; not full 10-service suite",
        "Pulvini",
    ),
    # Compass
    Capability(
        "E.SEARCH.GEODESIC_HANDOFF",
        "Geodesic handoff-only search boundary",
        CapStatus.READY,
        "compass",
        "aethel.geodesic.GeodesicHandoff",
        "Storage does not reimplement search",
        "Compass",
    ),
    Capability(
        "E.SEARCH.32_FACE",
        "32-face Poincaré–Cassini frame",
        CapStatus.PARTIAL,
        "compass",
        "GeodesicHandoff → Intelligence engine",
        "Ready when engine import resolves",
        "Compass",
    ),
    Capability(
        "E.SEARCH.11D_VECTOR",
        "11-dimensional routing/state vector",
        CapStatus.PARTIAL,
        "compass",
        "aethel.constants.DIM + manifold points",
        "Math spine live; DigitalHQ product API external",
        "Compass",
    ),
    Capability(
        "E.SEARCH.MULTI_LENS_API",
        "Multi-lens product search API",
        CapStatus.EXTERNAL,
        "compass",
        "HYBA Intelligence Compass product",
        "Not shipped as product API in this repo",
        "Compass",
    ),
    # Accel / Chronus
    Capability(
        "E.COMPUTE.CHRONUS_DEVICE",
        "Chronus iGPU offering bind",
        CapStatus.READY,
        "chronus",
        "chronus.device",
        "CLAIM_BOUNDARY: no preimage oracle; measured dispatches only",
        "Accel",
    ),
    Capability(
        "E.COMPUTE.VIRTUAL_IGPU",
        "Virtual iGPU fail-closed ABI",
        CapStatus.READY,
        "chronus",
        "chronus.virtual_igpu",
        "Adapters refuse missing hardware; evidence path",
        "Accel",
    ),
    Capability(
        "E.COMPUTE.NO_PREIMAGE",
        "Non-claim: no hash preimage / hash-strike",
        CapStatus.READY,
        "chronus",
        "CLAIM_BOUNDARY",
        "Mining accept authority remains sha256d target",
        "Accel",
    ),
    Capability(
        "E.COMPUTE.THESEUS_EVIDENCE",
        "Optional Theseus custody of iGPU evidence",
        CapStatus.READY,
        "chronus",
        "CHRONUS_VIGPU_THESEUS=1",
        "Additive fail-soft on virtual iGPU persist",
        "Accel",
    ),
    # Governance
    Capability(
        "E.GOV.CLAIM_BOUNDARY",
        "Owner claim boundaries",
        CapStatus.READY,
        "governance",
        "triad + chronus CLAIM_BOUNDARY",
        "Rule 7 non-claims locked in owners",
        "Governance",
    ),
    Capability(
        "E.GOV.TRUTH_CLASS",
        "truth_class labeling discipline",
        CapStatus.PARTIAL,
        "governance",
        "enterprise_bridge.emit_envelope + al_haras",
        "Helper READY; full Solutions API external",
        "Governance",
    ),
    Capability(
        "E.GOV.PROVENANCE_HASH",
        "SHA-256 provenance on envelopes",
        CapStatus.PARTIAL,
        "governance",
        "enterprise_bridge.emit_envelope",
        "Local envelope helper; passport mint external",
        "Governance",
    ),
    Capability(
        "E.GOV.WORM_AUDIT",
        "WORM / append-only audit",
        CapStatus.PARTIAL,
        "governance",
        "al_haras",
        "Core present; not full institutional ABAC product",
        "Governance",
    ),
    Capability(
        "E.GOV.ABAC",
        "Attribute-based access control product",
        CapStatus.EXTERNAL,
        "governance",
        "HYBA Intelligence enterprise ABAC",
        "Not the full product API in this mining proof repo",
        "Governance",
    ),
    # API / Millennium / MRI — honest external
    Capability(
        "E.API.SOLUTIONS_V1",
        "Phase-1 Solutions API 18 endpoints",
        CapStatus.EXTERNAL,
        "api",
        "HYBA Intelligence /api/v1/solutions",
        "Do not fake endpoints here",
        "API",
    ),
    Capability(
        "E.MILLENNIUM.SOLVERS",
        "Millennium mathematical engines",
        CapStatus.PARTIAL,
        "millennium",
        "millennium/ + hyba_data",
        "Engines/demos ≠ Clay conjecture resolutions",
        "API",
    ),
    Capability(
        "E.MRI.SL3Z",
        "Discrete unimodular 3D MRI substrate",
        CapStatus.EXTERNAL,
        "mri",
        "Intelligence native_kernels / papers",
        "No clinical claims; not canonical in this tree",
        "API",
    ),
    Capability(
        "E.QUANTUM.NEAR_STATE_10K",
        "Near-state 10k-qubit execution claims",
        CapStatus.STRETCH,
        "quantum",
        "turing paths if any",
        "Do not migrate unmeasured rooflines",
        "API",
    ),
    # Cortex
    Capability(
        "E.CORTEX.FOLDED_TRAINING",
        "Folded-state training / NCCL cortex",
        CapStatus.ABSENT,
        "cortex",
        "cortex_plugin / Intelligence",
        "Early scaffold at best; not triad-owned",
        "Cortex",
    ),
)


@dataclass
class EnterpriseCapabilityReport:
    """Machine-readable migration report for Intelligence CI."""

    generated_at: str
    governance: str = "Veritas Integritas Rule 7"
    thesis: str = "The Folded Form is the Working Form"
    mining_proof_ground: bool = True
    triad_ready: bool = True
    capabilities: List[Dict[str, Any]] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)
    migrate_now: List[str] = field(default_factory=list)
    do_not_claim_here: List[str] = field(default_factory=list)
    claim_boundary: str = (
        "This report enumerates measured capability status in the mining "
        "proof-ground repo. It does not certify the full HYBA Intelligence "
        "commercial suite, Solutions API, clinical MRI, or Clay resolutions."
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def report(
    *,
    include: Optional[Iterable[CapStatus]] = None,
) -> EnterpriseCapabilityReport:
    """Build the enterprise migration capability report."""
    wanted = set(include) if include is not None else None
    rows: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {s.value: 0 for s in CapStatus}
    migrate_now: List[str] = []
    refuse: List[str] = []
    for cap in CAPABILITIES:
        counts[cap.status.value] = counts.get(cap.status.value, 0) + 1
        if wanted is not None and cap.status not in wanted:
            continue
        rows.append(
            {
                "id": cap.id,
                "title": cap.title,
                "status": cap.status.value,
                "owner": cap.owner,
                "surface": cap.surface,
                "pillar": cap.pillar,
                "notes": cap.notes,
            }
        )
        if cap.status is CapStatus.READY:
            migrate_now.append(cap.id)
        if cap.status in {CapStatus.EXTERNAL, CapStatus.ABSENT, CapStatus.STRETCH}:
            refuse.append(cap.id)
    # triad_ready iff core fold/store/heal/chronus non-claims ready
    core = {
        "E.FOLD.WORKING_FORM",
        "E.STORE.SELF_HEAL",
        "E.STORE.PRIME_KEY",
        "E.COMPUTE.CHRONUS_DEVICE",
        "E.GOV.CLAIM_BOUNDARY",
    }
    triad_ready = core.issubset(set(migrate_now))
    return EnterpriseCapabilityReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        triad_ready=triad_ready,
        capabilities=rows,
        counts=counts,
        migrate_now=sorted(migrate_now),
        do_not_claim_here=sorted(refuse),
    )


def capability_by_id(cap_id: str) -> Optional[Capability]:
    for cap in CAPABILITIES:
        if cap.id == cap_id:
            return cap
    return None


def assert_ready(cap_id: str) -> Capability:
    """Fail closed if a host tries to advertise a non-READY capability as local."""
    cap = capability_by_id(cap_id)
    if cap is None:
        raise KeyError(f"unknown capability id: {cap_id}")
    if cap.status is not CapStatus.READY:
        raise RuntimeError(
            f"capability {cap_id} status={cap.status.value} — "
            f"cannot advertise as local production (Rule 7)"
        )
    return cap


def provenance_hash(payload: Mapping[str, Any] | bytes | str) -> str:
    if isinstance(payload, (bytes, bytearray)):
        body = bytes(payload)
    elif isinstance(payload, str):
        body = payload.encode("utf-8")
    else:
        body = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode(
            "utf-8"
        )
    return hashlib.sha256(body).hexdigest()


def emit_envelope(
    payload: Any,
    *,
    truth_class: TruthClass | str = TruthClass.MEASURED,
    capability_id: Optional[str] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Solutions-API-shaped envelope fragment for enterprise hosts.

    Does **not** implement `/api/v1/solutions`. It only provides the
    constitutional fields the brief requires: truth_class + provenance_hash.
    """
    if isinstance(truth_class, str):
        try:
            truth_class = TruthClass(truth_class)
        except ValueError:
            truth_class = TruthClass.UNVERIFIED
    body: Dict[str, Any] = {
        "schema": "hyba.enterprise_envelope.v1",
        "truth_class": truth_class.value
        if isinstance(truth_class, TruthClass)
        else str(truth_class),
        "payload": payload,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "aethel.enterprise_bridge",
        "mining_proof_ground": True,
    }
    if capability_id is not None:
        cap = capability_by_id(capability_id)
        body["capability_id"] = capability_id
        body["capability_status"] = cap.status.value if cap else "UNKNOWN"
        if cap is not None and cap.status is not CapStatus.READY:
            body["advertisement"] = "not_local_production"
    if extra:
        body["extra"] = dict(extra)
    body["provenance_hash"] = provenance_hash(
        {k: v for k, v in body.items() if k != "provenance_hash"}
    )
    return body


def open_enterprise_store(*, durable: bool = True, bind_chronus: bool = False):
    """Convenience: open the mining-proven triad as the enterprise store kernel."""
    from .triad import open_triad

    return open_triad(durable=durable, bind_chronus=bind_chronus)


def smoke_measured_put(payload: bytes = b"enterprise-bridge-smoke") -> Dict[str, Any]:
    """Measured put/get through Theseus/Ovid; returns envelope (Rule 7 measured)."""
    from .triad import open_triad

    db = open_triad(durable=True, bind_chronus=False)
    rec = db.put(payload, durable=True)
    got = db.get(rec.uuid)
    ok = got == payload
    return emit_envelope(
        {
            "ok": ok,
            "uuid": rec.uuid,
            "anchor": rec.anchor,
            "lane": rec.lane,
            "prime_key": rec.prime_key,
            "digest": rec.digest,
            "folded_units": rec.folded_units,
        },
        truth_class=TruthClass.MEASURED if ok else TruthClass.UNVERIFIED,
        capability_id="E.STORE.SELF_HEAL",
    )


__all__ = [
    "CapStatus",
    "TruthClass",
    "Capability",
    "CAPABILITIES",
    "EnterpriseCapabilityReport",
    "report",
    "capability_by_id",
    "assert_ready",
    "provenance_hash",
    "emit_envelope",
    "open_enterprise_store",
    "smoke_measured_put",
]
