"""Qualification-result receipts, separate from PR75 invocation authorizations.

Keys and SQLite paths are explicitly supplied by the protected host. This provides
local transactional replay custody, not backup rollback or distributed consensus.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import time
from types import MappingProxyType

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from ..substrate.engine import canonical, digest


@dataclass(frozen=True)
class QualificationReceipt:
    issuer: str
    audience: str
    candidate_id: str
    candidate_fingerprint: str
    gates_digest: str
    nonce: str
    issued_at: int
    expires_at: int
    signature: str = ''
    operation: str = 'admit_qualified'
    schema: str = 'euclid.philos.qualification-receipt/1'

    def body(self):
        body = asdict(self)
        body.pop('signature')
        return canonical(body)

    def encode(self):
        return canonical(asdict(self)).decode()

    def valid(self, *, audience, candidate, now):
        fields = (self.issuer, self.audience, self.candidate_id)
        hashes = (self.candidate_fingerprint, self.gates_digest, self.nonce)
        return (all(type(v) is str and 0 < len(v) <= 256 for v in fields)
            and all(type(v) is str and len(v) == 64 and all(c in '0123456789abcdef' for c in v) for v in hashes)
            and self.schema == 'euclid.philos.qualification-receipt/1' and self.operation == 'admit_qualified'
            and self.audience == audience and self.candidate_id == candidate.candidate_id
            and self.candidate_fingerprint == candidate.compute_fingerprint()
            and type(self.issued_at) is int and type(self.expires_at) is int
            and 0 <= self.issued_at <= now < self.expires_at
            and 1 <= self.expires_at - self.issued_at <= 300)


class QualificationReceiptIssuer:
    def __init__(self, *, signing_key, issuer, audience, clock=time.time, ttl_seconds=60):
        if (not isinstance(signing_key, Ed25519PrivateKey)
                or not all(type(v) is str and 0 < len(v) <= 256 for v in (issuer, audience))
                or type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 300):
            raise ValueError('explicit host receipt authority and bounded TTL required')
        self.key, self.issuer, self.audience = signing_key, issuer, audience
        self.clock, self.ttl = clock, ttl_seconds

    def issue(self, candidate, gates):
        now = checked_time(self.clock)
        receipt = QualificationReceipt(self.issuer, self.audience, candidate.candidate_id,
            candidate.compute_fingerprint(), digest(gates), secrets.token_hex(32), now, now + self.ttl)
        return replace(receipt, signature=self.key.sign(receipt.body()).hex())


def checked_time(clock):
    now = clock()
    if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
        raise ValueError('finite nonnegative host time required')
    return int(now)


class QualificationReceiptAdmission:
    """Public keys only; consume before an admission side effect. Failed effects do not refund."""
    def __init__(self, *, trusted_issuers, audience, replay_path: Path, is_active, clock=time.time):
        if (not trusted_issuers or not all(type(k) is str and isinstance(v, Ed25519PublicKey)
                for k, v in trusted_issuers.items()) or type(audience) is not str or not audience
                or not isinstance(replay_path, Path) or replay_path.is_symlink() or not callable(is_active)):
            raise ValueError('explicit public receipt trust, audience and protected replay Path required')
        self.keys, self.audience = MappingProxyType(dict(trusted_issuers)), audience
        self.path, self.clock, self.is_active = replay_path.absolute(), clock, is_active
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path)
        try:
            with db:
                db.execute('CREATE TABLE IF NOT EXISTS context (id INTEGER PRIMARY KEY CHECK(id=1), audience TEXT NOT NULL, last_seen INTEGER NOT NULL)')
                db.execute('INSERT OR IGNORE INTO context VALUES (1, ?, 0)', (audience,))
                if db.execute('SELECT audience FROM context WHERE id=1').fetchone()[0] != audience:
                    raise ValueError('receipt audience binding mismatch')
                db.execute('CREATE TABLE IF NOT EXISTS receipts (issuer TEXT NOT NULL, nonce TEXT NOT NULL, expires_at INTEGER NOT NULL, PRIMARY KEY(issuer, nonce))')
        finally:
            db.close()
        os.chmod(self.path, 0o600)

    def consume(self, encoded, *, candidate, gates_digest):
        db = None
        try:
            receipt = QualificationReceipt(**json.loads(encoded))
            now = checked_time(self.clock)
            if (not receipt.valid(audience=self.audience, candidate=candidate, now=now)
                    or receipt.gates_digest != gates_digest or receipt.issuer not in self.keys
                    or self.is_active(receipt) is not True):
                raise ValueError('receipt scope/time/trust mismatch')
            self.keys[receipt.issuer].verify(bytes.fromhex(receipt.signature), receipt.body())
            db = sqlite3.connect(self.path, timeout=2)
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT audience, last_seen FROM context WHERE id=1').fetchone()
            if row is None or row[0] != self.audience or now < row[1]:
                raise ValueError('receipt context/clock rollback')
            db.execute('DELETE FROM receipts WHERE expires_at <= ?', (now,))
            if db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0] >= 10000:
                raise ValueError('receipt replay capacity exhausted')
            db.execute('INSERT INTO receipts VALUES (?, ?, ?)', (receipt.issuer, receipt.nonce, receipt.expires_at))
            db.execute('UPDATE context SET last_seen=? WHERE id=1', (now,))
            db.commit()
            return receipt
        except (InvalidSignature, TypeError, ValueError, KeyError, sqlite3.Error) as exc:
            raise PermissionError('qualification receipt admission refused') from exc
        finally:
            if db is not None:
                db.close()
