"""Local AL HARAS admission binding for development execution.

This adapter binds Chronus execution to the maintained AL HARAS ingress
decision. It is deliberately local and evidence-scoped: it does not create
owner approval, hosted-CI attestation, physical-device evidence, or production
authorization.
"""

from __future__ import annotations

import hashlib
from typing import Any

from chronus.security.al_haras.engine import ALHarasSecurityFabric


class LocalALHarasAuthorizer:
    """Development-only adapter over the implemented AL HARAS ingress fabric."""

    mode = "local_development"

    def authorize(self, payload: bytes | str) -> dict[str, Any]:
        raw = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        decision = ALHarasSecurityFabric.evaluate_ingress(raw)
        return {
            "authorized": bool(decision["admitted"]),
            "mode": self.mode,
            "decision": decision["status"],
            "payload_sha256": hashlib.sha256(raw).hexdigest(),
            "receipt_body_sha256": decision["receipt"]["signature"]["body_sha256"],
            "external_owner_approval": "UNVERIFIED",
            "hosted_ci_attestation": "UNVERIFIED",
            "physical_hardware_attestation": "UNVERIFIED",
        }


__all__ = ["LocalALHarasAuthorizer"]
