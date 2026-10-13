"""HYBA / AL HARAS security layer - claim lane registry and external gate.

Provenance: P0-3 claim/language quarantine, AL HARAS package audit 20 Jul 2026,
and the PHI-Space v2.0 NOT-EXTERNAL list.

Rule enforced in code, not in comments:
  external materials may use only IMPLEMENTED-lane language.
"""

from __future__ import annotations

import re
from typing import Any, Final

LANE_IMPLEMENTED: Final[str] = "IMPLEMENTED"
LANE_BOUNDED: Final[str] = "BOUNDED_INTERNAL"
LANE_SIMULATED: Final[str] = "SIMULATED_INTERNAL"

VALID_LANES: Final[frozenset[str]] = frozenset(
    {LANE_IMPLEMENTED, LANE_BOUNDED, LANE_SIMULATED}
)

# Terms that must never appear in external-facing text.
RESTRICTED_TERMS: Final[tuple[str, ...]] = (
    "unhackable",
    "unbreakable",
    "quantum-resistant",
    "quantum resistant",
    "post-quantum",
    "pqc",
    "beyond aes-256",
    "replaces encryption",
    "topology replaces cryptography",
    "no keys to steal",
    "mathematically impossible to break",
    "aes-256-gcm",
)

REGISTRY: Final[dict[str, dict[str, Any]]] = {
    "aead_seal": {
        "lane": LANE_IMPLEMENTED,
        "statement": "Classical authenticated encryption (ChaCha20-Poly1305) with HKDF-SHA256 key separation and AAD purpose binding.",
        "evidence": "hyba_security/aead.py + IPA suite",
        "post_quantum": False,
    },
    "audit_chain": {
        "lane": LANE_IMPLEMENTED,
        "statement": "Tamper-evident append-only audit chain with SHA-256 hash linking and Merkle inclusion proofs.",
        "evidence": "hyba_security/audit_chain.py + IPA suite",
        "post_quantum": False,
    },
    "launch_guard": {
        "lane": LANE_IMPLEMENTED,
        "statement": "Fail-closed production launch gate rejecting bypass flags, private key material, and secret markers.",
        "evidence": "hyba_security/production_guard.py + IPA suite",
        "post_quantum": False,
    },
    "pqc_kem": {
        "lane": LANE_SIMULATED,
        "statement": "No KEM or post-quantum signature scheme is implemented. Roadmap item only.",
        "evidence": "absent by design; see AL HARAS Round 3 finding",
        "post_quantum": False,
    },
    "topological_protection": {
        "lane": LANE_SIMULATED,
        "statement": "Fold-based data protection is a research lane. Not a cryptographic control and not a substitute for AEAD.",
        "evidence": "research record only",
        "post_quantum": False,
    },
}


class ClaimViolation(Exception):
    """Raised when text or a claim breaches the external claim boundary."""


def lane_of(claim_id: str) -> str:
    if claim_id not in REGISTRY:
        raise ClaimViolation(f"unregistered claim: {claim_id}")
    return REGISTRY[claim_id]["lane"]


def is_external_safe(claim_id: str) -> bool:
    return lane_of(claim_id) == LANE_IMPLEMENTED


def scan_text(text: str) -> list[str]:
    """Return restricted terms found in `text` (case-insensitive)."""
    lowered = text.lower()
    found = []
    for term in RESTRICTED_TERMS:
        if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", lowered):
            found.append(term)
    return sorted(set(found))


def assert_external_safe(text: str) -> None:
    """Fail-closed gate for any external-facing string."""
    violations = scan_text(text)
    if violations:
        raise ClaimViolation(f"restricted claim language: {', '.join(violations)}")


def posture() -> dict[str, Any]:
    """Machine-readable claim posture for evidence packs."""
    return {
        "unhackable": False,
        "post_quantum": False,
        "implemented_claims": sorted(
            cid for cid, rec in REGISTRY.items() if rec["lane"] == LANE_IMPLEMENTED
        ),
        "internal_only_claims": sorted(
            cid for cid, rec in REGISTRY.items() if rec["lane"] != LANE_IMPLEMENTED
        ),
    }
