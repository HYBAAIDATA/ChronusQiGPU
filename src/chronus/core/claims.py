"""Claims are held unless all named attested CI gates PASS."""
from __future__ import annotations
from typing import Mapping
CLAIM_GATES = {
    "CO-001": ("CO-SIGN",),
    "CO-002": ("CO-SIGN", "RS-RECEIPT"),
    "RS-001": ("RS-RECEIPT", "RS-REPLAY"),
    "RS-002": ("RS-REPLAY", "FN-CUSTODY"),
    "FN-001": ("FN-CLAIMS", "FN-CUSTODY"),
}
def dispositions(gates: Mapping[str, str], attestation_verified: bool) -> dict[str, str]:
    return {claim: ("supported" if attestation_verified and all(gates.get(g) == "PASS" for g in required) else "held") for claim, required in CLAIM_GATES.items()}
