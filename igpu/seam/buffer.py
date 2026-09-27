"""Layer 2 — digested, multi-tenant, audited buffers over igpu.runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from igpu.seam import store
from igpu.seam.types import (
    BufferBacking,
    Err,
    Ok,
    Result,
    SeamError,
    digest_of,
    new_id,
    now_iso,
)


@dataclass
class AccessPolicy:
    owner: str
    readers: Set[str] = field(default_factory=set)
    writers: Set[str] = field(default_factory=set)
    audit_log: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Buffer:
    id: str
    device_id: str
    size_bytes: int
    resident: bool
    backing: BufferBacking
    digest: str
    policy: AccessPolicy
    encrypted: bool
    created_at: str
    payload: bytes = b""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "size_bytes": self.size_bytes,
            "resident": self.resident,
            "backing": self.backing.value,
            "digest": self.digest,
            "encrypted": self.encrypted,
            "created_at": self.created_at,
            "owner": self.policy.owner,
        }


def _authorized(caller: str, buf: Buffer, action: str) -> bool:
    if caller == buf.policy.owner or caller == "seam":
        return True
    if action == "read":
        return caller in buf.policy.readers
    if action in ("write", "release"):
        return caller in buf.policy.writers
    return False


def allocate(
    device_id: str,
    size_bytes: int,
    backing: BufferBacking = BufferBacking.host_mapped,
    policy: Optional[AccessPolicy] = None,
) -> Result[Buffer]:
    cap = store.get_cap(device_id)
    if cap is None:
        return Err(SeamError.device_absent, device_id)
    if store.is_quarantined(device_id):
        return Err(SeamError.device_quarantined, device_id)
    if size_bytes < 0:
        return Err(SeamError.unknown, "size_bytes < 0")
    payload = b"\x00" * int(size_bytes)
    kind = "host"
    try:
        from igpu.runtime import KIND_BUFFER, allocate_device, allocate_host_mapped

        if backing in (BufferBacking.device_private, BufferBacking.unified):
            alloc = allocate_device(size_bytes, mode=KIND_BUFFER)
            kind = alloc.kind
        else:
            allocate_host_mapped(size_bytes)
            kind = "host_mapped"
    except Exception:
        kind = "host"
    pol = policy or AccessPolicy(owner="seam")
    buf = Buffer(
        id=new_id("buf"),
        device_id=device_id,
        size_bytes=int(size_bytes),
        resident=kind not in ("unavailable", "host_fallback"),
        backing=backing,
        digest=digest_of(payload),
        policy=pol,
        encrypted=backing is BufferBacking.encrypted_at_rest,
        created_at=now_iso(),
        payload=payload,
    )
    pol.audit_log.append({"action": "allocate", "caller": "seam", "at": now_iso(), "kind": kind})
    store.put_buffer(buf)
    store.audit("buffer_allocate", buffer_id=buf.id, device_id=device_id, kind=kind)
    return Ok(buf)


def write(caller: str, buffer: Buffer, data: bytes, offset: int = 0) -> Result[Buffer]:
    live = store.get_buffer(buffer.id)
    if live is None:
        return Err(SeamError.unknown, "buffer gone")
    if live.device_id != buffer.device_id:
        return Err(SeamError.capability_mismatch, "cross-device write")
    if not _authorized(caller, live, "write"):
        return Err(SeamError.privacy_violation, caller)
    raw = bytearray(live.payload)
    if offset < 0 or offset + len(data) > max(len(raw), offset + len(data)):
        need = offset + len(data)
        raw.extend(b"\x00" * max(0, need - len(raw)))
    raw[offset : offset + len(data)] = data
    live.payload = bytes(raw)
    live.size_bytes = len(live.payload)
    live.digest = digest_of(live.payload)
    live.policy.audit_log.append({"action": "write", "caller": caller, "at": now_iso()})
    store.put_buffer(live)
    store.audit("buffer_write", buffer_id=live.id, caller=caller)
    return Ok(live)


def read(caller: str, buffer: Buffer, offset: int = 0, length: Optional[int] = None) -> Result[bytes]:
    live = store.get_buffer(buffer.id)
    if live is None:
        return Err(SeamError.unknown, "buffer gone")
    if live.device_id != buffer.device_id:
        return Err(SeamError.capability_mismatch, "cross-device read")
    if not _authorized(caller, live, "read"):
        return Err(SeamError.privacy_violation, caller)
    data = live.payload[offset:] if length is None else live.payload[offset : offset + length]
    actual = digest_of(live.payload)
    if actual != live.digest:
        store.audit("buffer_corruption", buffer_id=live.id)
        return Err(SeamError.buffer_corruption, f"expected {live.digest} actual {actual}")
    live.policy.audit_log.append({"action": "read", "caller": caller, "at": now_iso()})
    return Ok(data)


def release(caller: str, buffer: Buffer) -> Result[None]:
    live = store.get_buffer(buffer.id)
    if live is None:
        return Ok(None)
    if not _authorized(caller, live, "release"):
        return Err(SeamError.privacy_violation, caller)
    store.drop_buffer(live.id)
    store.audit("buffer_release", buffer_id=live.id, caller=caller)
    return Ok(None)
