"""Trusted host SHA256d verifier at the CHRONUS -> PYTHIA boundary.

An adapter's claim is never evidence. Every candidate is rebuilt from the
authorised header prefix and recomputed with ``hashlib`` before it may cross
back to the caller.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping


class CandidateVerificationError(RuntimeError):
    """An adapter-reported candidate failed independent host verification."""


def sha256d(header80: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(header80).digest()).digest()


def verify_candidate(
    header_prefix76: bytes,
    nonce: int,
    claimed_hash_hex: str,
    target_int: int,
    *,
    allowed_nonces: Iterable[int] | None = None,
    nonce_range: tuple[int, int] | None = None,
) -> bytes:
    """Return the host-computed digest or raise ``CandidateVerificationError``."""
    if isinstance(nonce, bool) or not isinstance(nonce, int) or not 0 <= nonce <= 0xFFFFFFFF:
        raise CandidateVerificationError("candidate nonce is not a uint32")
    if nonce_range is not None:
        start, count = nonce_range
        if not start <= nonce < start + count:
            raise CandidateVerificationError("candidate nonce outside the admitted range")
    if allowed_nonces is not None and nonce not in allowed_nonces:
        raise CandidateVerificationError("candidate nonce outside the admitted batch")
    digest = sha256d(bytes(header_prefix76) + nonce.to_bytes(4, "little"))
    if digest.hex() != str(claimed_hash_hex).lower():
        raise CandidateVerificationError("candidate digest mismatch")
    if int.from_bytes(digest, "little") > target_int:
        raise CandidateVerificationError("candidate digest above target")
    return digest


def verify_hits(
    header_prefix76: bytes,
    hits: Iterable[Mapping[str, Any]],
    target_int: int,
    **bounds: Any,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for hit in hits:
        verify_candidate(
            header_prefix76,
            hit.get("nonce"),  # type: ignore[arg-type]
            str(hit.get("hash_hex", "")),
            target_int,
            **bounds,
        )
        out.append({**dict(hit), "host_verified": True})
    return out


__all__ = ["CandidateVerificationError", "sha256d", "verify_candidate", "verify_hits"]
