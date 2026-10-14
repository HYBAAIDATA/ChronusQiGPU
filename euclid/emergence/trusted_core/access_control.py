"""PHILOS authorization: external Ed25519 issuance, scoped verification and replay custody.

The verifier retains public keys only. Host key custody/process isolation and a
protected persistent ledger are deployment prerequisites, not Python guarantees.
"""
from __future__ import annotations

import inspect
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import Mapping, Set

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class UnauthorizedOperationalLoopCallError(PermissionError):
    """A diagnostic operational-loop frame reached the qualification service."""


class InvalidGovernanceTokenError(PermissionError):
    """Scoped authorization, trust configuration or replay custody is unavailable."""


MAX_TOKEN_LIFETIME = 300
TOKEN_SCHEMA = "euclid.philos.authorization/1"


def _identifier(value):
    return type(value) is str and bool(value.strip()) and len(value) <= 256


def _hex(value, length):
    return type(value) is str and len(value) == length and all(c in "0123456789abcdef" for c in value)


@dataclass(frozen=True)
class GovernanceToken:
    """Single-use, candidate/audience-bound invocation authorization, not qualification.

    token_digest retains its historical field name but now carries a complete
    Ed25519 signature in hex, not a hash or MAC. Legacy unscoped tokens invalidate.
    """
    issuer: str
    officer_id: str
    issued_at: int
    expires_at: int
    token_digest: str
    audience: str
    candidate_fingerprint: str
    nonce: str
    operation: str = "qualify"
    schema: str = TOKEN_SCHEMA

    def body(self) -> bytes:
        payload = asdict(self)
        del payload["token_digest"]
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

    def _valid_scope(self, *, audience, candidate_fingerprint, now):
        return (
            type(self.schema) is str and self.schema == TOKEN_SCHEMA
            and type(self.operation) is str and self.operation == "qualify"
            and all(_identifier(v) for v in (self.issuer, self.officer_id, self.audience))
            and self.audience == audience
            and _hex(self.candidate_fingerprint, 64)
            and self.candidate_fingerprint == candidate_fingerprint
            and _hex(self.nonce, 64)
            and type(now) is int and type(self.issued_at) is int and type(self.expires_at) is int
            and 0 <= self.issued_at <= now < self.expires_at
            and 1 <= self.expires_at - self.issued_at <= MAX_TOKEN_LIFETIME
        )

    @classmethod
    def issue(cls, officer_id: str, signing_key: Ed25519PrivateKey, *, issuer: str,
              audience: str, candidate_fingerprint: str, ttl_seconds: int = 60,
              now: int | None = None) -> GovernanceToken:
        """Issuer-side helper. Never supply this private key to EQS or the agent."""
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise TypeError("issuer-owned Ed25519 private key required; public keys cannot issue")
        now = int(time.time()) if now is None else now
        if type(now) is not int or type(ttl_seconds) is not int or not 1 <= ttl_seconds <= MAX_TOKEN_LIFETIME:
            raise ValueError("bounded integer issue time and lifetime required")
        token = cls(issuer, officer_id, now, now + ttl_seconds, "", audience,
                    candidate_fingerprint, secrets.token_hex(32))
        if not token._valid_scope(audience=audience, candidate_fingerprint=candidate_fingerprint, now=now):
            raise ValueError("valid issuer, officer, audience and candidate digest required")
        from dataclasses import replace
        return replace(token, token_digest=signing_key.sign(token.body()).hex())

    def verify(self, public_key: Ed25519PublicKey, *, audience: str,
               candidate_fingerprint: str, now: int | None = None) -> bool:
        """Verify signature/scope only. Replay admission is a separate mandatory step."""
        now = int(time.time()) if now is None else now
        try:
            if (not isinstance(public_key, Ed25519PublicKey)
                    or not self._valid_scope(audience=audience,
                                             candidate_fingerprint=candidate_fingerprint, now=now)
                    or not _hex(self.token_digest, 128)):
                return False
            public_key.verify(bytes.fromhex(self.token_digest), self.body())
            return True
        except (InvalidSignature, TypeError, ValueError):
            return False


class QualificationAuthorization:
    """Host-configured public-key verifier and transactional single-use ledger.

    Trust is an explicit (issuer, officer) -> public key allowlist. Rotation or
    revocation requires replacing this host configuration, retaining the ledger.
    SQLite provides local transaction/restart continuity, not independent custody,
    network-wide replay consensus, OS isolation or backup-rollback resistance.
    """
    def __init__(self, *, trusted_signers: Mapping, audience: str, replay_path: Path,
                 clock=time.time, max_outstanding: int = 10000):
        if not _identifier(audience) or not isinstance(replay_path, Path) or not callable(clock):
            raise ValueError("explicit audience, host-owned replay Path and clock required")
        if type(max_outstanding) is not int or not 1 <= max_outstanding <= 100000:
            raise ValueError("bounded positive replay capacity required")
        if not isinstance(trusted_signers, Mapping) or not trusted_signers:
            raise ValueError("explicit trusted issuer/officer public keys required")
        keys = {}
        for principal, key in trusted_signers.items():
            if (type(principal) is not tuple or len(principal) != 2
                    or not all(_identifier(v) for v in principal)
                    or not isinstance(key, Ed25519PublicKey)):
                raise TypeError("trusted (issuer, officer) public-key bindings required")
            keys[principal] = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self._keys = MappingProxyType(keys)
        self.audience, self.replay_path = audience, replay_path.absolute()
        self.clock, self.max_outstanding = clock, max_outstanding
        self._lock = RLock()
        self.replay_path.parent.mkdir(parents=True, exist_ok=True)
        if self.replay_path.is_symlink():
            raise ValueError("host replay path must not be a symlink")
        with self._connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS context (id INTEGER PRIMARY KEY CHECK(id=1), audience TEXT NOT NULL, last_seen INTEGER NOT NULL)")
            row = db.execute("SELECT audience FROM context WHERE id=1").fetchone()
            if row is None:
                db.execute("INSERT INTO context VALUES (1, ?, 0)", (audience,))
            elif row[0] != audience:
                raise ValueError("replay ledger belongs to a different audience")
            db.execute("CREATE TABLE IF NOT EXISTS used_tokens (issuer TEXT NOT NULL, nonce TEXT NOT NULL, expires_at INTEGER NOT NULL, candidate_fingerprint TEXT NOT NULL, PRIMARY KEY (issuer, nonce))")
        os.chmod(self.replay_path, 0o600)

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.replay_path, timeout=2)
        try:
            with db:
                yield db
        finally:
            db.close()

    def authorize(self, token: GovernanceToken, *, candidate_fingerprint: str):
        """Verify and durably consume before any executor invocation; no refunds."""
        with self._lock:
            now = self.clock()
            if type(now) is float and now.is_integer():
                now = int(now)
            elif type(now) is float:
                # Wall-clock subsecond precision is not token authority.
                import math
                if math.isfinite(now):
                    now = int(now)
            if type(token) is not GovernanceToken or type(now) is not int:
                raise InvalidGovernanceTokenError("typed token and finite integer clock required")
            if not token._valid_scope(audience=self.audience,
                    candidate_fingerprint=candidate_fingerprint, now=now):
                raise InvalidGovernanceTokenError("invalid governance authorization scope")
            raw = self._keys.get((token.issuer, token.officer_id))
            if raw is None or not token.verify(Ed25519PublicKey.from_public_bytes(raw),
                    audience=self.audience, candidate_fingerprint=candidate_fingerprint, now=now):
                raise InvalidGovernanceTokenError("untrusted, invalid, expired or mismatched governance authorization")
            try:
                with self._connection() as db:
                    db.execute("BEGIN IMMEDIATE")
                    context = db.execute("SELECT audience, last_seen FROM context WHERE id=1").fetchone()
                    if context is None or context[0] != self.audience or now < context[1]:
                        raise InvalidGovernanceTokenError("authorization context missing or clock rollback detected")
                    db.execute("DELETE FROM used_tokens WHERE expires_at <= ?", (now,))
                    if db.execute("SELECT COUNT(*) FROM used_tokens").fetchone()[0] >= self.max_outstanding:
                        raise InvalidGovernanceTokenError("authorization replay capacity exhausted")
                    try:
                        db.execute("INSERT INTO used_tokens VALUES (?, ?, ?, ?)",
                            (token.issuer, token.nonce, token.expires_at, candidate_fingerprint))
                    except sqlite3.IntegrityError as exc:
                        raise InvalidGovernanceTokenError("governance authorization replay refused") from exc
                    db.execute("UPDATE context SET last_seen=? WHERE id=1", (now,))
            except sqlite3.Error as exc:
                raise InvalidGovernanceTokenError("authorization replay ledger unavailable") from exc


class CallerBoundaryGuard:
    """Diagnostic defense in depth; not a process or authorization boundary."""

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
