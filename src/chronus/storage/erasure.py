"""Bounded XOR single-erasure recovery over immutable byte shards.

Pure software fault model: a data shard is missing or fails its independent
SHA-256 digest, but parity and all other shards remain intact. This is NOT
physical storage, hardware ECC, or Cassini-based correction. THESEUS must
separately attest metadata custody; plain hashes do not authenticate an actor.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

_MAX_PAYLOAD = 1 << 20
_MAX_SHARDS = 32


@dataclass(frozen=True)
class ErasureStripe:
    original_size: int
    shard_count: int
    shard_bytes: int
    source_sha256: str
    shard_sha256: tuple[str, ...]
    parity: bytes
    parity_sha256: str
    schema: str = "chronus.storage.xor-single-erasure/1"


def encode_stripe(payload: bytes, shard_count: int = 4) -> tuple[ErasureStripe, tuple[bytes, ...]]:
    if not isinstance(payload, bytes) or not 1 <= len(payload) <= _MAX_PAYLOAD:
        raise ValueError("payload must be 1..1048576 bytes")
    if type(shard_count) is not int or not 2 <= shard_count <= _MAX_SHARDS:
        raise ValueError("shard_count must be 2..32")
    width = (len(payload) + shard_count - 1) // shard_count
    chunks = tuple(payload[i * width:(i + 1) * width].ljust(width, b"\0")
                   for i in range(shard_count))
    parity = bytearray(width)
    for part in chunks:
        for j, value in enumerate(part):
            parity[j] ^= value
    manifest = ErasureStripe(
        original_size=len(payload), shard_count=shard_count,
        shard_bytes=width, source_sha256=sha256(payload).hexdigest(),
        shard_sha256=tuple(sha256(part).hexdigest() for part in chunks),
        parity=bytes(parity), parity_sha256=sha256(parity).hexdigest(),
    )
    return manifest, chunks


def recover_stripe(stripe: ErasureStripe, received: tuple[bytes | None, ...]) -> bytes:
    """Recover at most one unavailable/bad shard, then verify original digest.

    A corrupt shard is treated as an erasure only because an independent
    trusted manifest identifies its expected digest. Multiple failures fail.
    """
    if not isinstance(stripe, ErasureStripe) or stripe.schema != "chronus.storage.xor-single-erasure/1":
        raise ValueError("unsupported stripe authority or schema")
    if (type(stripe.shard_count) is not int or not 2 <= stripe.shard_count <= _MAX_SHARDS
            or type(stripe.original_size) is not int or not 1 <= stripe.original_size <= _MAX_PAYLOAD
            or type(stripe.shard_bytes) is not int or stripe.shard_bytes < 1
            or stripe.shard_bytes != (stripe.original_size + stripe.shard_count - 1) // stripe.shard_count
            or len(stripe.shard_sha256) != stripe.shard_count
            or len(stripe.parity) != stripe.shard_bytes
            or sha256(stripe.parity).hexdigest() != stripe.parity_sha256):
        raise ValueError("corrupt stripe metadata or parity")
    if not isinstance(received, tuple) or len(received) != stripe.shard_count:
        raise ValueError("exactly shard_count parts required")
    parts = list(received)
    absent = []
    for i, part in enumerate(parts):
        if (not isinstance(part, bytes) or len(part) != stripe.shard_bytes
                or sha256(part).hexdigest() != stripe.shard_sha256[i]):
            absent.append(i)
    if len(absent) > 1:
        raise ValueError("single-erasure recovery cannot repair multiple failures")
    if absent:
        missing = bytearray(stripe.parity)
        for i, part in enumerate(parts):
            if i != absent[0]:
                for j, value in enumerate(part):
                    missing[j] ^= value
        candidate = bytes(missing)
        if sha256(candidate).hexdigest() != stripe.shard_sha256[absent[0]]:
            raise ValueError("parity cannot reconstruct missing shard digest")
        parts[absent[0]] = candidate
    output = b"".join(parts)[:stripe.original_size]
    if sha256(output).hexdigest() != stripe.source_sha256:
        raise ValueError("reconstructed original payload digest mismatch")
    return output
