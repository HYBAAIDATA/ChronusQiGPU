"""
Quantum-safe gateway security — production implementation of the
pre-consolidation ``hyba_backend.services.gateway.quantum_security`` surface.

The earlier monorepo declared ``APIKey``, ``security_manager`` and
``verify_api_key``. None was migrated. This is the real implementation.

Security contract (fail-closed, per README 4.5 item 4)
-----------------------------------------------------
* If ``QUANTUM_SECURITY_API_KEYS`` is unset or empty, **every** verification
  fails. The gateway does not fall back to "no auth required".
* Keys are compared with :func:`hmac.compare_digest` in constant time.
* Only SHA-256 digests of keys are stored, never the key material.
* :class:`APIKey` records the role and scopes, so authorisation can be checked
  separately from authentication.

Quantum-safety note
-------------------
The stored digest is a plain SHA-256, which is *not* post-quantum resistant.
That is stated here rather than implied away: this module provides
authentication and constant-time comparison; a post-quantum signature scheme
would be required to make the digest itself quantum-resistant, and that is a
separate migration.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

__all__ = [
    "APIKey",
    "SecurityManager",
    "security_manager",
    "verify_api_key",
    "ENV_API_KEYS",
    "POST_QUANTUM_NOTE",
]

#: Comma-separated ``key_id:digest[:role]`` entries.
ENV_API_KEYS = "QUANTUM_SECURITY_API_KEYS"

#: Digest algorithm used for stored key material.
DIGEST_ALGORITHM = "sha256"

POST_QUANTUM_NOTE = (
    "Keys are stored as SHA-256 digests. SHA-256 is not post-quantum "
    "resistant; this module provides authentication and constant-time "
    "comparison only."
)


def digest_key(raw_key: str) -> str:
    """Return the hex SHA-256 digest of ``raw_key``."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class APIKey:
    """A registered API key: its id, stored digest, role and scopes."""

    key_id: str
    digest: str
    role: str = "client"
    scopes: Tuple[str, ...] = ()

    def has_scope(self, scope: str) -> bool:
        """True when this key carries ``scope`` (``"*"`` grants all scopes)."""
        return "*" in self.scopes or scope in self.scopes

    def to_dict(self) -> Dict[str, object]:
        """Redacted view: the digest is included, the raw key never is."""
        return {
            "key_id": self.key_id,
            "role": self.role,
            "scopes": list(self.scopes),
            "digest": self.digest,
        }


class SecurityManager:
    """Registry of API keys with constant-time verification.

    Keys are loaded from the ``QUANTUM_SECURITY_API_KEYS`` environment variable
    as comma-separated ``key_id:digest[:role[:scope1|scope2]]`` entries.
    ``digest`` is the hex SHA-256 of the raw key.
    """

    def __init__(self, keys: Optional[List[APIKey]] = None) -> None:
        self._keys: Dict[str, APIKey] = {}
        self._fail_closed = True
        for key in keys or []:
            self.register(key)
        if not self._keys:
            self.load_from_environment()

    # -- registration -------------------------------------------------------

    def register(self, key: APIKey) -> None:
        """Add a key to the registry."""
        self._keys[key.key_id] = key
        self._fail_closed = False

    def load_from_environment(self, env: Optional[Dict[str, str]] = None) -> int:
        """Load keys from the environment; returns the number registered."""
        source = env if env is not None else os.environ
        raw = (source.get(ENV_API_KEYS) or "").strip()
        if not raw:
            # No configured keys: stay fail-closed.
            self._keys = {}
            self._fail_closed = True
            return 0
        count = 0
        for entry in raw.split(","):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split(":")
            if len(parts) < 2:
                continue
            key_id = parts[0].strip()
            digest = parts[1].strip().lower()
            role = parts[2].strip() if len(parts) > 2 and parts[2].strip() else "client"
            scopes: Tuple[str, ...] = ()
            if len(parts) > 3 and parts[3].strip():
                scopes = tuple(s.strip() for s in parts[3].split("|") if s.strip())
            self.register(APIKey(key_id=key_id, digest=digest, role=role, scopes=scopes))
            count += 1
        self._fail_closed = not self._keys
        return count

    # -- verification -------------------------------------------------------

    @property
    def fail_closed(self) -> bool:
        """True when no keys are registered, so verification must fail."""
        return self._fail_closed or not self._keys

    @property
    def key_count(self) -> int:
        """Number of registered keys."""
        return len(self._keys)

    def verify(self, raw_key: Optional[str]) -> Tuple[bool, Optional[APIKey], str]:
        """Verify ``raw_key`` against every registered digest.

        Returns ``(ok, key, reason)``. Comparison is constant time per key.
        When no keys are registered this returns ``(False, None, "fail_closed")``
        rather than allowing the request through.
        """
        if self.fail_closed:
            return False, None, "fail_closed"
        if not raw_key:
            return False, None, "missing_key"
        presented = digest_key(raw_key)
        matched: Optional[APIKey] = None
        for key in self._keys.values():
            # Compare every key so timing does not reveal which one matched.
            if hmac.compare_digest(presented, key.digest):
                matched = key
        if matched is None:
            return False, None, "invalid_key"
        return True, matched, "ok"

    def has_scope(self, key: Optional[APIKey], scope: str) -> bool:
        """Authorisation check, separate from authentication."""
        return bool(key is not None and key.has_scope(scope))

    def stats(self) -> Dict[str, object]:
        """Registry statistics; never exposes key material."""
        return {
            "key_count": self.key_count,
            "fail_closed": self.fail_closed,
            "digest_algorithm": DIGEST_ALGORITHM,
            "post_quantum_note": POST_QUANTUM_NOTE,
            "key_ids": sorted(self._keys),
        }


#: Process-wide manager, built from the environment at import time.
security_manager = SecurityManager()


def verify_api_key(raw_key: Optional[str]) -> bool:
    """Verify ``raw_key`` against the process-wide :data:`security_manager`.

    Returns ``False`` whenever verification cannot succeed, including the
    fail-closed case where no keys are configured.
    """
    ok, _key, _reason = security_manager.verify(raw_key)
    return ok
