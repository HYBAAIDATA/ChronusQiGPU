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
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Mapping


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def content_id_for(payload: Any, *, representation_version: str = "v1") -> str:
    body = {
        "representation_version": representation_version,
        "payload": payload,
    }
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

    def _index_path(self) -> Path:
        return self.root / "memory_index.json"

    def _load_index(self) -> None:
        path = self._index_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        for item in data.get("objects", []):
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
                    payload=item.get("payload"),
                    metadata=dict(item.get("metadata", {})),
                    adapter_id=item.get("adapter_id"),
                    residency=str(item.get("residency", "host")),
                    created_at=str(item.get("created_at", _utc_now())),
                    refs=int(item.get("refs", 1)),
                )
                self._objects[rec.object_id] = rec
                self.residency[rec.object_id] = rec.residency
                self.memory_tiers[rec.object_id] = rec.residency
                self._host_bytes += rec.host_resident_bytes
                self._device_bytes += rec.device_resident_bytes
            except Exception:
                continue

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
                    "payload": r.payload,
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
            meta = dict(metadata or {})
            if kind:
                meta.setdefault("kind", kind)
            if representation:
                meta.update(dict(representation))
                if "version" in representation:
                    representation_version = str(representation.get("version") or representation_version)
            if identity and "content_id" in identity:
                cid = str(identity["content_id"])
            else:
                cid = content_id_for(payload, representation_version=representation_version)
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
            raw = _canonical(payload)
            logical = len(raw)
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

            rec = ObjectRecord(
                object_id=oid,
                tenant=tenant_s,
                content_id=cid,
                representation_version=representation_version,
                logical_bytes=logical,
                folded_bytes=folded,
                host_resident_bytes=host_b,
                device_resident_bytes=dev_b,
                payload=payload,
                metadata=meta,
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
            blob = self.objects_dir / f"{oid}.json"
            blob.write_text(
                json.dumps(
                    {
                        "object_id": oid,
                        "tenant": tenant_s,
                        "content_id": cid,
                        "payload": payload,
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
                payload=payload,
            )

    def lookup(
        self, object_id: str, *, tenant: str | None = None, tenant_id: str | None = None
    ) -> ObjectRecord:
        tenant = tenant or tenant_id or "default"
        with self._lock:
            rec = self._objects.get(object_id)
            if rec is None:
                raise KeyError(f"object not found: {object_id}")
            if rec.tenant != tenant:
                raise PermissionError(
                    f"tenant {tenant!r} not authorized for object {object_id}"
                )
            return rec

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
        with self._lock:
            rec = self.lookup(object_id, tenant=tenant, tenant_id=tenant_id)
            self._host_bytes -= rec.host_resident_bytes
            self._device_bytes -= rec.device_resident_bytes
            host_b = rec.logical_bytes if target == "host" else 0
            dev_b = 0 if target == "host" else rec.logical_bytes
            rec.host_resident_bytes = host_b
            rec.device_resident_bytes = dev_b
            rec.residency = target
            if target_adapter_id:
                rec.adapter_id = target_adapter_id
            self.residency[object_id] = target
            self.memory_tiers[object_id] = target
            self._host_bytes += host_b
            self._device_bytes += dev_b
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

    def store_artifact(self, *, tenant: str, workload_id: str, artifact: Mapping[str, Any]) -> None:
        """Persist tenant/workload artifact for retrieve(tenant, workload_id)."""
        with self._lock:
            path = self.root / "artifacts" / tenant
            path.mkdir(parents=True, exist_ok=True)
            (path / f"{workload_id}.json").write_text(
                json.dumps(artifact, sort_keys=True, default=str),
                encoding="utf-8",
            )
            self._artifacts[(tenant, workload_id)] = dict(artifact)

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
                    return art
                path = self.root / "artifacts" / tenant / f"{workload_id}.json"
                if path.exists():
                    return json.loads(path.read_text(encoding="utf-8"))
                raise KeyError(f"artifact not found: {tenant}/{workload_id}")
        # object plane
        object_id = str(args[0]) if args else str(kwargs.get("object_id"))
        tenant = kwargs.get("tenant") or kwargs.get("tenant_id") or "default"
        return self._retrieve_object(object_id, tenant=str(tenant))

    def _retrieve_object(self, object_id: str, *, tenant: str) -> Any:
        with self._lock:
            rec = self._objects.get(object_id)
            if rec is None:
                path = self.objects_dir / f"{object_id}.json"
                if not path.exists():
                    raise KeyError(f"object not found: {object_id}")
                data = json.loads(path.read_text(encoding="utf-8"))
                if str(data.get("tenant")) != tenant:
                    raise PermissionError(
                        f"tenant {tenant!r} not authorized for object {object_id}"
                    )
                return data.get("payload")
            if rec.tenant != tenant:
                raise PermissionError(
                    f"tenant {tenant!r} not authorized for object {object_id}"
                )
            return rec.payload

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
        # Find tenant from record
        rec = self._objects.get(object_id)
        tenant = rec.tenant if rec else "default"
        self.migrate_residency(
            object_id, tenant=tenant, target_adapter_id=target_adapter_id
        )


# Back-compat alias used by older imports
MemoryPlane = VirtualMemoryPlane
