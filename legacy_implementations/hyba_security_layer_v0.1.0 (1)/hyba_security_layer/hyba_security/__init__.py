"""HYBA security layer.

BASE (assessed KEEP / LANDED - withstands scrutiny):
  - aead              classical AEAD, ChaCha20-Poly1305 + HKDF-SHA256
  - audit_chain       tamper-evident hash chain + Merkle proofs
  - production_guard  fail-closed launch gate

BUILT ON TOP:
  - claims            claim-lane registry + external language gate
  - ci_claim_scan     AST scanner that fails CI on fake crypto

NOT IMPLEMENTED (declared, not hidden):
  - post-quantum KEM / signatures
  - topological protection as a cryptographic control

The import boundary is enforced in code: `legacy` is a defect reference and is
not re-exported here.
"""

from __future__ import annotations

from . import aead, audit_chain, claims, production_guard
from .aead import AeadAuthError, AeadError, AeadFormatError, open_sealed, seal
from .audit_chain import AuditChain
from .claims import ClaimViolation, assert_external_safe, posture
from .production_guard import evaluate, is_ready

__all__ = [
    "aead",
    "audit_chain",
    "claims",
    "production_guard",
    "seal",
    "open_sealed",
    "AeadError",
    "AeadFormatError",
    "AeadAuthError",
    "AuditChain",
    "evaluate",
    "is_ready",
    "assert_external_safe",
    "ClaimViolation",
    "posture",
]

__version__ = "0.1.0"


def security_posture() -> dict:
    """Single call an auditor can run to see exactly what is claimed."""
    return {
        "version": __version__,
        "aead": aead.describe(),
        "claims": claims.posture(),
        "fail_closed": True,
    }
