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


def _as_wire_str(value: object) -> str:
    """Coerce enum defaults / instances to their wire string value."""
    if hasattr(value, "value") and isinstance(getattr(value, "value"), str):
        return value.value  # type: ignore[no-any-return]
    if isinstance(value, str):
        return value
    raise ValueError(f"expected string or enum, got {type(value).__name__}")


def normalize_workload_type(value: object) -> str:
    """Map any accepted wire value to the internal provenance identifier."""
    text = _as_wire_str(value)
    if not text:
        raise ValueError("workload_type must be a non-empty string")
    if text in EXTERNAL_TO_INTERNAL_WORKLOAD:
        return EXTERNAL_TO_INTERNAL_WORKLOAD[text]
    return text


def externalize_workload_type(internal: object) -> str:
    """Map an internal identifier to the sealed external class name."""
    text = _as_wire_str(internal)
    return INTERNAL_TO_EXTERNAL_WORKLOAD.get(text, text)


def normalize_representation_mode(value: object) -> str:
    text = _as_wire_str(value)
    if not text:
        raise ValueError("representation_mode must be a non-empty string")
    if text in EXTERNAL_TO_INTERNAL_REPRESENTATION:
        return EXTERNAL_TO_INTERNAL_REPRESENTATION[text]
    return text


def externalize_representation_mode(internal: object) -> str:
    text = _as_wire_str(internal)
    return INTERNAL_TO_EXTERNAL_REPRESENTATION.get(text, text)


def normalize_pointer_operation(operation: str) -> str:
    """Map sealed pointer ops to internal uppercase dispatch keys."""
    text = operation.strip()
    if not text:
        raise ValueError("operation must be a non-empty string")
    # Sealed class names stay lowercase with dots; map before uppercasing.
    if text in EXTERNAL_TO_INTERNAL_WORKLOAD:
        return EXTERNAL_TO_INTERNAL_WORKLOAD[text]
    if text.lower() in EXTERNAL_TO_INTERNAL_WORKLOAD:
        return EXTERNAL_TO_INTERNAL_WORKLOAD[text.lower()]
    return text.upper()


def externalize_scaling_result(result: dict) -> dict:
    """Map a scaling execution result onto sealed external keys.

    Only measured values and the sealed family name are emitted; internal
    provenance keys and identity text are dropped from the customer view.
    """
    if not isinstance(result, dict):
        return result
    payload = result.get("result")
    if not isinstance(payload, dict):
        return result
    representation = payload.get("representation")
    nested_index = (
        representation.get("index") if isinstance(representation, dict) else None
    )
    # Already-sealed adapter payloads carry index at the top level.
    index = nested_index if nested_index is not None else payload.get("index")
    family = (
        representation.get("family") if isinstance(representation, dict) else None
    )
    already_sealed = (
        family == "scaling.v1"
        or payload.get("family") == "scaling.v1"
        or "sequence_value" in payload
        or "companion_value" in payload
    )
    is_scaling_payload = (
        already_sealed
        or family == "LUCAS_PISOT"
        or "lucas" in payload
        or "fibonacci" in payload
    )
    if not is_scaling_payload:
        return result
    sealed_payload = {
        "family": "scaling.v1",
        "index": index,
        "sequence_value": payload.get("sequence_value", payload.get("lucas")),
        "companion_value": payload.get("companion_value", payload.get("fibonacci")),
        "identity_verified": payload.get("identity_verified"),
    }
    return {**result, "result": sealed_payload}
