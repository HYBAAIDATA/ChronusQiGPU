"""Virtual memory plane composed over Aethel/HybaSubstrate custody.

Optional Theseus path: when ``CHRONUS_VIGPU_THESEUS=1``, evidence payloads are
also committed through ``aethel.theseus`` (prime keys + phyllotaxis packing).
Default remains HybaSubstrate. Theseus is additive and fail-soft.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading
from typing import Any

from hyba.substrate import HybaSubstrate

from .abi import Workload, WorkloadResult, canonical_json, digest_json


@dataclass(frozen=True)
class PersistedEvidence:
    object_id: str
    fold_id: str
    logical_address: int
    evidence_digest: str
    path: str


class VirtualMemoryPlane:
    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._stores: dict[str, HybaSubstrate] = {}
        self._lock = threading.RLock()
        self.residency: dict[str, str] = {}
        self._theseus: Any = None

    @staticmethod
    def _tenant_name(tenant: str) -> str:
        safe = "".join(c for c in tenant if c.isalnum() or c in "-_")
        if not safe or safe != tenant:
            raise ValueError("tenant contains unsafe filesystem characters")
        return safe

    def _store(self, tenant: str) -> HybaSubstrate:
        tenant = self._tenant_name(tenant)
        if tenant not in self._stores:
            path = self.root / "tenants" / tenant
            if (path / "objects_index.json").is_file():
                self._stores[tenant] = HybaSubstrate.attach(path, tenant=tenant)
            else:
                self._stores[tenant] = HybaSubstrate(tenant=tenant)
        return self._stores[tenant]

    def _maybe_theseus_put(self, payload: bytes) -> None:
        flag = os.environ.get("CHRONUS_VIGPU_THESEUS", "").strip().lower()
        if flag not in {"1", "true", "yes"}:
            return
        try:
            if self._theseus is None:
                from aethel.theseus import open_theseus

                self._theseus = open_theseus(durable=False)
            self._theseus.put(payload, durable=False)
        except Exception:
            # Hyba path is authoritative; Theseus is additive custody.
            return

    def persist(
        self, workload: Workload, result: WorkloadResult, negotiation: dict[str, Any]
    ) -> PersistedEvidence:
        if result.status != "ok":
            raise ValueError("failed results cannot be committed as successful evidence")
        evidence = {
            "schema": "chronus.virtual-igpu-evidence.v1",
            "abi_version": workload.abi_version,
            "workload": workload.as_dict(),
            "result": result.as_dict(),
            "negotiation": negotiation,
        }
        evidence_digest = digest_json(evidence)
        payload = canonical_json(evidence)
        with self._lock:
            store = self._store(workload.tenant)
            identity = store.put(workload.id, payload, transform="virtual_igpu.execute")
            tenant_path = self.root / "tenants" / self._tenant_name(workload.tenant)
            store.persist(tenant_path)
            evidence_dir = self.root / "evidence"
            evidence_dir.mkdir(parents=True, exist_ok=True)
            path = evidence_dir / f"{evidence_digest}.json"
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(payload)
            os.replace(temporary, path)
            self.residency[identity.content_id] = result.executed_on
            self._maybe_theseus_put(payload)
        return PersistedEvidence(
            object_id=identity.content_id,
            fold_id=identity.fold_id,
            logical_address=identity.logical_address,
            evidence_digest=evidence_digest,
            path=str(path),
        )

    def retrieve(self, tenant: str, workload_id: str) -> dict[str, Any]:
        payload = self._store(tenant).get(workload_id)
        return json.loads(payload)

    def checkpoint(self, name: str = "checkpoint") -> dict[str, Any]:
        with self._lock:
            for tenant, store in self._stores.items():
                store.persist(self.root / "tenants" / tenant)
            manifest = {
                "schema": "chronus.virtual-igpu-checkpoint.v1",
                "tenants": sorted(self._stores),
                "residency": dict(sorted(self.residency.items())),
            }
            digest = digest_json(manifest)
            path = self.root / f"{name}-{digest}.json"
            path.write_bytes(canonical_json(manifest))
            return {"digest": digest, "path": str(path)}

    def migrate(self, object_id: str, target_adapter: str) -> None:
        if object_id not in self.residency:
            raise KeyError("unknown object residency")
        self.residency[object_id] = target_adapter
