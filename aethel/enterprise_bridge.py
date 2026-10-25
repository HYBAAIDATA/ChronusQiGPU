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
from pathlib import Path
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

    Capability(
        "E.STORE.CONSENSUS_LOCAL",
        "Distributed consensus (local multi-node Raft-like)",
        CapStatus.READY,
        "theseus",
        "aethel.enterprise.distributed.MultiNodeCluster",
        "Scope: distributed_consensus_software_multi_node_local — in-process majority commit",
        "Pulvini",
    ),
    Capability(
        "E.STORE.MULTI_ROOT",
        "Multi-root multi-node custody",
        CapStatus.READY,
        "theseus",
        "aethel.enterprise.distributed.MultiRootCustody",
        "Scope: multi_root_multi_node_custody_software — distinct root per node",
        "Pulvini",
    ),
    Capability(
        "E.STORE.DR_SIMULATED",
        "Cross-region DR (simulated regions)",
        CapStatus.READY,
        "theseus",
        "aethel.enterprise.distributed.CrossRegionDR",
        "Scope: cross_region_dr_software_simulated_regions — not real multi-geo WAN",
        "Pulvini",
    ),
    Capability(
        "E.STORE.SOAK_LOCAL_FLEET",
        "Hyperscaler soak (local multi-worker fleet)",
        CapStatus.READY,
        "theseus",
        "aethel.enterprise.distributed.HyperscalerSoak",
        "Scope: hyperscaler_soak_software_local_fleet — not infinite cloud",
        "Pulvini",
    ),
    Capability(
        "E.COMPUTE.CHRONUS_PERF_PROBE",
        "Chronus hardware perf probe (honest CPU/accel)",
        CapStatus.READY,
        "chronus",
        "aethel.enterprise.distributed.ChronusPerfProbe",
        "Scope: chronus_hardware_perf_measured — never invents device FLOPS",
        "Accel",
    ),
    Capability(
        "E.API.SOLUTIONS_SOFTWARE_FACADE",
        "Solutions API readiness (in-process facade)",
        CapStatus.READY,
        "api",
        "aethel.enterprise.solutions_api.SolutionsAPI",
        "Scope: solutions_api_readiness_software — not product /api/v1/solutions suite",
        "API",
    ),
    Capability(
        "E.GOV.HYBA_CERT_GATE",
        "Enterprise HYBA certification gate (software)",
        CapStatus.READY,
        "governance",
        "aethel.enterprise.distributed.HybaEnterpriseCertificate",
        "Scope: enterprise_hyba_certification_gate_software — PASS only if all evidence passes",
        "Governance",
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
    """Machine-readable migration report for Intelligence CI.

    Catalogue CapStatus values are **declarative**. Independent promotion to
    operational READY requires named acceptance evidence. Report surfaces never
    emit unqualified production_ready=true.
    """

    generated_at: str
    governance: str = "Veritas Integritas Rule 7"
    thesis: str = "The Folded Form is the Working Form"
    catalogue_is_declarative: bool = True
    evidence_drives_readiness: bool = True
    software_readiness_scope: str = "enterprise_custody_software_single_root"
    readiness_kind: str = "scoped_software"
    extended_software_scopes: List[str] = field(
        default_factory=lambda: [
            "enterprise_custody_software_single_root",
            "distributed_consensus_software_multi_node_local",
            "multi_root_multi_node_custody_software",
            "cross_region_dr_software_simulated_regions",
            "hyperscaler_soak_software_local_fleet",
            "chronus_hardware_perf_measured",
            "solutions_api_readiness_software",
            "enterprise_hyba_certification_gate_software",
        ]
    )
    # Never true for whole-system / hyperscaler / hardware
    production_ready: bool = False
    production_ready_note: str = (
        "production_ready is always false at report level. "
        "Use software_readiness_scope / extended_software_scopes for scoped claims only."
    )
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
        d = asdict(self)
        # Hard rule: never surface unqualified production_ready=true
        d["production_ready"] = False
        d.setdefault(
            "triad_ready_note",
            "Declarative catalogue AND local triad import smoke only; "
            "not hyperscaler/whole-system production readiness.",
        )
        d.setdefault("catalogue_is_declarative", True)
        d.setdefault("evidence_drives_readiness", True)
        d.setdefault("readiness_kind", "scoped_software")
        d.setdefault(
            "software_readiness_scope",
            "enterprise_custody_software_single_root",
        )
        return d

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
    """Fail closed if catalogue status is not READY (declarative, not production proof)."""
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
    """SHA-256 integrity hash over canonical payload bytes.

    This is integrity, not authenticity. HMAC authenticity is owned by
    Theseus custody (aethel.enterprise.authenticity) and is never implied
    by this envelope field.
    """
    if isinstance(payload, (bytes, bytearray)):
        body = bytes(payload)
    elif isinstance(payload, str):
        body = payload.encode("utf-8")
    else:
        body = json.dumps(
            dict(payload), sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def compute_envelope_provenance_hash(body: Mapping[str, Any]) -> str:
    """Recompute envelope provenance the same way envelope_response seals it.

    Tests must assert equality against the recomputed hash, not merely that
    the existing value is 64 hex characters.
    """
    sealed = {k: v for k, v in dict(body).items() if k != "provenance_hash"}
    return provenance_hash(sealed)


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
    # SHA-256 integrity only (not HMAC authenticity)
    body["provenance_hash"] = provenance_hash(
        {k: v for k, v in body.items() if k != "provenance_hash"}
    )
    return body


def open_enterprise_store(
    *,
    durable: bool = True,
    durable_dir: str | Path | None = None,
    bind_chronus: bool = False,
):
    """Open canonical enterprise custody with an explicit persistence boundary.

    ``durable=True`` requires a real directory binding. Callers intentionally
    using memory-only custody must pass ``durable=False``. The low-level
    ``open_triad`` / ``open_theseus`` compatibility contracts are unchanged.
    No legacy root migration, tenant identity or network admission is implied.
    """
    if type(durable) is not bool:
        raise TypeError("durable must be a bool")
    if durable and (durable_dir is None or str(durable_dir).strip() == ""):
        raise ValueError("durable enterprise custody requires durable_dir")
    if not durable and durable_dir is not None:
        raise ValueError("durable=False cannot bind durable_dir")
    from .triad import THESEUS_CUSTODY_PROFILE, open_triad

    return open_triad(
        durable=durable,
        durable_dir=durable_dir,
        storage_profile=THESEUS_CUSTODY_PROFILE,
        bind_chronus=bind_chronus,
    )


def smoke_measured_put(
    payload: bytes = b"enterprise-bridge-smoke",
    *,
    durable_dir: str | Path | None = None,
) -> Dict[str, Any]:
    """Commit, read and reattach a directory-bound Theseus/Ovid store.

    Retain the supplied directory for inspection. This is local integrity
    evidence, not independent attestation, authentication, a process-restart
    test, a commercial savings measurement or launch qualification.
    """
    db = open_enterprise_store(durable_dir=durable_dir, bind_chronus=False)
    rec = db.put(payload, durable=True)
    got = db.get(rec.uuid)
    # Exercise the public factory's attach path instead of only reading the
    # still-live owner's primary/replica memory. A separate process test is
    # required before claiming process-restart survival.
    reopened = open_enterprise_store(durable_dir=durable_dir, bind_chronus=False)
    restored = reopened.get(rec.uuid)
    custody = reopened.health()["custody"]
    ok = (
        got == payload
        and restored == payload
        and hashlib.sha256(restored).hexdigest() == rec.digest
        and reopened.verify() is True
        and custody.get("authority") == "theseus"
        and custody.get("disk_bound") is True
        and custody.get("integrity_verified") is True
    )
    if not ok:
        raise RuntimeError("enterprise durable smoke verification failed")
    return emit_envelope(
        {
            "ok": True,
            "uuid": rec.uuid,
            "anchor": rec.anchor,
            "lane": rec.lane,
            "prime_key": rec.prime_key,
            "digest": rec.digest,
            "folded_units": rec.folded_units,
            "custody": custody,
            "storage_profile": reopened.storage_profile,
            "restart_evidence": "reattach_same_process",
        },
        truth_class=TruthClass.MEASURED,
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
    "compute_envelope_provenance_hash",
    "emit_envelope",
    "open_enterprise_store",
    "smoke_measured_put",
]
