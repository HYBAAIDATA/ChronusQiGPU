"""Claims are held unless the attested gates and declared profile support them."""
from __future__ import annotations

from typing import Any, Mapping

CLAIM_GATES = {
    "CO-001": ("CO-SIGN",),
    "CO-002": ("CO-SIGN", "RS-RECEIPT"),
    "RS-001": ("RS-RECEIPT", "RS-REPLAY"),
    "RS-002": ("RS-REPLAY", "FN-CUSTODY"),
    # FN-001 is specifically the external/customer-held custody claim.
    "FN-001": ("FN-CLAIMS", "FN-CUSTODY"),
}

SOFTWARE_BASE_REQUIRED_CLAIMS = ("CO-001", "CO-002", "RS-001", "RS-002")


def dispositions(
    gates: Mapping[str, str],
    attestation_verified: bool,
    *,
    deployment_profile: str | None = None,
    product_facts: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    facts = product_facts or {}
    result: dict[str, str] = {}
    for claim, required in CLAIM_GATES.items():
        supported = bool(
            attestation_verified and all(gates.get(gate) == "PASS" for gate in required)
        )
        if claim == "FN-001":
            custody = facts.get("custody")
            supported = bool(
                supported
                and isinstance(custody, Mapping)
                and custody.get("verified") is True
                and custody.get("external_customer_key_custody") is True
            )
        result[claim] = "supported" if supported else "held"
    return result


def required_claims_for_profile(deployment_profile: str | None) -> tuple[str, ...]:
    if deployment_profile == "software-base":
        return SOFTWARE_BASE_REQUIRED_CLAIMS
    # Deployment profiles must explicitly satisfy every governed claim unless
    # a future profile contract defines a narrower, reviewed set.
    return tuple(CLAIM_GATES)
