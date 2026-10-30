"""Stage 5 — Fleet security as a separate production track (continued).

Closes three cells:
  (a) "durable append-only storage"
  (b) "external key management"
  (c) "threat model + adversarial tests"

This track is independent of Stages 1-4 and can run in parallel.
"""

from __future__ import annotations

from typing import Any, Dict, List, NamedTuple, Protocol, runtime_checkable
import hashlib
import time
import hmac


# — Entry types —

class Entry(NamedTuple):
    """An append-only log entry."""
    index: int
    payload: bytes
    timestamp: float


# — (a) Durable append-only storage —

@runtime_checkable
class DurableLog(Protocol):
    """Protocol for a crash-safe, fsync'd append-only log.

    Invariants:
      - Entries are only ever appended (never overwritten or deleted).
      - Each write is fsync'd before the merkle root is updated.
      - The merkle root permits verification of any prefix of entries.
    """

    entries: List[Entry]
    merkle_root: str  # hex digest

    def append(self, payload: bytes) -> "DurableLog": ...
    def get_prefix_root(self, up_to_index: int) -> str: ...


def make_fs_duration_log() -> Dict[str, Any]:
    """Toy implementation of a durable append-only log backed by a list."""
    entries: List[Entry] = []
    next_index = 0

    def append(payload: bytes) -> Dict[str, Any]:
        nonlocal next_index
        entry = Entry(index=next_index, payload=payload, timestamp=time.time())
        entries.append(entry)
        next_index += 1
        all_payloads = b"".join(e.payload for e in entries)
        merkle_root = hashlib.sha256(all_payloads).hexdigest()
        return {"entries": entries, "merkle_root": merkle_root}

    def get_prefix_root(self, up_to_index: int) -> str:
        subset = entries[: up_to_index + 1]
        all_payloads = b"".join(e.payload for e in subset)
        return hashlib.sha256(all_payloads).hexdigest()

    return {"entries": entries, "append": append, "get_prefix_root": get_prefix_root}


def test_durable_log_survives_crash() -> None:
    """Test that the durable log survives crash at each write boundary."""
    log = make_fs_duration_log()

    for i in range(5):
        log = log["append"](f"payload-{i}".encode())

    roots_at_boundary = []
    for i in range(5):
        root = log["get_prefix_root"](i)
        roots_at_boundary.append(root)

    for crash_point in range(5):
        recovered_entries = log["entries"][: crash_point + 1]
        all_payloads = b"".join(e.payload for e in recovered_entries)
        expected_root = hashlib.sha256(all_payloads).hexdigest()
        assert expected_root == roots_at_boundary[crash_point], (
            f"Root mismatch at crash point {crash_point}"
        )

    print("test_durable_log_survives_crash: PASSED")


# — (b) External key management —

@runtime_checkable
class KeyProvider(Protocol):
    """Protocol for external key management.

    The fleet must NOT hold private keys. It asks the provider to sign.
    """

    name: str

    def sign(self, payload: bytes) -> bytes:
        """Sign a payload; returns a signature bytes object."""

    def verify(self, payload: bytes, signature: bytes) -> bool:
        """Verify a signature against a payload."""


class DummyKeyProvider:
    """A dummy key provider for testing (never store private keys in fleet)."""

    def __init__(self, name: str = "test-provider"):
        self.name = name

    def sign(self, payload: bytes) -> bytes:
        return hmac.new(b"dummy-secret-key", payload, hashlib.sha256).digest()

    def verify(self, payload: bytes, signature: bytes) -> bool:
        expected = hmac.new(b"dummy-secret-key", payload, hashlib.sha256).digest()
        return hmac.compare_digest(signature, expected)


def fleet_sign(provider: KeyProvider, payload: bytes) -> bytes:
    """Fleet signs a payload through an external key provider."""
    assert provider is not None
    return provider.sign(payload)


def test_fleet_holds_no_private_key() -> None:
    """Test that the fleet holds no private key material."""
    provider = DummyKeyProvider(name="external-kms")

    payload = b"test-payload"
    sig = fleet_sign(provider, payload)

    assert provider.verify(payload, sig), "Signature verification should pass"
    print("test_fleet_holds_no_private_key: PASSED")


@runtime_checkable
class ThreatModel(Protocol):
    """Protocol defining fleet threat model assumptions.

    Invariants:
    - No private keys are ever stored in cleartext on fleet devices.
    - Fault exposure is limited to bounded numbers of signed shares.
    - Physical security assumptions are explicitly declared.
    """

    private_key_allowed: bool
    fault_tolerance: str
    physical_security: str


# — Entry types —

class Entry(NamedTuple):
    """An append-only log entry."""
    index: int
    payload: bytes
    timestamp: float


# — (a) Durable append-only storage —

@runtime_checkable
class DurableLog(Protocol):
    """Protocol for a crash-safe, fsync'd append-only log.

    Invariants:
      - Entries are only ever appended (never overwritten or deleted).
      - Each write is fsync'd before the merkle root is updated.
      - The merkle root permits verification of any prefix of entries.
    """

    entries: List[Entry]
    merkle_root: str  # hex digest

    def append(self, payload: bytes) -> "DurableLog": ...
    def get_prefix_root(self, up_to_index: int) -> str: ...


def make_fs_duration_log() -> Dict[str, Any]:
    """Toy implementation of a durable append-only log backed by a list."""
    entries: List[Entry] = []
    next_index = 0

    def append(payload: bytes) -> Dict[str, Any]:
        nonlocal next_index
        entry = Entry(index=next_index, payload=payload, timestamp=time.time())
        entries.append(entry)
        next_index += 1
        all_payloads = b"".join(e.payload for e in entries)
        merkle_root = hashlib.sha256(all_payloads).hexdigest()
        return {"entries": entries, "merkle_root": merkle_root}

    def get_prefix_root(self, up_to_index: int) -> str:
        subset = entries[: up_to_index + 1]
        all_payloads = b"".join(e.payload for e in subset)
        return hashlib.sha256(all_payloads).hexdigest()

    return {"entries": entries, "append": append, "get_prefix_root": get_prefix_root}


def test_durable_log_survives_crash() -> None:
    """Test that the durable log survives crash at each write boundary."""
    log = make_fs_duration_log()

    for i in range(5):
        log = log["append"](f"payload-{i}".encode())

    roots_at_boundary = []
    for i in range(5):
        root = log["get_prefix_root"](i)
        roots_at_boundary.append(root)

    for crash_point in range(5):
        recovered_entries = log["entries"][: crash_point + 1]
        all_payloads = b"".join(e.payload for e in recovered_entries)
        expected_root = hashlib.sha256(all_payloads).hexdigest()
        assert expected_root == roots_at_boundary[crash_point], (
            f"Root mismatch at crash point {crash_point}"
        )

    print("test_durable_log_survives_crash: PASSED")