"""Virtual memory plane composed over Aethel/HybaSubstrate custody when present.

Content-addressed buffers and folded objects, tenant-authorized handles,
immutable canonical metadata, reference ownership, bounded eviction, and
host/device residency tracking. Logical size, folded size, host-resident and
device-resident bytes are reported separately.

Optional Theseus path: when ``CHRONUS_VIGPU_THESEUS=1``, evidence payloads may
also be committed through ``aethel.theseus`` (prime keys) if that package is
installed. Absence of Aethel does not block the software memory plane.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import copy
import base64
import hashlib
import json
import os
import re
import threading
import urllib.parse
from pathlib import Path
from typing import Any, Mapping


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _pack_payload(payload):
    if isinstance(payload, bytes):
        return "bytes-base64/v1", base64.b64encode(payload).decode("ascii")
    # Never stringify opaque objects or nested bytes into lossy identities.
    json.dumps(payload, allow_nan=False)
    return "json/v1", payload


def _unpack_payload(codec, payload):
    if codec in (None, "json/v1"):
        return payload
    if codec == "bytes-base64/v1" and isinstance(payload, str):
        return base64.b64decode(payload, validate=True)
    raise ValueError("unsupported persisted memory payload codec")


def content_id_for(payload: Any, *, representation_version: str = "v1") -> str:
    body = {
        "representation_version": representation_version,
        "payload": payload,
    }
    if isinstance(payload, bytes):
        body["payload_type"] = "bytes"
        body["payload"] = base64.b64encode(payload).decode("ascii")
    return hashlib.sha256(_canonical(body)).hexdigest()


@dataclass
class ObjectRecord:
    object_id: str
    tenant: str
    content_id: str
    representation_version: str
    logical_bytes: int
    folded_bytes: int
    host_resident_bytes: int
    device_resident_bytes: int
    payload: Any
    metadata: dict[str, Any] = field(default_factory=dict)
    adapter_id: str | None = None
    residency: str = "host"
    created_at: str = field(default_factory=_utc_now)
    refs: int = 1


class VirtualMemoryPlane:
    """Tenant-scoped, content-addressed object store with residency accounting."""

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        max_host_bytes: int = 512 * 1024 * 1024,
    ) -> None:
        self.root = Path(root or os.getenv("CHRONUS_VIGPU_STORE", ".chronus-virtual-igpu"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.objects_dir = self.root / "objects"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.max_host_bytes = int(max_host_bytes)
        self._lock = threading.RLock()
        self._objects: dict[str, ObjectRecord] = {}
        self._artifacts: dict[tuple[str, str], dict[str, Any]] = {}
        self.residency: dict[str, str] = {}
        self.memory_tiers: dict[str, str] = {}
        self._host_bytes = 0
        self._device_bytes = 0
        self._load_index()

    @staticmethod
    def _checked_object_id(object_id: str) -> str:
        if not isinstance(object_id, str) or not re.fullmatch(r"[0-9a-f]{64}", object_id):
            raise ValueError("object_id must be a canonical SHA-256 handle")
        return object_id

    def _contained_file(self, directory: Path, filename: str) -> Path:
        if directory.is_symlink() or not directory.resolve().is_relative_to(self.root.resolve()):
            raise PermissionError("memory path is outside its owned root")
        path = directory / filename
        if path.is_symlink() or path.resolve().parent != directory.resolve():
            raise PermissionError("memory path escapes its owned directory")
        return path

    def _artifact_path(self, tenant: str, workload_id: str) -> Path:
        if not isinstance(tenant, str) or not tenant or len(tenant) > 256:
            raise ValueError("tenant must be a bounded nonempty string")
        # Safe legacy tenant names retain their paths. Unsafe ids get an exact-id
        # digest suffix, never lossy slash/question-mark replacement or traversal.
        name = tenant if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", tenant) else (
            "tenant~" + hashlib.sha256(tenant.encode()).hexdigest()
        )
        parent = self.root / "artifacts"
        if parent.is_symlink():
            raise PermissionError("artifact root must not be a symlink")
        directory = parent / name
        return self._contained_file(directory, self._artifact_filename(workload_id))

    def _index_path(self) -> Path:
        return self.root / "memory_index.json"

    def _load_index(self) -> None:
        path = self._index_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError("invalid persisted memory index") from exc
        if not isinstance(data, dict) or not isinstance(data.get("objects"), list):
            raise ValueError("invalid persisted memory index schema")
        for item in data["objects"]:
            try:
                rec = ObjectRecord(
                    object_id=str(item["object_id"]),
                    tenant=str(item["tenant"]),
                    content_id=str(item["content_id"]),
                    representation_version=str(item.get("representation_version", "v1")),
                    logical_bytes=int(item.get("logical_bytes", 0)),
                    folded_bytes=int(item.get("folded_bytes", 0)),
                    host_resident_bytes=int(item.get("host_resident_bytes", 0)),
                    device_resident_bytes=int(item.get("device_resident_bytes", 0)),
                    payload=_unpack_payload(item.get("payload_codec"), item.get("payload")),
                    metadata=dict(item.get("metadata", {})),
                    adapter_id=item.get("adapter_id"),
                    residency=str(item.get("residency", "host")),
                    created_at=str(item.get("created_at", _utc_now())),
                    refs=int(item.get("refs", 1)),
                )
                self._checked_object_id(rec.object_id)
                verified_payload = self._retrieve_object(rec.object_id, tenant=rec.tenant)
                if not rec.tenant or rec.content_id != content_id_for(
                    verified_payload, representation_version=rec.representation_version
                ):
                    raise ValueError("persisted content identity mismatch")
                if rec.payload is not None and content_id_for(
                    rec.payload, representation_version=rec.representation_version
                ) != rec.content_id:
                    raise ValueError("persisted index payload mismatch")
                actual_size = len(verified_payload) if isinstance(verified_payload, bytes) else len(_canonical(verified_payload))
                if rec.logical_bytes != actual_size:
                    raise ValueError("persisted logical size mismatch")
                rec.payload = verified_payload if rec.residency == "host" else None
                if min(rec.logical_bytes, rec.folded_bytes, rec.host_resident_bytes,
                       rec.device_resident_bytes, rec.refs) < 0:
                    raise ValueError("negative persisted accounting")
                if rec.object_id in self._objects:
                    raise ValueError("duplicate persisted object handle")
                if rec.residency not in {"host", "folded"} or rec.device_resident_bytes:
                    # A persisted label cannot reattach a real device allocation.
                    rec.residency = "unbound"
                    rec.adapter_id = None
                    rec.device_resident_bytes = 0
                    rec.host_resident_bytes = 0
                    rec.payload = None
                if self._host_bytes + rec.host_resident_bytes > self.max_host_bytes:
                    raise MemoryError("persisted host residency exceeds budget")
                self._objects[rec.object_id] = rec
                self.residency[rec.object_id] = rec.residency
                self.memory_tiers[rec.object_id] = rec.residency
                self._host_bytes += rec.host_resident_bytes
                self._device_bytes += rec.device_resident_bytes
            except Exception as exc:
                raise ValueError("invalid persisted memory record") from exc

    def _save_index(self) -> None:
        payload = {
            "objects": [
                {
                    "object_id": r.object_id,
                    "tenant": r.tenant,
                    "content_id": r.content_id,
                    "representation_version": r.representation_version,
                    "logical_bytes": r.logical_bytes,
                    "folded_bytes": r.folded_bytes,
                    "host_resident_bytes": r.host_resident_bytes,
                    "device_resident_bytes": r.device_resident_bytes,
                    "payload_codec": _pack_payload(r.payload)[0],
                    "payload": _pack_payload(r.payload)[1],
                    "metadata": r.metadata,
                    "adapter_id": r.adapter_id,
                    "residency": r.residency,
                    "created_at": r.created_at,
                    "refs": r.refs,
                }
                for r in self._objects.values()
            ]
        }
        tmp = self._index_path().with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self._index_path())

    def store(
        self,
        payload: Any = None,
        *,
        tenant: str | None = None,
        tenant_id: str | None = None,
        adapter_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        representation_version: str = "v1",
        object_id: str | None = None,
        residency: str = "host",
        # Legacy elevation test signature
        kind: str | None = None,
        identity: Mapping[str, Any] | None = None,
        representation: Mapping[str, Any] | None = None,
        **_extra: Any,
    ) -> Any:
        """Store payload; return object_id (str) or legacy SimpleNamespace with fields."""
        with self._lock:
            tenant_s = str(tenant or tenant_id or "default")
            if residency not in {"host", "folded"}:
                raise NotImplementedError("physical device residency requires a bound transfer adapter")
            payload = copy.deepcopy(payload)
            meta = copy.deepcopy(dict(metadata or {}))
            if kind:
                meta.setdefault("kind", kind)
            if representation:
                meta.update(dict(representation))
                if "version" in representation:
                    representation_version = str(representation.get("version") or representation_version)
            payload_codec, persisted_payload = _pack_payload(payload)
            cid = content_id_for(payload, representation_version=representation_version)
            if identity and "content_id" in identity and identity["content_id"] != cid:
                raise ValueError("caller content_id does not match the payload")
            requested_oid = object_id or (
                str(identity.get("object_id"))
                if identity and identity.get("object_id")
                else cid
            )
            # Handles are tenant-scoped even when the immutable content digest
            # is shared. One tenant can never replace another tenant's owner
            # record merely by storing identical content.
            oid = hashlib.sha256(
                _canonical({"tenant": tenant_s, "object_id": requested_oid})
            ).hexdigest()
            prev = self._objects.get(oid)
            if prev is not None and (prev.tenant != tenant_s or prev.content_id != cid
                                     or prev.representation_version != representation_version):
                raise PermissionError("an existing handle cannot change ownership or content")
            blob = self._contained_file(self.objects_dir, f"{oid}.json")
            raw = _canonical(payload)
            logical = len(payload) if isinstance(payload, bytes) else len(raw)
            folded = logical
            if "folded_bytes" in meta:
                folded = int(meta["folded_bytes"])
            host_b = logical if residency == "host" else 0
            dev_b = 0
            if residency not in {"host", "folded"}:
                dev_b = logical
                host_b = 0

            if host_b and self._host_bytes + host_b > self.max_host_bytes:
                self._evict_until(host_b)
            if host_b and self._host_bytes + host_b > self.max_host_bytes:
                raise MemoryError("host residency budget exceeded")

            rec = ObjectRecord(
                object_id=oid,
                tenant=tenant_s,
                content_id=cid,
                representation_version=representation_version,
                logical_bytes=logical,
                folded_bytes=folded,
                host_resident_bytes=host_b,
                device_resident_bytes=dev_b,
                payload=copy.deepcopy(payload),
                metadata=copy.deepcopy(meta),
                adapter_id=adapter_id,
                residency=residency,
            )
            prev = self._objects.get(oid)
            if prev is not None:
                self._host_bytes -= prev.host_resident_bytes
                self._device_bytes -= prev.device_resident_bytes
            self._objects[oid] = rec
            self.residency[oid] = residency
            self.memory_tiers[oid] = residency
            self._host_bytes += host_b
            self._device_bytes += dev_b
            blob = self._contained_file(self.objects_dir, f"{oid}.json")
            blob.write_text(
                json.dumps(
                    {
                        "object_id": oid,
                        "tenant": tenant_s,
                        "content_id": cid,
                        "payload_codec": payload_codec,
                        "payload": persisted_payload,
                        "metadata": meta,
                        "representation_version": representation_version,
                    },
                    sort_keys=True,
                    default=str,
                ),
                encoding="utf-8",
            )
            self._save_index()
            # Legacy object-like return for acceptance tests
            from types import SimpleNamespace

            return SimpleNamespace(
                object_id=oid,
                content_id=cid,
                tenant=tenant_s,
                tenant_id=tenant_s,
                logical_bytes=logical,
                folded_bytes=folded,
                host_resident_bytes=host_b,
                device_resident_bytes=dev_b,
                residency=residency,
                payload=copy.deepcopy(payload),
            )

    def lookup(
        self, object_id: str, *, tenant: str | None = None, tenant_id: str | None = None
    ) -> ObjectRecord:
        tenant = tenant or tenant_id or "default"
        self._checked_object_id(object_id)
        with self._lock:
            rec = self._objects.get(object_id)
            if rec is None:
                raise KeyError(f"object not found: {object_id}")
            if rec.tenant != tenant:
                raise PermissionError(
                    f"tenant {tenant!r} not authorized for object {object_id}"
                )
            # Return a copy so callers cannot mutate occupancy or ownership.
            return ObjectRecord(
                object_id=rec.object_id,
                tenant=rec.tenant,
                content_id=rec.content_id,
                representation_version=rec.representation_version,
                logical_bytes=rec.logical_bytes,
                folded_bytes=rec.folded_bytes,
                host_resident_bytes=rec.host_resident_bytes,
                device_resident_bytes=rec.device_resident_bytes,
                payload=copy.deepcopy(rec.payload),
                metadata=copy.deepcopy(rec.metadata),
                adapter_id=rec.adapter_id,
                residency=rec.residency,
                created_at=rec.created_at,
                refs=rec.refs,
            )

    def sizes(
        self, object_id: str, *, tenant: str | None = None, tenant_id: str | None = None
    ) -> dict[str, int]:
        rec = self.lookup(object_id, tenant=tenant, tenant_id=tenant_id)
        return {
            "logical_bytes": rec.logical_bytes,
            "folded_bytes": rec.folded_bytes,
            "host_resident_bytes": rec.host_resident_bytes,
            "device_resident_bytes": rec.device_resident_bytes,
        }

    def migrate_residency(
        self,
        object_id: str,
        *,
        tenant: str | None = None,
        tenant_id: str | None = None,
        target_tier: str | None = None,
        target_adapter_id: str | None = None,
    ) -> None:
        target = target_tier or target_adapter_id or "host"
        if target not in {"host", "folded"}:
            raise NotImplementedError("physical device residency requires a bound transfer adapter")
        with self._lock:
            rec = self.lookup(object_id, tenant=tenant, tenant_id=tenant_id)
            host_b = rec.logical_bytes if target == "host" else 0
            if self._host_bytes - rec.host_resident_bytes + host_b > self.max_host_bytes:
                raise MemoryError("host residency budget exceeded")
            payload = self._retrieve_object(object_id, tenant=rec.tenant) if target == "host" else None
            self._host_bytes -= rec.host_resident_bytes
            self._device_bytes -= rec.device_resident_bytes
            rec.host_resident_bytes = host_b
            rec.device_resident_bytes = 0
            rec.payload = payload
            rec.residency = target
            rec.adapter_id = None
            self._objects[object_id] = rec
            self.residency[object_id] = target
            self.memory_tiers[object_id] = target
            self._host_bytes += host_b
            self._save_index()

    def _evict_until(self, need: int) -> None:
        # Bounded eviction: oldest host-resident first
        candidates = sorted(
            (r for r in self._objects.values() if r.host_resident_bytes > 0),
            key=lambda r: r.created_at,
        )
        for rec in candidates:
            if self._host_bytes + need <= self.max_host_bytes:
                break
            self._host_bytes -= rec.host_resident_bytes
            rec.host_resident_bytes = 0
            rec.payload = None
            if rec.device_resident_bytes == 0:
                rec.residency = "folded"
                self.residency[rec.object_id] = "folded"

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "objects": len(self._objects),
                "host_resident_bytes": self._host_bytes,
                "device_resident_bytes": self._device_bytes,
            }

    # --- legacy unit-test helpers -----------------------------------------

    @staticmethod
    def _artifact_filename(workload_id: str) -> str:
        """Filesystem-safe filename for a workload id.

        Workload ids are arbitrary strings (canonical contract ids carry
        ``/`` separators, e.g. ``chronus.first-workload/1``); quoting keeps
        them inside the tenant artifact dir and prevents ``..``/separator
        traversal. Same mapping on store and retrieve.
        """
        return urllib.parse.quote(str(workload_id), safe="") + ".json"

    def store_artifact(self, *, tenant: str, workload_id: str, artifact: Mapping[str, Any]) -> None:
        """Persist tenant/workload artifact for retrieve(tenant, workload_id)."""
        with self._lock:
            path = self._artifact_path(tenant, workload_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(artifact, sort_keys=True, default=str),
                encoding="utf-8",
            )
            self._artifacts[(tenant, workload_id)] = copy.deepcopy(dict(artifact))

    def retrieve(self, *args: Any, **kwargs: Any) -> Any:
        """
        Dual signature:
          retrieve(object_id, tenant=...) — object plane
          retrieve(tenant, workload_id) — artifact plane (unit tests)
        """
        if len(args) == 2 and not kwargs:
            tenant, workload_id = str(args[0]), str(args[1])
            with self._lock:
                art = self._artifacts.get((tenant, workload_id))
                if art is not None:
                    return copy.deepcopy(art)
                path = self._artifact_path(tenant, workload_id)
                if path.exists():
                    return json.loads(path.read_text(encoding="utf-8"))
                raise KeyError(f"artifact not found: {tenant}/{workload_id}")
        # object plane
        object_id = str(args[0]) if args else str(kwargs.get("object_id"))
        tenant = kwargs.get("tenant") or kwargs.get("tenant_id") or "default"
        return self._retrieve_object(object_id, tenant=str(tenant))

    def _retrieve_object(self, object_id: str, *, tenant: str) -> Any:
        self._checked_object_id(object_id)
        with self._lock:
            rec = self._objects.get(object_id)
            if rec is not None and rec.tenant != tenant:
                raise PermissionError("tenant is not authorised for object")
            path = self._contained_file(self.objects_dir, f"{object_id}.json")
            if not path.exists():
                raise KeyError(f"object not found: {object_id}")
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("object_id") != object_id:
                raise ValueError("persisted object handle mismatch")
            if data.get("tenant") != tenant:
                raise PermissionError("tenant is not authorised for persisted object")
            if not isinstance(data.get("representation_version"), str):
                raise ValueError("missing persisted representation version")
            restored_payload = _unpack_payload(data.get("payload_codec"), data.get("payload"))
            cid = content_id_for(restored_payload,
                                 representation_version=data["representation_version"])
            if data.get("content_id") != cid or (rec is not None and rec.content_id != cid):
                raise ValueError("persisted object content identity mismatch")
            return copy.deepcopy(restored_payload)

    def checkpoint(self) -> dict[str, Any]:
        with self._lock:
            path = self.root / "checkpoints"
            path.mkdir(parents=True, exist_ok=True)
            cp = path / f"cp-{len(list(path.glob('*.json')))}.json"
            payload = {
                "objects": list(self._objects.keys()),
                "residency": dict(self.residency),
                "host_bytes": self._host_bytes,
            }
            cp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            return {"path": str(cp), "objects": len(self._objects)}

    def migrate(self, object_id: str, target_adapter_id: str) -> None:
        """Legacy migrate(object_id, adapter_id) used by unit tests."""
        raise PermissionError("legacy migration lacks an explicit caller tenant; use migrate_residency")


# Back-compat alias used by older imports
MemoryPlane = VirtualMemoryPlane
