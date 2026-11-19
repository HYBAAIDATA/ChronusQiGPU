"""Bounded self-healing for THESEUS durable content (Reed-Solomon parity).

What this is
------------
Every object written to :class:`chronus.storage.durable.DurableTheseusService`
gets a Reed-Solomon parity sidecar (systematic RS(48, 32) over GF(257), the
same code as ``chronus.security.al_haras.reed_solomon``). When a stored payload
later fails its SHA-256 content address, either at open time
(``verify_store``) or on read (``reconstruct``), the store tries to correct the
damaged bytes from that parity. The repair is accepted only if the corrected
bytes hash to the object's content address; then they are written back and a
row goes into the ``self_heal_events`` table. Anything else fails closed with
the original ``StorageIntegrityError``.

Bounds (what it cannot do)
--------------------------
* At most ``t = (n - k) // 2 = 8`` corrupted bytes per 32-byte block. Heavier
  damage, a changed length, or a missing row is not repairable.
* Parity lives in the same SQLite file. It does not protect against a lost or
  page-corrupted database (``PRAGMA integrity_check`` still fails closed) or a
  lost disk; that needs replication, which is a deployment concern.
* Objects larger than ``CHRONUS_SELF_HEALING_MAX_BYTES`` (default 256 KiB,
  capped at the encoder's 1 MiB limit) get no parity. They keep fail-closed
  behaviour. Encoding and decoding use the batched numpy decoder in
  ``reed_solomon`` (measured numbers: ``benchmarks/acceleration/self_healing_raw.json``).
* Metadata rows (records, journal) are verified but not repaired.

THESEUS owns this storage integrity function. Remediation authority can be
handed to Salamander (``CHRONUS_SELF_HEALING_REPAIR=salamander``; see
``chronus.integration.salamander_theseus``), which uses the canonical
Salamander package when it is installed.

Configuration
-------------
``CHRONUS_SELF_HEALING``: ``1`` (default) enables parity and repair; ``0``
restores the previous strict fail-closed behaviour.
``CHRONUS_SELF_HEALING_MAX_BYTES``: largest payload that gets parity.
``CHRONUS_SELF_HEALING_REPAIR``: ``theseus`` (default) repairs in place on
open/read; ``salamander`` makes THESEUS detect and diagnose only, and the
repair is executed through Salamander's AL HARAS-authorised control plane
(``chronus.integration.salamander_theseus``).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np

SCHEME = "reed-solomon-gf257-systematic/1"
RS_N = 48
RS_K = 32
DEFAULT_MAX_BYTES = 256 * 1024

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def self_healing_enabled() -> bool:
    raw = os.getenv("CHRONUS_SELF_HEALING")
    if raw is None:
        return True
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError("CHRONUS_SELF_HEALING must be 1/0, true/false, yes/no or on/off")


REPAIR_AUTHORITIES = frozenset({"theseus", "salamander"})


def repair_authority() -> str:
    raw = os.getenv("CHRONUS_SELF_HEALING_REPAIR", "theseus").strip().lower()
    if raw not in REPAIR_AUTHORITIES:
        raise ValueError("CHRONUS_SELF_HEALING_REPAIR must be 'theseus' or 'salamander'")
    return raw


def encoder_max_bytes() -> int:
    """Largest payload the Reed-Solomon encoder accepts (1 MiB)."""
    return int(_rs().MAX_TRACE_BYTES)


def self_healing_max_bytes() -> int:
    """Effective protection limit: the configured value, capped at the encoder limit."""
    raw = os.getenv("CHRONUS_SELF_HEALING_MAX_BYTES")
    if raw is None:
        return min(DEFAULT_MAX_BYTES, encoder_max_bytes())
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("CHRONUS_SELF_HEALING_MAX_BYTES must be an integer") from exc
    if value < 1:
        raise ValueError("CHRONUS_SELF_HEALING_MAX_BYTES must be positive")
    return min(value, encoder_max_bytes())


def sidecar_metadata_valid(scheme: object, n: object, k: object) -> bool:
    """Only the fixed scheme and dimensions are trusted for repair."""
    return scheme == SCHEME and n == RS_N and k == RS_K


def _rs():
    # Local import keeps storage import-light and free of package cycles.
    from chronus.security.al_haras import reed_solomon

    return reed_solomon


def encode_parity(payload: bytes, n: int = RS_N, k: int = RS_K) -> bytes:
    """Parity symbols (0..256) for ``payload``, packed as 2-byte big-endian."""
    return _rs().encode_blocks(payload, n=n, k=k).astype(">u2").tobytes()


def _decode_parity(blob: bytes, length: int, n: int, k: int) -> np.ndarray:
    per_block = n - k
    blocks = (length + k - 1) // k
    if len(blob) != blocks * per_block * 2:
        raise ValueError("parity sidecar has the wrong size")
    symbols = np.frombuffer(blob, dtype=">u2").astype(np.int64)
    if symbols.size and int(symbols.max()) > 256:
        raise ValueError("parity symbol outside GF(257)")
    return symbols.reshape(blocks, per_block)


@dataclass(frozen=True)
class HealOutcome:
    repaired: Optional[bytes]
    corrected_positions: tuple[int, ...]
    reason: str

    @property
    def ok(self) -> bool:
        return self.repaired is not None


def heal_payload(received: bytes, object_id: str, parity: bytes,
                 expected_length: int, n: int = RS_N, k: int = RS_K) -> HealOutcome:
    """Try to recover the bytes whose SHA-256 is ``object_id``.

    Returns ``HealOutcome(repaired=None, ...)`` when repair is out of bounds;
    never returns bytes that do not match the content address.
    """
    if len(received) != expected_length:
        return HealOutcome(None, (), "length differs from the recorded size")
    if not sidecar_metadata_valid(SCHEME, n, k):
        return HealOutcome(None, (), "unsupported parity dimensions")
    try:
        blocks = _decode_parity(parity, expected_length, n, k)
    except ValueError as exc:
        return HealOutcome(None, (), str(exc))
    try:
        result = _rs().heal_blocks(received, blocks, n, k, object_id)
    except (ValueError, ZeroDivisionError) as exc:  # ReedSolomonError is a ValueError
        return HealOutcome(None, (), f"decoder rejected the sidecar: {exc}")
    repaired = result["repaired"]
    if result["uncorrectable_blocks"]:
        return HealOutcome(None, (), f"{len(result['uncorrectable_blocks'])} block(s) beyond correction bound")
    if hashlib.sha256(repaired).hexdigest() != object_id:
        return HealOutcome(None, (), "corrected bytes do not match the content address")
    return HealOutcome(repaired, tuple(result["corrected_data_positions"]), "repaired")
