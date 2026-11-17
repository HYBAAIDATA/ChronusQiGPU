"""THESEUS-custodied immutable shards with real restart/one-erasure recovery.

Parity-bearing manifests remain under existing THESEUS durability/journaling.
The shard filesystem is a distinct storage surface, not a second database.
This recovers one missing or corrupted shard, not a lost database or whole disk.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

from chronus.storage.durable import DurableTheseusService
from chronus.storage.erasure import ErasureStripe, encode_stripe, recover_stripe

_SCHEMA = "chronus.theseus.protected-stripe/1"


@dataclass(frozen=True)
class ProtectedReceipt:
    tenant_id: str
    manifest_object_id: str
    payload_sha256: str
    schema: str = _SCHEMA


class ProtectedTheseusService:
    """Write physical shard files, with canonical metadata in THESEUS custody."""

    def __init__(self, custody: DurableTheseusService, shard_root: str | Path):
        if not isinstance(custody, DurableTheseusService):
            raise TypeError("THESEUS durable service required")
        root = Path(shard_root)
        if root.is_symlink():
            raise ValueError("shard root must not be a symlink")
        root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir():
            raise ValueError("shard root must be a directory")
        self.custody = custody
        self.shard_root = root.resolve(strict=True)

    def _directory(self, tenant_id: str, payload_sha256: str) -> Path:
        return self.shard_root / sha256(tenant_id.encode("utf-8")).hexdigest() / payload_sha256

    @staticmethod
    def _write_immutable(path: Path, content: bytes) -> None:
        if path.is_symlink():
            raise ValueError("shard symlink refused")
        if path.exists():
            if not path.is_file() or path.read_bytes() != content:
                raise ValueError("immutable shard conflicts with existing file")
            return
        try:
            with path.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            if not path.is_file() or path.is_symlink() or path.read_bytes() != content:
                raise ValueError("concurrent immutable shard conflict") from None

    def store(self, tenant_id: str, payload: bytes, *, shard_count: int = 4) -> ProtectedReceipt:
        if not isinstance(tenant_id, str) or not tenant_id:
            raise ValueError("tenant_id is required")
        stripe, shards = encode_stripe(payload, shard_count)
        directory = self._directory(tenant_id, stripe.source_sha256)
        for candidate in (directory.parent, directory):
            if candidate.is_symlink():
                raise ValueError("shard directory symlink refused")
            candidate.mkdir(exist_ok=True)
            if candidate.is_symlink():
                raise ValueError("shard directory symlink refused")
        for index, data in enumerate(shards):
            self._write_immutable(directory / f"{index}.shard", data)
        manifest: dict[str, Any] = {
            "schema": _SCHEMA,
            "tenant_digest": sha256(tenant_id.encode()).hexdigest(),
            "original_size": stripe.original_size,
            "shard_count": stripe.shard_count,
            "shard_bytes": stripe.shard_bytes,
            "source_sha256": stripe.source_sha256,
            "shard_sha256": list(stripe.shard_sha256),
            "parity_b64": base64.b64encode(stripe.parity).decode("ascii"),
            "parity_sha256": stripe.parity_sha256,
        }
        record_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        stored = self.custody.store(tenant_id, record_bytes)
        self.custody.append_journal_event(
            tenant_id, "PROTECTED_STRIPE_COMMITTED", record_bytes
        )
        return ProtectedReceipt(tenant_id, stored.object_id, stripe.source_sha256)

    def reconstruct(self, receipt: ProtectedReceipt) -> bytes:
        if not isinstance(receipt, ProtectedReceipt) or receipt.schema != _SCHEMA:
            raise ValueError("invalid protected receipt schema")
        record = self.custody.reconstruct(
            receipt.tenant_id, receipt.manifest_object_id
        )
        manifest = json.loads(record.decode("utf-8"))
        if (manifest.get("schema") != _SCHEMA
                or manifest.get("tenant_digest") != sha256(receipt.tenant_id.encode()).hexdigest()
                or manifest.get("source_sha256") != receipt.payload_sha256):
            raise ValueError("manifest/tenant/receipt mismatch")
        parity = base64.b64decode(manifest["parity_b64"], validate=True)
        count, size, width, hashes = (
            manifest.get("shard_count"), manifest.get("original_size"),
            manifest.get("shard_bytes"), manifest.get("shard_sha256"),
        )
        if (type(count) is not int or not 2 <= count <= 32
                or type(size) is not int or not 1 <= size <= (1 << 20)
                or type(width) is not int or width != (size + count - 1) // count
                or not isinstance(hashes, list) or len(hashes) != count
                or any(not isinstance(h, str) or len(h) != 64
                       or any(c not in "0123456789abcdef" for c in h) for h in hashes)
                or len(parity) != width):
            raise ValueError("untrusted stripe manifest outside bounded policy")
        stripe = ErasureStripe(
            original_size=size, shard_count=count, shard_bytes=width,
            source_sha256=manifest["source_sha256"],
            shard_sha256=tuple(hashes), parity=parity,
            parity_sha256=manifest["parity_sha256"],
        )
        directory = self._directory(receipt.tenant_id, stripe.source_sha256)
        if directory.is_symlink() or directory.parent.is_symlink():
            raise ValueError("shard directory symlink refused")
        parts: list[bytes | None] = []
        for index in range(stripe.shard_count):
            path = directory / f"{index}.shard"
            if path.is_symlink():
                raise ValueError("shard symlink refused")
            try:
                part = path.read_bytes()
            except FileNotFoundError:
                part = None
            parts.append(part)
        payload = recover_stripe(stripe, tuple(parts))
        if not self.custody.verify_journal_continuity(receipt.tenant_id):
            raise ValueError("THESEUS journal continuity invalid")
        return payload
