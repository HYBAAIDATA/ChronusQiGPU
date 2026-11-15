"""Evidence-based status: only externally verified CI attestation can produce PASS."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from chronus.crypto import signers

MANDATORY = ("CO-SIGN", "RS-RECEIPT", "RS-REPLAY", "FN-CLAIMS", "FN-CUSTODY")
@dataclass(frozen=True)
class Verdict:
    status: str
    unqualified: tuple[str, ...]

def qualify(require_pq: bool = True, ci_gates: Mapping[str, str] | None = None, attestation_verified: bool = False, key_provider: str = "local-memory") -> Verdict:
    blockers = []
    if require_pq and not signers.ml_dsa_available():
        blockers.append("ML-DSA-65 unavailable")
    if key_provider != "azure-managed-hsm":
        blockers.append("Azure Managed HSM not verified")
    if not attestation_verified:
        blockers.append("CI artifact attestation not verified")
    for gate in MANDATORY:
        if ci_gates is None or ci_gates.get(gate) != "PASS":
            blockers.append(gate + " not PASS")
    return Verdict("PASS" if not blockers else "UNQUALIFIED", tuple(blockers))
