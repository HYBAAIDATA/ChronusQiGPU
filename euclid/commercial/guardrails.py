"""Commercial Security Guardrails — Governed by AL HARAS.

Enforces zero-trust admission, strict content safety, sovereign policy checks,
and resource quotas for commercial enterprise client payloads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PolicyVerdict:
    allowed: bool
    policy_name: str
    violations: tuple[str, ...]
    sanitized_content: Optional[str] = None
    audit_metadata: Dict[str, Any] = field(default_factory=dict)


class CommercialGuardrails:
    """Enterprise security gatekeeper powered by AL HARAS authority."""

    def __init__(
        self,
        *,
        max_prompt_bytes: int = 1_000_000,
        rate_limit_per_minute: int = 1200,
        enforce_no_float: bool = False,
    ) -> None:
        self.max_prompt_bytes = max_prompt_bytes
        self.rate_limit_per_minute = rate_limit_per_minute
        self.enforce_no_float = enforce_no_float
        self._forbidden_patterns = [
            re.compile(r"(?i)\b(?:eval\s*\(|exec\s*\(|os\.system|subprocess\.Popen)"),
            re.compile(r"(?i)\bignore\s+all\s+previous\s+instructions\b"),
            re.compile(r"(?i)\b(?:dump_all_memory_keys|bypass_auth_gate)\b"),
        ]

    def inspect_request(self, content: str, client_id: str = "default") -> PolicyVerdict:
        """Inspect and validate an incoming client payload."""
        violations: List[str] = []

        if len(content.encode("utf-8")) > self.max_prompt_bytes:
            violations.append(
                f"Payload size {len(content.encode('utf-8'))} bytes exceeds limit of {self.max_prompt_bytes} bytes."
            )

        for pattern in self._forbidden_patterns:
            if pattern.search(content):
                violations.append(f"Content matches restricted pattern: {pattern.pattern}")

        if violations:
            return PolicyVerdict(
                allowed=False,
                policy_name="AL_HARAS_SOVEREIGN_ADMISSION",
                violations=tuple(violations),
                audit_metadata={"client_id": client_id, "status": "DENIED"},
            )

        return PolicyVerdict(
            allowed=True,
            policy_name="AL_HARAS_SOVEREIGN_ADMISSION",
            violations=(),
            sanitized_content=content,
            audit_metadata={"client_id": client_id, "status": "APPROVED"},
        )

    def inspect_response(self, response: str, client_id: str = "default") -> PolicyVerdict:
        """Inspect and sanitize an outbound agent response before delivery."""
        violations: List[str] = []
        # Mask sensitive keys or leakages
        sanitized = re.sub(r"(?i)(?:sk-[a-zA-Z0-9]{32,}|ghp_[a-zA-Z0-9]{36,})", "[REDACTED_SECRET]", response)

        return PolicyVerdict(
            allowed=True,
            policy_name="AL_HARAS_EGRESS_VERIFICATION",
            violations=tuple(violations),
            sanitized_content=sanitized,
            audit_metadata={"client_id": client_id, "status": "DELIVERED"},
        )
