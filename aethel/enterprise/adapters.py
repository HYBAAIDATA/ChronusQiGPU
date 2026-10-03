"""Migration classification registry and mirror evidence helpers."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class StoreClass(str, Enum):
    CANONICAL = "canonical"
    REMAIN = "remain"
    PEER_LEGACY = "peer_legacy"
    ENTERPRISE_CUSTODY = "enterprise_custody"
    OUT_OF_SCOPE = "out_of_scope"
    MIRROR_EVIDENCE = "mirror_evidence"
    PROVISIONAL = "provisional"
    EXTERNAL = "external"
    SECURITY_AUTHORITY = "security_authority"
    OPTIONAL_ANCHOR = "optional_anchor"


@dataclass(frozen=True)
class StoreClassification:
    name: str
    store_class: StoreClass
    notes: str = ""


# Repo store classification (see docs/enterprise_triad/05_migration_classification.md)
CLASSIFICATION_REGISTRY: dict[str, StoreClassification] = {
    "address_space": StoreClassification(
        "AddressSpace",
        StoreClass.CANONICAL,
        "Topological addressing remains source of truth for manifold IDs.",
    ),
    "euclid": StoreClassification(
        "EUCLID",
        StoreClass.REMAIN,
        "Geometry helpers remain libraries; not absorbed into disk format.",
    ),
    "aethel.theseus": StoreClassification(
        "aethel.theseus",
        StoreClass.PEER_LEGACY,
        "Software triad Theseus path remains; enterprise adds journal+HMAC+tenants.",
    ),
    "aethel.enterprise": StoreClassification(
        "aethel.enterprise.EnterpriseCustody",
        StoreClass.ENTERPRISE_CUSTODY,
        "Single-root measured custody substrate.",
    ),
    "mining": StoreClassification(
        "mining/PhiMiner",
        StoreClass.OUT_OF_SCOPE,
        "Mining is proof ground only; not Intelligence migration proof.",
    ),
    "telemetry_mirror": StoreClassification(
        "EvidenceTelemetry/custody_events",
        StoreClass.MIRROR_EVIDENCE,
        "Counters and events; mirror_digest for bridge envelopes.",
    ),
    "hyperscaler_sku": StoreClassification(
        "HyperscalerSku",
        StoreClass.PROVISIONAL,
        "Must not inherit READY from single-root custody.",
    ),
    "geodesic": StoreClassification(
        "Geodesic/Solutions API",
        StoreClass.EXTERNAL,
        "Outside triad; do not mark READY in this tranche.",
    ),
    "al_haras": StoreClassification(
        "AL HARAS",
        StoreClass.SECURITY_AUTHORITY,
        "Hooks adapter only; policy not inside Theseus.",
    ),
    "cassini": StoreClassification(
        "Cassini/pulvini",
        StoreClass.OPTIONAL_ANCHOR,
        "May coexist; not required for enterprise envelope v1.",
    ),
}


def classify(name: str) -> Optional[StoreClassification]:
    return CLASSIFICATION_REGISTRY.get(name)


def wrap_notes(name: str, extra: str) -> str:
    c = classify(name)
    base = c.notes if c else ""
    return f"{base} | {extra}".strip(" |")


def mirror_digest(payload: dict[str, Any] | bytes | str) -> str:
    """SHA-256 over canonical JSON or raw bytes for evidence mirrors."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def classification_report() -> list[dict[str, str]]:
    return [
        {
            "key": key,
            "name": c.name,
            "class": c.store_class.value,
            "notes": c.notes,
        }
        for key, c in CLASSIFICATION_REGISTRY.items()
    ]


__all__ = [
    "StoreClass",
    "StoreClassification",
    "CLASSIFICATION_REGISTRY",
    "classify",
    "wrap_notes",
    "mirror_digest",
    "classification_report",
]
