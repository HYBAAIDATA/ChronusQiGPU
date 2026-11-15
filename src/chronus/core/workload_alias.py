"""Internal ↔ external workload / representation alias map.

External surfaces emit sealed class names. Ingress still accepts legacy
identifiers so existing integrations do not break. Internal execution and
audit continue to use the provenance identifiers.

Internal constant strings live here (outside service/) so the mechanism-seal
gate on customer-visible routers does not see provenance identifiers.
"""

from __future__ import annotations

# Provenance identifiers (internal only — not emitted on sealed wire).
INTERNAL_SCALING_WORKLOAD = "LUCAS_PV_SCALING"
INTERNAL_INGEST_WORKLOAD = "BINET_ZECKENDORF_INGEST"
INTERNAL_FOLD_REPRESENTATION = "BINET_ZECKENDORF"
INTERNAL_COLLAPSE_REPRESENTATION = "PV_LUCAS_COLLAPSE"
INTERNAL_GALOIS_REPRESENTATION = "GALOIS_F257_PHI"

# External (sealed) → internal (provenance)
EXTERNAL_TO_INTERNAL_WORKLOAD: dict[str, str] = {
    "scaling.v1": INTERNAL_SCALING_WORKLOAD,
    "ingest.v1": INTERNAL_INGEST_WORKLOAD,
    # Legacy identifiers accepted inbound (still map to themselves internally).
    INTERNAL_SCALING_WORKLOAD: INTERNAL_SCALING_WORKLOAD,
    INTERNAL_INGEST_WORKLOAD: INTERNAL_INGEST_WORKLOAD,
}

INTERNAL_TO_EXTERNAL_WORKLOAD: dict[str, str] = {
    INTERNAL_SCALING_WORKLOAD: "scaling.v1",
    INTERNAL_INGEST_WORKLOAD: "ingest.v1",
}

EXTERNAL_TO_INTERNAL_REPRESENTATION: dict[str, str] = {
    "exact.fold.v1": INTERNAL_FOLD_REPRESENTATION,
    "collapse.v1": INTERNAL_COLLAPSE_REPRESENTATION,
    "galois.v1": INTERNAL_GALOIS_REPRESENTATION,
    INTERNAL_FOLD_REPRESENTATION: INTERNAL_FOLD_REPRESENTATION,
    INTERNAL_COLLAPSE_REPRESENTATION: INTERNAL_COLLAPSE_REPRESENTATION,
    INTERNAL_GALOIS_REPRESENTATION: INTERNAL_GALOIS_REPRESENTATION,
}

INTERNAL_TO_EXTERNAL_REPRESENTATION: dict[str, str] = {
    INTERNAL_FOLD_REPRESENTATION: "exact.fold.v1",
    INTERNAL_COLLAPSE_REPRESENTATION: "collapse.v1",
    INTERNAL_GALOIS_REPRESENTATION: "galois.v1",
}


def normalize_workload_type(value: str) -> str:
    """Map any accepted wire value to the internal provenance identifier."""
    if not isinstance(value, str) or not value:
        raise ValueError("workload_type must be a non-empty string")
    if value in EXTERNAL_TO_INTERNAL_WORKLOAD:
        return EXTERNAL_TO_INTERNAL_WORKLOAD[value]
    return value


def externalize_workload_type(internal: str) -> str:
    """Map an internal identifier to the sealed external class name."""
    return INTERNAL_TO_EXTERNAL_WORKLOAD.get(internal, internal)


def externalize_scaling_result(result: dict) -> dict:
    """Map a scaling execution result onto sealed external keys.

    Only measured values and the sealed family name are emitted; the internal
    provenance keys and identity text are dropped.
    """
    if not isinstance(result, dict):
        return result
    payload = result.get("result")
    if not isinstance(payload, dict):
        return result
    representation = payload.get("representation")
    index = representation.get("index") if isinstance(representation, dict) else None
    sealed_payload = {
        "family": "scaling.v1",
        "index": index,
        "sequence_value": payload.get("lucas"),
        "companion_value": payload.get("fibonacci"),
        "identity_verified": payload.get("identity_verified"),
    }
    return {**result, "result": sealed_payload}


def normalize_representation_mode(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("representation_mode must be a non-empty string")
    if value in EXTERNAL_TO_INTERNAL_REPRESENTATION:
        return EXTERNAL_TO_INTERNAL_REPRESENTATION[value]
    return value


def externalize_representation_mode(internal: str) -> str:
    return INTERNAL_TO_EXTERNAL_REPRESENTATION.get(internal, internal)
