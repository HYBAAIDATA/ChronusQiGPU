"""Durable Ed25519 signing for qualification audit transcripts.

API receipt signing remains process-local (``receipt_signer``). Qualification
transcripts are persisted across restarts and shared across replicas that share
the qualification database, so their signatures must verify with a durable key.

Key custody (not HSM-backed):

1. ``CHRONUS_QUALIFICATION_SIGNING_SEED_HEX`` — 32-byte seed as hex (preferred
   for multi-replica deployments).
2. Otherwise a seed file next to the qualification DB
   (``<db>.ed25519.seed``), created once via write-temp + atomic link and
   reused so restart and replicas sharing that path keep the same key.

Seed-file hardening: reject symlinks, require a regular file whose ``st_uid``
matches ``os.geteuid()`` (when available) with group/other bits clear, and
never treat an incomplete (empty / wrong-length) file as a valid key.
"""

from __future__ import annotations

import hashlib
import os
import stat
import time
from pathlib import Path
from threading import Lock
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

SEED_ENV = "CHRONUS_QUALIFICATION_SIGNING_SEED_HEX"
_SEED_HEX_LEN = 64  # 32 bytes as lowercase hex
_READ_ATTEMPTS = 8
_READ_RETRY_SLEEP_S = 0.01

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


def _open_flags(base: int) -> int:
    flags = base
    # Refuse to follow symlinks when the platform supports it.
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    return flags | nofollow


def _validate_seed_stat(st: os.stat_result, *, path: Path) -> None:
    if not stat.S_ISREG(st.st_mode):
        raise ValueError(f"qualification seed {path} must be a regular file")
    # Ownership is the primary trust gate (mode alone passes in a root container).
    if hasattr(os, "geteuid") and st.st_uid != os.geteuid():
        raise ValueError(
            f"qualification seed {path} must be owned by the service user "
            f"(uid={st.st_uid})"
        )
    if st.st_mode & 0o077:
        raise ValueError(
            f"qualification seed {path} must not be group/world accessible "
            f"(mode={stat.filemode(st.st_mode)})"
        )


def _decode_seed_hex(text: str, *, path: Path) -> bytes:
    cleaned = text.strip()
    if len(cleaned) != _SEED_HEX_LEN:
        raise ValueError(
            f"qualification seed file {path} is incomplete or corrupt "
            f"(expected {_SEED_HEX_LEN} hex chars, got {len(cleaned)})"
        )
    raw = bytes.fromhex(cleaned)
    if len(raw) != 32:
        raise ValueError(f"qualification seed file {path} must hold 32 bytes")
    return raw


def read_trusted(path: Path) -> bytes:
    """Open an existing seed without following symlinks; reject incomplete files."""
    last_error: Exception | None = None
    for attempt in range(_READ_ATTEMPTS):
        try:
            fd = os.open(str(path), _open_flags(os.O_RDONLY))
        except FileNotFoundError:
            raise
        except OSError as exc:
            # ELOOP when O_NOFOLLOW hits a symlink
            raise ValueError(
                f"qualification seed {path} is not a trusted regular file"
            ) from exc
        try:
            st = os.fstat(fd)
            _validate_seed_stat(st, path=path)
            data = os.read(fd, _SEED_HEX_LEN + 16)
        finally:
            os.close(fd)
        try:
            return _decode_seed_hex(data.decode("ascii"), path=path)
        except (ValueError, UnicodeDecodeError) as exc:
            last_error = exc
            # Another replica may still be publishing; brief retry then fail closed.
            if attempt + 1 < _READ_ATTEMPTS:
                time.sleep(_READ_RETRY_SLEEP_S)
                continue
            raise ValueError(
                f"qualification seed file {path} is incomplete or corrupt; "
                "delete it only after operator review, or set "
                f"{SEED_ENV}"
            ) from last_error
    assert last_error is not None
    raise last_error


# Back-compat alias for callers/tests that imported the private name.
_read_seed_file = read_trusted


def _write_all(fd: int, payload: bytes) -> None:
    """Write every byte; treat a zero-length write as failure."""
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise OSError("short write while publishing qualification seed")
        offset += written


def _fsync_dir(directory: Path) -> None:
    """Durably record directory entries (required after link/create).

    On Windows, ``os.open`` on a directory raises ``PermissionError``; the
    seed file itself was already ``fsync``'d before ``link``, so skip the
    parent fsync there.
    """
    if os.name == "nt":
        return
    flags = os.O_RDONLY
    # O_DIRECTORY is POSIX-only; Windows open() rejects unknown flags.
    directory_flag = getattr(os, "O_DIRECTORY", 0)
    if directory_flag:
        flags |= directory_flag
    try:
        dir_fd = os.open(str(directory), flags)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _publish_seed_file(path: Path) -> bytes:
    """Write seed to a private temp file, then atomically link into place.

    Durability order: open(0600) → write_all → fsync(fd) → close → link →
    fsync(parent). ``FileExistsError`` on link is the loser path: unlink the
    temp and return the winner's bytes via ``read_trusted``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    seed = os.urandom(32)
    payload = seed.hex().encode("ascii")
    tmp = path.parent / f".{path.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp"
    published: bytes | None = None
    try:
        fd = os.open(str(tmp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            _write_all(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            # File must be durable before the link makes it visible.
            os.link(str(tmp), str(path))
        except FileExistsError:
            # Loser path — winner's final file is authoritative.
            try:
                os.unlink(str(tmp))
            except FileNotFoundError:
                pass
            return read_trusted(path)
        _fsync_dir(path.parent)
        published = seed
    except Exception:
        try:
            os.unlink(str(tmp))
        except FileNotFoundError:
            pass
        raise
    finally:
        try:
            os.unlink(str(tmp))
        except FileNotFoundError:
            pass
    if published is not None:
        return published
    return read_trusted(path)


def _resolve_seed() -> tuple[bytes, str]:
    """Return (seed, custody_label)."""
    configured = os.getenv(SEED_ENV)
    if configured:
        raw = bytes.fromhex(configured.strip())
        if len(raw) != 32:
            raise ValueError(f"{SEED_ENV} must decode to exactly 32 bytes")
        return raw, "environment-supplied seed"

    path = _seed_file_path()
    if path.exists():
        # exists() may follow a symlink for the existence check; open uses O_NOFOLLOW.
        return read_trusted(path), f"seed-file:{path}"
    seed = _publish_seed_file(path)
    return seed, f"seed-file:{path}"


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
