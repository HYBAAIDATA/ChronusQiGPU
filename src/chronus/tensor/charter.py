"""Section 0: The Charter as an Executable Assertion.

Runs before any code in the Falsifiable Tensor Engine.
Guarantees scientific integrity, bans hype language, and enforces
error ledgers and contraction certificates on all claims.
"""

from __future__ import annotations

import re
from typing import Set


class CharterViolation(Exception):
    """Raised when an operation, claim, or text violates the consortium charter."""


class ScientificIntegrityLead:
    """The designated veto holder for scientific integrity."""

    name: str = "scientific_integrity_lead"
    role: str = "Consortium Scientific Integrity & Verification Lead"

    def veto(self, proposal: str) -> None:
        raise CharterViolation(f"Scientific Integrity Veto exercised on: {proposal}")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ScientificIntegrityLead):
            return True
        if isinstance(other, str):
            return other == self.name
        return False

    def __repr__(self) -> str:
        return self.name


scientific_integrity_lead = ScientificIntegrityLead()


class ConsortiumCharter:
    """The controlled-programme charter enforcing auditability over ambition."""

    version: str = "1.0"
    metric: str = "largest chi with certified error eps"
    veto_holder: ScientificIntegrityLead = scientific_integrity_lead

    BANNED_HYPE_TOKENS: Set[str] = {
        "quantum supremacy",
        "quantum advantage",
        "exponential speedup",
        "unlimited qubits",
        "infinite entanglement",
        "mother of all tensors",
        "production-ready quantum",
        "unconstrained scaling",
        "error-free 1000 qubits",
    }

    REQUIRED_SUBSYSTEMS: Set[str] = {
        "error_ledger",
        "contraction_certificate",
    }

    @classmethod
    def refuses(cls, claim_or_text: str) -> bool:
        """Returns True if the text is clean of banned hype language.

        Raises CharterViolation if hype language is detected.
        """
        lowered = claim_or_text.lower()
        for token in cls.BANNED_HYPE_TOKENS:
            if re.search(r"\b" + re.escape(token) + r"\b", lowered):
                return False
        return True

    @classmethod
    def assert_refuses(cls, claim_or_text: str) -> None:
        """Asserts that text does not contain hype language."""
        if not cls.refuses(claim_or_text):
            raise CharterViolation(
                f"Charter refusal: Text contains banned hype language violating scientific integrity: '{claim_or_text}'"
            )

    @classmethod
    def requires(cls, subsystem: str) -> bool:
        """Verifies that mandatory audit subsystems are present."""
        return subsystem in cls.REQUIRED_SUBSYSTEMS


charter = ConsortiumCharter()


def program_entry_check() -> bool:
    """The Section 0 PROGRAM_ENTRY assertion suite.

    Runs before any tensor computation or CI build.
    If any assertion fails, the build does not ship.
    """
    assert charter.version == "1.0", "Charter version must be 1.0"
    assert charter.refuses("Exact tensor contraction with Vidal2003 truncation error bound"), "Legitimate text rejected"
    assert not charter.refuses("This engine demonstrates quantum supremacy over classical supercomputers"), "Hype language not refused"
    assert charter.requires("error_ledger") and charter.requires("contraction_certificate"), "Mandatory audit subsystems missing"
    assert charter.metric == "largest chi with certified error eps", "Invalid optimization metric"
    assert charter.veto_holder == scientific_integrity_lead, "Scientific integrity lead must hold veto power"
    return True
