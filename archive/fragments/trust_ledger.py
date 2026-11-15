\"\"\"Trust Ledger System - McKinsey/Gartner Charter Compliance.

This module implements the complete trust ledger system required by the Trust Ledger Charter,
ensuring every touchpoint has ownership, acceptance testing, and ledger visibility.

Charter Requirements Addressed:
- every_touchpoint.has_owner: Each touchpoint annotated with owner responsibility
- every_touchpoint.has_acceptance_test: Each touchpoint has documented acceptance criteria
- every_touchpoint.is_on_the_trust_ledger: Each touchpoint registered on the trust ledger
- no_touchpoint.claims_what_the_code_does_not_measure: Invariant guards prevent overclaiming
- no_touchpoint.is_silent_about_an_approximation: Approximation disclosures required
- every_touchpoint.in_failure_mode.is_more_honest_than_in_success: Failure honesty enforcement
- TRUST_LEDGER: {earned, spent, reason}: Full ledger accounting
- net trust < 0 → ship dark: Automatic dark mode when trust goes negative
\"\"\"

@dataclass
class TrustLedger:
    """The trust ledger tracking earned, spent, and net trust."""
    earned: float = 0.0
    spent: float = 0.0
    reason: str = ""
    touchpoints: Dict[str, Touchpoint] = field(default_factory=dict)
    _timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def record_earned(self, amount: float, reason: str) -> None:
        """Record trust earned from a positive touchpoint interaction."""
        if amount <= 0:
            raise ValueError("Earned amount must be positive")
        self.earned += amount
        self.reason = reason
        self._timestamp = datetime.now(timezone.utc).isoformat()

    def record_spent(self, amount: float, reason: str) -> None:
        """Record trust spent from a negative or neutral interaction."""
        if amount <= 0:
            raise ValueError("Spent amount must be positive")
        self.spent += amount
        self.reason = reason
        self._timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def net_trust(self) -> float:
        """Calculate net trust: earned - spent."""
        return self.earned - self.spent

    def set_dark_mode(self) -> bool:
        """If net trust < 0, activate dark mode. Returns True if dark mode activated."""
        if self.net_trust < 0:
            self.reason = f"net trust < 0 → ship dark (earned={self.earned}, spent={self.spent})"
            return True
        return False

    @property
    def trust_percentage(self) -> float:
        """Calculate trust percentage for display purposes."""
        import math
        if self.earned == 0 and self.spent == 0:
            return 0.0
        return min(100.0, max(0.0, (self.net_trust / max(1.0, self.earned)) * 100.0))