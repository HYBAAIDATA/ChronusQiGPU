"""Signed, tenant-bound subscription entitlements."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
import time
from typing import Any, Iterable, Mapping


class SubscriptionError(ValueError):
    """The subscription token is absent, malformed, expired, or out of scope."""


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise SubscriptionError("invalid base64 token") from exc


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class SubscriptionClaims:
    subscription_id: str
    tenant_id: str
    issuer: str
    key_id: str
    capabilities: tuple[str, ...]
    actors: tuple[str, ...]
    not_before: int
    expires_at: int
    max_payload_bytes: int = 1_048_576
    version: str = "al-haras.subscription.v2"
    jti: str | None = None

    def __post_init__(self) -> None:
        required = (
            self.subscription_id,
            self.tenant_id,
            self.issuer,
            self.key_id,
            self.version,
        )
        if any(not isinstance(value, str) or not value for value in required):
            raise SubscriptionError("subscription identity fields are required")
        if not self.capabilities or any(not item for item in self.capabilities):
            raise SubscriptionError("at least one capability is required")
        if not self.actors or any(not item for item in self.actors):
            raise SubscriptionError("at least one actor identity is required")
        if self.not_before < 0 or self.expires_at <= self.not_before:
            raise SubscriptionError("invalid subscription validity window")
        if self.max_payload_bytes <= 0:
            raise SubscriptionError("max_payload_bytes must be positive")
        if self.jti is not None and not self.jti:
            raise SubscriptionError("jti must be non-empty when present")

    def payload(self) -> dict[str, Any]:
        value = asdict(self)
        value["capabilities"] = list(self.capabilities)
        value["actors"] = list(self.actors)
        return value

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SubscriptionClaims":
        try:
            return cls(
                subscription_id=str(payload["subscription_id"]),
                tenant_id=str(payload["tenant_id"]),
                issuer=str(payload["issuer"]),
                key_id=str(payload["key_id"]),
                capabilities=tuple(str(item) for item in payload["capabilities"]),
                actors=tuple(str(item) for item in payload["actors"]),
                not_before=int(payload["not_before"]),
                expires_at=int(payload["expires_at"]),
                max_payload_bytes=int(payload.get("max_payload_bytes", 1_048_576)),
                version=str(payload.get("version", "")),
                jti=(None if payload.get("jti") is None else str(payload["jti"])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SubscriptionError("invalid subscription claims") from exc


class SubscriptionReplayError(SubscriptionError):
    """A token whose ``jti`` was already consumed within its validity window."""


class SubscriptionAuthority:
    """Issue and validate HMAC-SHA256 entitlements.

    Issuance belongs in the subscription control plane. It remains available as
    an explicit method for that control plane and deterministic tests; data-plane
    request handling calls only ``verify``.

    Verification is signature-first: an attacker-controlled token cannot probe
    which claim was wrong, because every unauthenticated mutation collapses to
    the same ``invalid subscription signature`` error.

    ``jti`` replay registry: when a token carries a ``jti`` claim, the admission
    path calls :meth:`consume`, which rejects a jti already consumed within its
    validity window. The registry is in-memory and per-process; issuers that
    need cross-instance replay protection must allocate unique ``jti`` values
    per request and accept restart-window replay, or front the authority with
    a shared nonce store.
    """

    def __init__(self, keys: Mapping[str, bytes], issuer: str) -> None:
        self._keys = dict(keys)
        self.issuer = issuer
        self._consumed_jti: dict[str, int] = {}
        for key_id, secret in self._keys.items():
            if not key_id or not isinstance(secret, bytes) or len(secret) < 32:
                raise ValueError("subscription keys must be named and at least 32 bytes")

    def issue(self, claims: SubscriptionClaims) -> str:
        if claims.issuer != self.issuer:
            raise SubscriptionError("issuer mismatch")
        secret = self._keys.get(claims.key_id)
        if secret is None:
            raise SubscriptionError("unknown subscription key")
        body = _b64encode(_canonical(claims.payload()))
        signature = _b64encode(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
        return f"{body}.{signature}"

    def verify(
        self,
        token: str,
        *,
        tenant_id: str,
        actor: str,
        capability: str,
        now: int | None = None,
    ) -> SubscriptionClaims:
        if not token or token.count(".") != 1:
            raise SubscriptionError("missing or malformed subscription token")
        body, signature = token.split(".", 1)
        try:
            payload = json.loads(_b64decode(body))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SubscriptionError("invalid subscription payload") from exc
        if not isinstance(payload, dict):
            raise SubscriptionError("subscription payload must be an object")
        claims = SubscriptionClaims.from_payload(payload)
        secret = self._keys.get(claims.key_id)
        expected = (
            _b64encode(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
            if secret is not None
            else ""
        )
        if not hmac.compare_digest(expected, signature):
            raise SubscriptionError("invalid subscription signature")
        if claims.version != "al-haras.subscription.v2":
            raise SubscriptionError("unsupported subscription version")
        if claims.issuer != self.issuer:
            raise SubscriptionError("issuer mismatch")
        current = int(time.time() if now is None else now)
        if current < claims.not_before:
            raise SubscriptionError("subscription not active")
        if current >= claims.expires_at:
            raise SubscriptionError("subscription expired")
        if claims.tenant_id != tenant_id:
            raise SubscriptionError("tenant mismatch")
        if actor not in claims.actors:
            raise SubscriptionError("actor identity not entitled")
        if capability not in claims.capabilities:
            raise SubscriptionError("capability not subscribed")
        return claims

    def consume(self, claims: SubscriptionClaims, *, now: int | None = None) -> None:
        """Register a verified token's ``jti``; raise on replay.

        Called by the admission path after ``verify`` succeeds and all other
        gates pass, so a rejected request never burns the token's nonce.
        Tokens without ``jti`` are accepted without replay tracking.
        """
        if claims.jti is None:
            return
        current = int(time.time() if now is None else now)
        consumed = self._consumed_jti
        for nonce, expiry in list(consumed.items()):
            if expiry <= current:
                del consumed[nonce]
        if claims.jti in consumed:
            raise SubscriptionReplayError("subscription token replay detected")
        consumed[claims.jti] = claims.expires_at

    def active_key_ids(self) -> Iterable[str]:
        return tuple(sorted(self._keys))
