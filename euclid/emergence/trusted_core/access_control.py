"""Access control, governance capability tokens, and caller boundary enforcement."""

from __future__ import annotations
import inspect
import hmac
import hashlib
import time
from dataclasses import dataclass
from typing import Set


class UnauthorizedOperationalLoopCallError(PermissionError):
    """Raised when an operational-loop caller attempts to invoke trusted-core qualification."""
    pass


class InvalidGovernanceTokenError(PermissionError):
    """Raised when an invocation lacks a cryptographically valid governance token."""
    pass


@dataclass(frozen=True)
class GovernanceToken:
    """Capability-based access token issued only to trusted governance/assurance officers."""
    issuer: str
    officer_id: str
    issued_at: float
    expires_at: float
    token_digest: str

    @classmethod
    def issue(cls, officer_id: str, secret_key: str, ttl_seconds: float = 3600.0) -> GovernanceToken:
        now = time.time()
        expiry = now + ttl_seconds
        payload = f"euclid:governance:{officer_id}:{now}:{expiry}"
        digest = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return cls(
            issuer="euclid.trusted_core.governance_authority",
            officer_id=officer_id,
            issued_at=now,
            expires_at=expiry,
            token_digest=digest,
        )

    def verify(self, secret_key: str) -> bool:
        now = time.time()
        if now > self.expires_at:
            return False
        payload = f"euclid:governance:{self.officer_id}:{self.issued_at}:{self.expires_at}"
        expected = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.token_digest)


class CallerBoundaryGuard:
    """Enforces strict module visibility and execution boundary checks at runtime."""

    FORBIDDEN_FRAME_PATTERNS: Set[str] = {
        "operational_loop",
        "agent_loop",
        "worker_loop",
        "execution_loop",
        "policy_loop",
    }

    @classmethod
    def assert_trusted_caller(cls) -> None:
        stack = inspect.stack()
        for frame_info in stack:
            filename = frame_info.filename.replace("\\", "/").lower()
            function_name = frame_info.function.lower()

            for pattern in cls.FORBIDDEN_FRAME_PATTERNS:
                if pattern in filename or pattern in function_name:
                    raise UnauthorizedOperationalLoopCallError(
                        f"Principle Violation: Emergent capability self-certification forbidden. "
                        f"Operational loop detected in call stack: frame={function_name} in file={frame_info.filename}"
                    )
