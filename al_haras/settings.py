"""Environment-backed AL HARAS runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Mapping


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ALHarasSettings:
    issuer: str
    keyring: Mapping[str, bytes]
    audit_path: Path
    policy_version: str = "al-haras.policy.v1"
    capability: str = "hyba.security"
    max_payload_bytes: int = 1_048_576
    require_intelligence_evidence: bool = False
    subscription_url: str = "/contact?product=hyba-security"
    audit_quarantine: bool = True
    lhras_enabled: bool = False
    lhras_config: str | None = None

    @classmethod
    def from_env(cls, *, service: str) -> "ALHarasSettings":
        raw_keys = os.getenv("AL_HARAS_SUBSCRIPTION_KEYS", "{}")
        try:
            parsed = json.loads(raw_keys)
        except json.JSONDecodeError as exc:
            raise RuntimeError("AL_HARAS_SUBSCRIPTION_KEYS must be JSON") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("AL_HARAS_SUBSCRIPTION_KEYS must map key ids to secrets")
        keys = {
            str(key_id): str(secret).encode("utf-8")
            for key_id, secret in parsed.items()
            if str(key_id) and str(secret)
        }
        root = Path(os.getenv("AL_HARAS_DATA_DIR", "data/al-haras"))
        return cls(
            issuer=os.getenv("AL_HARAS_ISSUER", "hyba-subscriptions"),
            keyring=keys,
            audit_path=root / f"{service}-guardian.jsonl",
            policy_version=os.getenv("AL_HARAS_POLICY_VERSION", "al-haras.policy.v1"),
            capability=os.getenv("AL_HARAS_CAPABILITY", "hyba.security"),
            max_payload_bytes=int(os.getenv("AL_HARAS_MAX_PAYLOAD_BYTES", "1048576")),
            require_intelligence_evidence=_truthy(
                os.getenv("AL_HARAS_REQUIRE_INTELLIGENCE_EVIDENCE"), default=False
            ),
            subscription_url=os.getenv(
                "AL_HARAS_SUBSCRIPTION_URL",
                "/contact?product=hyba-security",
            ),
            audit_quarantine=_truthy(os.getenv("AL_HARAS_AUDIT_QUARANTINE"), default=True),
            lhras_enabled=_truthy(os.getenv("AL_HARAS_ENABLE_LHRAS"), default=False),
            lhras_config=os.getenv("AL_HARAS_LHRAS_CONFIG") or None,
        )
