"""OVID authority and disposable THESEUS discovery over the enterprise format.

The existing authenticated envelope, folding, WAL and replica formats stay
readable. This composition assigns ownership explicitly; it never imports or
migrates the historical ``open_triad`` stores.
"""

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path

from aethel.storage import _atomic_write
from .custody import EnterpriseCustody
from .journal import FileLock, _fsync_directory

OVID_STATE_PROFILE = "ovid-enterprise-state/v1"


class UncertainStateError(RuntimeError):
    """An interrupted mutation requires explicit reconciliation."""


class OvidEnterpriseState:
    authority = "ovid"
    storage_profile = OVID_STATE_PROFILE

    def __init__(self, root, *, tenant, hmac_key, **options):
        if not isinstance(hmac_key, bytes) or len(hmac_key) < 32:
            raise ValueError("OVID requires a private HMAC key of at least 32 bytes")
        self.root, self.tenant = Path(root), tenant
        tenant_path = self.root / "tenants" / EnterpriseCustody._safe_tenant(tenant)
        self._lock = FileLock(tenant_path / "ovid-authority.lock")
        self._pending = tenant_path / "ovid-pending.json"
        with self._lock:
            self.engine = EnterpriseCustody(self.root, tenant=tenant, hmac_key=hmac_key, **options)

    def _tenant(self, tenant):
        if tenant != self.tenant:
            raise PermissionError("OVID tenant mismatch")

    @contextmanager
    def mutation(self, operation):
        with self._lock:
            if self._pending.exists():
                raise UncertainStateError("OVID pending mutation requires reconciliation")
            # Persist before entering an operation that could partially commit.
            _atomic_write(self._pending, json.dumps(operation, sort_keys=True).encode())
            yield
            self._pending.unlink()
            _fsync_directory(self._pending.parent)

    def put_record(self, tenant, record):
        self._tenant(tenant)
        record.validate(self.engine.producer_registry, self.engine.dependency_policy)
        with self.mutation({"kind": "put_record", "id": record.record_id}):
            self.engine.recover()
            # A sealed identity is immutable, including producer provenance.
            try:
                existing = self.engine.get_record(record.record_id)
            except KeyError:
                existing = None
            if existing is not None:
                if existing.to_dict() != record.to_dict():
                    raise ValueError("OVID record identity conflict")
            else:
                self.engine.put_record(record)
            if self.engine.get_record(record.record_id).to_dict() != record.to_dict():
                raise UncertainStateError("OVID readback differs from submitted record")
        return record.record_id

    def get_record(self, tenant, record_id):
        self._tenant(tenant)
        with self._lock:
            if self._pending.exists():
                raise UncertainStateError("OVID pending mutation requires reconciliation")
            return self.engine.get_record(record_id)

    def verify(self, tenant, record_id):
        self.get_record(tenant, record_id)
        return True

    def records(self, tenant):
        self._tenant(tenant)
        with self._lock:
            if self._pending.exists():
                raise UncertainStateError("OVID pending mutation requires reconciliation")
            # Do not inherit list_records' best-effort omission of corrupt rows.
            ids = sorted(
                {p.stem for p in self.engine.primary_dir.glob("*.json")}
                | {p.stem for p in self.engine.replica_dir.glob("*.json")}
            )
            return [self.engine.get_record(rid) for rid in ids]

    def checkpoint(self, tenant, label=""):
        self._tenant(tenant)
        with self.mutation({"kind": "checkpoint", "label": label}):
            self.records_unchecked()
            result = self.engine.checkpoint(label)
            if self.engine.verify_checkpoint(result["checkpoint_id"])["status"] != "PASS":
                raise UncertainStateError("OVID checkpoint readback failed")
        return result

    def records_unchecked(self):
        """Verify every replica identity while holding the mutation lock."""
        ids = {p.stem for p in self.engine.primary_dir.glob("*.json")}
        ids |= {p.stem for p in self.engine.replica_dir.glob("*.json")}
        for rid in ids:
            self.engine.get_record(rid)

    def health(self):
        return {
            **self.engine.health(),
            "status": "uncertain" if self._pending.exists() else self.engine.health()["status"],
            "ready": not self._pending.exists() and self.engine.health()["ready"],
            "authority": self.authority,
            "storage_profile": self.storage_profile,
            "pending_mutation": self._pending.exists(),
        }

    def storage_measurements(self):
        with self._lock:
            records = self.records(self.tenant)
            raw_bytes = sum(len(record.payload) for record in records)
            folded_bytes = self.engine.health()["bytes_used"]
            return {
                "raw_payload_bytes": raw_bytes,
                "primary_folded_payload_bytes": folded_bytes,
                "raw_to_folded_ratio": [raw_bytes, folded_bytes],
                "fold_codec": "zeckendorf_vector_v1",
                "excludes": ["replica", "WAL", "metadata", "checkpoints", "execution_cache"],
            }


class TheseusStateIndex:
    """Rebuildable tenant-local metadata index; all returned records come from OVID."""

    def __init__(self, root, authority):
        self.authority = authority
        self.root = Path(root) / EnterpriseCustody._safe_tenant(authority.tenant)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "projection.json"

    def rebuild(self):
        records = self.authority.records(self.authority.tenant)
        rows = [r.manifest() for r in records]
        body = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
        generation = hashlib.sha256(body).hexdigest()
        _atomic_write(
            self.path,
            json.dumps(
                {
                    "schema": "theseus-ovid-index/v1",
                    "generation": generation,
                    "tenant": self.authority.tenant,
                    "rows": rows,
                },
                sort_keys=True,
            ).encode(),
        )
        return generation

    def query(self, *, tenant, producer=None, workload_id=None):
        self.authority._tenant(tenant)
        # Refresh against authoritative inventory even if the index was edited,
        # deleted or left stale by an interrupted projection update.
        with self.authority._lock:
            self.rebuild()
            rows = json.loads(self.path.read_bytes())["rows"]
            return [
                self.authority.get_record(tenant, row["record_id"])
                for row in rows
                if (producer is None or row["producer"] == producer)
                and (
                    workload_id is None or row["correlation_ids"].get("workload_id") == workload_id
                )
            ]

    def delete(self):
        with self.authority._lock:
            self.path.unlink(missing_ok=True)
