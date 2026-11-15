"""Durable Ed25519 signing for qualification audit transcripts.

API receipt signing remains process-local (``receipt_signer``). Qualification
transcripts are persisted across restarts and shared across replicas that share
the qualification database, so their signatures must verify with a durable key.

Key custody (not HSM-backed):

1. ``CHRONUS_QUALIFICATION_SIGNING_SEED_HEX`` — 32-byte seed as hex (preferred
   for multi-replica deployments).
2. Otherwise a seed file next to the qualification DB
   (``<db>.ed25519.seed``), created once and reused so restart and replicas
   sharing that path keep the same verification key.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from threading import Lock
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

SEED_ENV = "CHRONUS_QUALIFICATION_SIGNING_SEED_HEX"

_LOCK = Lock()
_cached: Optional["QualificationSigner"] = None
_cache_key: Optional[tuple[str | None, str]] = None


def _db_path() -> str:
    configured = os.getenv("CHRONUS_QUALIFICATION_DB_PATH")
    if configured:
        return configured
    workload = os.getenv("CHRONUS_WORKLOAD_DB_PATH", "data/chronus-workloads.sqlite3")
    parent = Path(workload).parent
    return str(parent / "chronus-qualification.sqlite3")


def _seed_file_path() -> Path:
    return Path(_db_path()).with_name(Path(_db_path()).name + ".ed25519.seed")


def _resolve_seed() -> tuple[bytes, str]:
    """Return (seed, custody_label)."""
    configured = os.getenv(SEED_ENV)
    if configured:
        raw = bytes.fromhex(configured.strip())
        if len(raw) != 32:
            raise ValueError(f"{SEED_ENV} must decode to exactly 32 bytes")
        return raw, "environment-supplied seed"

    path = _seed_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            seed = os.urandom(32)
            os.write(fd, seed.hex().encode("ascii"))
        finally:
            os.close(fd)
        return seed, f"seed-file:{path}"
    except FileExistsError:
        text = path.read_text(encoding="ascii").strip()
        raw = bytes.fromhex(text)
        if len(raw) != 32:
            raise ValueError(f"qualification seed file {path} must hold 32 bytes hex")
        return raw, f"seed-file:{path}"


class QualificationSigner:
    """Ed25519 signer bound to a durable qualification seed."""

    def __init__(self, seed: bytes, *, custody: str) -> None:
        if len(seed) != 32:
            raise ValueError("Ed25519 seed must be 32 bytes")
        self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
        self._public_key = self._private_key.public_key()
        self.public_key_hex = self._public_key.public_bytes(
            Encoding.Raw, PublicFormat.Raw
        ).hex()
        self.key_id = hashlib.sha256(bytes.fromhex(self.public_key_hex)).hexdigest()[:16]
        self.custody = f"{custody} (not HSM-backed)"

    def sign(self, message: bytes) -> str:
        return self._private_key.sign(message).hex()

    def verify(self, message: bytes, signature: str) -> bool:
        try:
            self._public_key.verify(bytes.fromhex(signature), message)
            return True
        except (InvalidSignature, ValueError):
            return False


def get_qualification_signer() -> QualificationSigner:
    """Process-wide durable signer; reloads when DB path or seed env changes."""
    global _cached, _cache_key
    key = (os.getenv(SEED_ENV), _db_path())
    with _LOCK:
        if _cached is not None and _cache_key == key:
            return _cached
        seed, custody = _resolve_seed()
        _cached = QualificationSigner(seed, custody=custody)
        _cache_key = key
        return _cached


def reset_qualification_signer() -> None:
    """Drop the cached signer (tests / after env path changes)."""
    global _cached, _cache_key
    with _LOCK:
        _cached = None
        _cache_key = None
