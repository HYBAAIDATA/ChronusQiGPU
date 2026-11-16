"""Evidence-based production admission.

Provider names, source presence and green unit tests cannot award production
status. Only exact-commit attestation plus all mandatory product gates can.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from chronus.crypto import signers

MANDATORY = ("CO-SIGN", "RS-RECEIPT", "RS-REPLAY", "FN-CLAIMS", "FN-CUSTODY")


@dataclass(frozen=True)
class Verdict:
    status: str
    unqualified: tuple[str, ...]


def qualify(
    require_pq: bool = True,
    ci_gates: Mapping[str, str] | None = None,
    attestation_verified: bool = False,
    key_provider: str = "local-memory",
) -> Verdict:
    """Return PASS only for attested mandatory gates.

    key_provider is retained for compatibility and reporting only. Custody
    qualification belongs to the attested FN-CUSTODY gate; a caller-supplied
    vendor/provider label cannot itself create production credit.
    """
    blockers: list[str] = []
    if require_pq and not signers.ml_dsa_available():
        blockers.append("ML-DSA-65 unavailable")
    if not attestation_verified:
        blockers.append("CI artifact attestation not verified")
    for gate in MANDATORY:
        if ci_gates is None or ci_gates.get(gate) != "PASS":
            blockers.append(gate + " not PASS")
    return Verdict("PASS" if not blockers else "UNQUALIFIED", tuple(blockers))
