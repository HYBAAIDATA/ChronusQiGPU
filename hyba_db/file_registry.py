"""Canonical file registry and mining lifecycle projection for ``hyba_db``.

This module is deliberately an extension of ``OntologyStore`` rather than a
second database.  The store owns the SQLite connection, tenant/quota rules and
attestation chain; this registry adds typed file objects, immutable versions,
append-only events, semantic links, recoverable content-addressed blobs and the
minimal first-class mining lifecycle needed by the M3 evidence chain.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from aethel.storage_topology import (
    StorageTopologyError,
    TheseusPhysicalStore,
    TheseusStorageAddress,
    derive_storage_address,
    verify_storage_address,
)

from .models import AccessDenied, IntegrityFailure, InvalidRecord

FILE_CLASSES = frozenset(
    {
        "source_reference",
        "configuration",
        "contract",
        "manifest",
        "stratum_source",
        "plan",
        "lease",
        "execution",
        "candidate_verification",
        "verified_proof",
        "submission",
        "pool_outcome",
        "transform",
        "custody",
        "governance",
        "audit",
        "cache",
        "legacy",
        "experimental",
        "report",
        "package",
        "snapshot",
        "durable_evidence",
    }
)
FILE_STATUSES = frozenset({"ACTIVE", "QUARANTINED", "SUPERSEDED", "RETIRED", "MISSING"})
FILE_EVENTS = frozenset(
    {
        "CREATED",
        "VERSIONED",
        "REGISTERED",
        "CUSTODIED",
        "LINKED",
        "MOVED",
        "RETENTION_APPLIED",
        "QUARANTINED",
        "MISSING",
        "CORRUPT",
        "RECOVERED",
        "SUPERSEDED",
        "DELETED_BY_POLICY",
        "TRANSFORMED",
        "RECONCILED",
    }
)
MINING_KINDS = frozenset(
    {
        "job",
        "search_plan",
        "lease",
        "execution",
        "candidate_verification",
        "verified_proof",
        "submission",
        "pool_outcome",
        "learning",
        "recovery",
    }
)
MINING_STATES = frozenset(
    {
        "PASS",
        "FAIL",
        "MEASURED",
        "GATED",
        "UNAVAILABLE",
        "MISSING",
        "REFUTED",
        # Evidence classes are deliberately distinct from verdicts.
        "SOURCE_PRESENT",
        "SOURCE_WIRED",
        "LOCAL_TEST_PASSED",
        "LOCAL_E2E_EXECUTED",
        "CI_EXECUTED",
        "CI_UNAVAILABLE",
        "LIVE_POOL_OBSERVED",
        "PHYSICAL_DEVICE_OBSERVED",
        "PERFORMANCE_MEASURED",
        "POOL_ACCEPTANCE_OBSERVED",
    }
)

FILE_REGISTRY_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS file_objects(
 tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
 file_object_id TEXT NOT NULL,
 logical_name TEXT NOT NULL,
 file_class TEXT NOT NULL,
 semantic_owner TEXT NOT NULL,
 domain TEXT NOT NULL,
 mime_type TEXT NOT NULL,
 retention_policy TEXT NOT NULL,
 created_at TEXT NOT NULL,
 created_by TEXT NOT NULL,
 current_version_id TEXT,
 status TEXT NOT NULL DEFAULT 'ACTIVE',
 attestation_id TEXT NOT NULL,
 PRIMARY KEY(tenant_id,file_object_id),
 UNIQUE(tenant_id,logical_name),
 FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS file_versions(
 tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
 file_version_id TEXT NOT NULL,
 file_object_id TEXT NOT NULL,
 version INTEGER NOT NULL,
 content_sha256 TEXT NOT NULL,
 size_bytes INTEGER NOT NULL,
 storage_uri TEXT NOT NULL,
 logical_path TEXT NOT NULL,
 created_at TEXT NOT NULL,
 producer TEXT NOT NULL,
 producer_version TEXT NOT NULL,
 schema_version INTEGER NOT NULL,
 evidence_state TEXT NOT NULL,
 custody_record_id TEXT NOT NULL,
 previous_version_id TEXT,
 ovid_lineage_id TEXT,
 transform_contract TEXT,
 transform_version INTEGER,
 exactness TEXT,
 encryption_key_ref TEXT,
 compression TEXT,
 content_encoding TEXT NOT NULL DEFAULT 'identity',
 status TEXT NOT NULL DEFAULT 'ACTIVE',
 attestation_id TEXT NOT NULL,
 PRIMARY KEY(tenant_id,file_version_id),
 UNIQUE(tenant_id,file_object_id,version),
 FOREIGN KEY(tenant_id,file_object_id) REFERENCES file_objects(tenant_id,file_object_id),
 FOREIGN KEY(tenant_id,previous_version_id) REFERENCES file_versions(tenant_id,file_version_id),
 FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS file_provenance(
 tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
 file_version_id TEXT NOT NULL,
 provenance_json TEXT NOT NULL,
 provenance_sha256 TEXT NOT NULL,
 attestation_id TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,file_version_id),
 FOREIGN KEY(tenant_id,file_version_id) REFERENCES file_versions(tenant_id,file_version_id),
 FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS theseus_storage_addresses(
 tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
 file_version_id TEXT NOT NULL,
 address_id TEXT NOT NULL,
 address_json TEXT NOT NULL,
 address_sha256 TEXT NOT NULL,
 custody_record_id TEXT NOT NULL,
 migration_state TEXT NOT NULL,
 attestation_id TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,file_version_id),
 UNIQUE(tenant_id,address_id,file_version_id),
 FOREIGN KEY(tenant_id,file_version_id) REFERENCES file_versions(tenant_id,file_version_id),
 FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id)
);
CREATE INDEX IF NOT EXISTS idx_theseus_address_id
 ON theseus_storage_addresses(tenant_id,address_id);
CREATE TABLE IF NOT EXISTS file_events(
 tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
 event_id TEXT NOT NULL,
 file_version_id TEXT NOT NULL,
 event_type TEXT NOT NULL,
 actor TEXT NOT NULL,
 detail_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 sequence INTEGER NOT NULL,
 PRIMARY KEY(tenant_id,event_id),
 UNIQUE(tenant_id,file_version_id,sequence),
 FOREIGN KEY(tenant_id,file_version_id) REFERENCES file_versions(tenant_id,file_version_id)
);
CREATE TABLE IF NOT EXISTS file_links(
 tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
 link_id TEXT NOT NULL,
 file_version_id TEXT NOT NULL,
 domain_type TEXT NOT NULL,
 domain_id TEXT NOT NULL,
 relationship TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,link_id),
 UNIQUE(tenant_id,file_version_id,domain_type,domain_id,relationship),
 FOREIGN KEY(tenant_id,file_version_id) REFERENCES file_versions(tenant_id,file_version_id)
);
CREATE TABLE IF NOT EXISTS file_intents(
 tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
 intent_id TEXT NOT NULL,
 file_object_id TEXT NOT NULL,
 file_version_id TEXT,
 temp_uri TEXT NOT NULL,
 final_uri TEXT NOT NULL,
 content_sha256 TEXT NOT NULL,
 size_bytes INTEGER NOT NULL,
 state TEXT NOT NULL,
 detail_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,intent_id),
 FOREIGN KEY(tenant_id,file_object_id) REFERENCES file_objects(tenant_id,file_object_id)
);
CREATE TABLE IF NOT EXISTS mining_lifecycle(
 tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
 record_id TEXT NOT NULL,
 kind TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 content_sha256 TEXT NOT NULL,
 evidence_state TEXT NOT NULL,
 parent_ids_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 producer TEXT NOT NULL,
 custody_record_id TEXT NOT NULL,
 PRIMARY KEY(tenant_id,record_id)
);
CREATE INDEX IF NOT EXISTS idx_file_versions_sha ON file_versions(tenant_id,content_sha256);
CREATE INDEX IF NOT EXISTS idx_file_objects_owner_domain
 ON file_objects(tenant_id,semantic_owner,domain);
CREATE INDEX IF NOT EXISTS idx_file_versions_status
 ON file_versions(tenant_id,status);
CREATE INDEX IF NOT EXISTS idx_mining_kind_state
 ON mining_lifecycle(tenant_id,kind,evidence_state);
CREATE INDEX IF NOT EXISTS idx_file_links_domain ON file_links(tenant_id,domain_type,domain_id);
CREATE INDEX IF NOT EXISTS idx_file_events_version ON file_events(tenant_id,file_version_id,sequence);
CREATE INDEX IF NOT EXISTS idx_mining_kind ON mining_lifecycle(tenant_id,kind);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _id(prefix: str, material: bytes) -> str:
    return f"{prefix}_{_sha(material)[:32]}"


@dataclass(frozen=True)
class ReconciliationReport:
    tenant_id: str
    root: str
    healthy: tuple[str, ...]
    orphan_files: tuple[str, ...]
    orphan_records: tuple[str, ...]
    missing_blobs: tuple[str, ...]
    hash_mismatches: tuple[str, ...]
    version_conflicts: tuple[str, ...]
    tenant_mismatches: tuple[str, ...]
    custody_missing: tuple[str, ...]
    domain_link_missing: tuple[str, ...]
    transform_mismatches: tuple[str, ...]
    retention_violations: tuple[str, ...]
    attestation_invalid: tuple[str, ...]
    unresolved: tuple[str, ...]
    generated_at: str

    @property
    def passed(self) -> bool:
        return not self.unresolved

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "hyba.file-reconciliation/v1",
            "tenant_id": self.tenant_id,
            "root": self.root,
            "healthy": list(self.healthy),
            "orphan_files": list(self.orphan_files),
            "orphan_records": list(self.orphan_records),
            "missing_blobs": list(self.missing_blobs),
            "hash_mismatches": list(self.hash_mismatches),
            "version_conflicts": list(self.version_conflicts),
            "tenant_mismatches": list(self.tenant_mismatches),
            "custody_missing": list(self.custody_missing),
            "domain_link_missing": list(self.domain_link_missing),
            "transform_mismatches": list(self.transform_mismatches),
            "retention_violations": list(self.retention_violations),
            "attestation_invalid": list(self.attestation_invalid),
            "unresolved": list(self.unresolved),
            "generated_at": self.generated_at,
            "passed": self.passed,
        }


class FileRegistry:
    """File-plane extension over one existing :class:`OntologyStore` connection."""

    def __init__(self, store: Any, custody: Any | None = None) -> None:
        self.store = store
        self.custody = custody
        self._migrate_provenance()

    def _normalise_provenance(
        self,
        obj: Mapping[str, Any],
        *,
        producer: str,
        producer_version: str,
        schema_version: int,
        evidence_state: str,
        exactness: str | None,
        provenance: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": "hyba.file-provenance/v1",
            "semantic_owner": str(obj["semantic_owner"]),
            "domain": str(obj["domain"]),
            "retention_class": str(obj["retention_policy"]),
            "recovery_class": "UNAVAILABLE",
            "producer": str(producer).strip().lower(),
            "producer_version": str(producer_version),
            "schema_version": int(schema_version),
            "evidence_state": str(evidence_state).upper(),
            "source_ids": [],
            "correlation_ids": {},
            "code_ref": "UNAVAILABLE",
            "package_ref": "UNAVAILABLE",
            "config_digest": "UNAVAILABLE",
            "backend": "UNAVAILABLE",
            "device_identity": "UNAVAILABLE",
            "precision_contract": "UNAVAILABLE",
            "exactness_contract": str(exactness or "UNAVAILABLE"),
            "policy_refs": [],
            "owner_approval_ref": "UNAVAILABLE",
        }
        out.update(dict(provenance or {}))
        out["source_ids"] = [str(x) for x in out.get("source_ids") or ()]
        out["correlation_ids"] = {
            str(k): str(v) for k, v in dict(out.get("correlation_ids") or {}).items()
        }
        out["policy_refs"] = [str(x) for x in out.get("policy_refs") or ()]
        return out

    def _migrate_provenance(self) -> None:
        """Upgrade v2 file rows without inventing historical provenance.

        Unknown historical fields are recorded explicitly as UNAVAILABLE.
        This makes an existing M3 database upgradeable to schema v3 while
        preserving the old file version and custody identities.
        """
        rows = list(
            self.store._db.execute(
                "SELECT fv.*,fo.semantic_owner,fo.domain,fo.retention_policy "
                "FROM file_versions fv JOIN file_objects fo "
                "ON fo.tenant_id=fv.tenant_id AND fo.file_object_id=fv.file_object_id "
                "LEFT JOIN file_provenance fp "
                "ON fp.tenant_id=fv.tenant_id AND fp.file_version_id=fv.file_version_id "
                "WHERE fp.file_version_id IS NULL"
            )
        )
        for row in rows:
            obj = {
                "semantic_owner": row["semantic_owner"],
                "domain": row["domain"],
                "retention_policy": row["retention_policy"],
            }
            prov = self._normalise_provenance(
                obj,
                producer=row["producer"],
                producer_version=row["producer_version"],
                schema_version=row["schema_version"],
                evidence_state=row["evidence_state"],
                exactness=row["exactness"],
                provenance={
                    "migration_state": "LEGACY_PROVENANCE_UNAVAILABLE",
                    "legacy_file_created_at": row["created_at"],
                },
            )
            body = _json(prov)
            digest = _sha(body.encode())
            with self.store._tx() as db:
                att = self.store._attest(
                    db,
                    row["tenant_id"],
                    f"file_provenance:{row['file_version_id']}",
                    "hyba_db",
                    {
                        "file_version_id": row["file_version_id"],
                        "provenance_sha256": digest,
                        "migration_state": "LEGACY_PROVENANCE_UNAVAILABLE",
                    },
                    (),
                )
                db.execute(
                    "INSERT OR IGNORE INTO file_provenance VALUES(?,?,?,?,?,?)",
                    (
                        row["tenant_id"],
                        row["file_version_id"],
                        body,
                        digest,
                        att.id,
                        _now(),
                    ),
                )

    def _tenant(self, tenant_id: str) -> None:
        self.store._tenant(tenant_id)

    def _event(
        self,
        db: Any,
        tenant_id: str,
        version_id: str,
        event_type: str,
        actor: str,
        detail: Mapping[str, Any] | None = None,
    ) -> str:
        if event_type not in FILE_EVENTS:
            raise InvalidRecord(f"unknown file event: {event_type}")
        row = db.execute(
            "SELECT COALESCE(MAX(sequence),-1)+1 FROM file_events WHERE tenant_id=? AND file_version_id=?",
            (tenant_id, version_id),
        ).fetchone()
        sequence = int(row[0])
        event_id = _id("fe", f"{tenant_id}:{version_id}:{sequence}:{event_type}".encode())
        db.execute(
            "INSERT INTO file_events VALUES(?,?,?,?,?,?,?,?)",
            (
                tenant_id,
                event_id,
                version_id,
                event_type,
                actor,
                _json(detail or {}),
                _now(),
                sequence,
            ),
        )
        return event_id

    # Custody OperationalRecord evidence states are the THESEUS taxonomy
    # (records.EVIDENCE_STATES). Extended workflow evidence classes are kept on
    # the file_version row and folded onto the custody taxonomy here.
    _CUSTODY_EVIDENCE_MAP = {
        "SOURCE_PRESENT": "MEASURED",
        "SOURCE_WIRED": "MEASURED",
        "LOCAL_TEST_PASSED": "MEASURED",
        "LOCAL_E2E_EXECUTED": "MEASURED",
        "CI_EXECUTED": "MEASURED",
        "CI_UNAVAILABLE": "UNAVAILABLE",
        "LIVE_POOL_OBSERVED": "MEASURED",
        "PHYSICAL_DEVICE_OBSERVED": "MEASURED",
        "PERFORMANCE_MEASURED": "MEASURED",
        "POOL_ACCEPTANCE_OBSERVED": "MEASURED",
    }

    def _custody_id(
        self,
        tenant_id: str,
        subject_id: str,
        payload: bytes,
        producer: str,
        evidence_state: str,
        supplied: str | None,
        *,
        kind: str = "file_version",
        producer_version: str = "",
        schema_version: int = 1,
        lineage: Sequence[str] = (),
        correlation_ids: Mapping[str, str] | None = None,
        dependencies: Mapping[str, int] | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> str:
        """Bind a verified THESEUS record while preserving producer provenance."""
        if self.custody is None:
            raise InvalidRecord(
                "THESEUS custody adapter required; a custody_record_id may not be self-asserted"
            )
        if supplied:
            supplied = str(supplied)
            if not self.custody.verify(tenant_id, supplied):
                raise IntegrityFailure(f"custody record does not exist in THESEUS: {supplied!r}")
            opener = getattr(self.custody, "open_tenant", None)
            if callable(opener):
                bound = opener(tenant_id).get_record(supplied)
                expected_digest = _sha(bytes(payload))
                if (
                    bound.content_digest != expected_digest
                    or bound.producer != str(producer).strip().lower()
                    or bound.kind != kind
                ):
                    raise IntegrityFailure(
                        "supplied THESEUS record is authentic but not bound to this "
                        "payload/producer/kind"
                    )
            return supplied
        from aethel.enterprise.records import EVIDENCE_STATES, OperationalRecord

        custody_state = (
            evidence_state
            if evidence_state in EVIDENCE_STATES
            else self._CUSTODY_EVIDENCE_MAP[evidence_state]
        )
        correlations = {
            "tenant_id": tenant_id,
            "file_plane_id": subject_id,
            "declared_evidence_state": evidence_state,
            **{str(k): str(v) for k, v in dict(correlation_ids or {}).items()},
        }
        record = OperationalRecord(
            record_id=f"file.{subject_id}",
            producer=producer,
            producer_version=str(producer_version),
            schema_version=int(schema_version),
            kind=kind,
            payload=payload,
            evidence_state=custody_state,
            lineage=tuple(str(x) for x in lineage),
            correlation_ids=correlations,
            dependencies={str(k): int(v) for k, v in dict(dependencies or {}).items()},
            meta=dict(meta or {}),
        )
        custody_id = self.custody.put_record(tenant_id, record)
        if not self.custody.verify(tenant_id, custody_id):
            raise IntegrityFailure(f"THESEUS failed read-back verification for {record.record_id}")
        return str(custody_id)

    def create_object(
        self,
        tenant_id: str,
        logical_name: str,
        file_class: str,
        semantic_owner: str,
        domain: str,
        *,
        mime_type: str | None = None,
        retention_policy: str = "declared",
        created_by: str = "system",
        status: str = "ACTIVE",
    ) -> str:
        self._tenant(tenant_id)
        if file_class not in FILE_CLASSES:
            raise InvalidRecord(f"unknown file_class={file_class!r}")
        if not logical_name or not semantic_owner or not domain:
            raise InvalidRecord("logical_name, semantic_owner and domain are required")
        if status not in FILE_STATUSES:
            raise InvalidRecord(f"unknown file status={status!r}")
        with self.store._tx() as db:
            existing = db.execute(
                "SELECT * FROM file_objects WHERE tenant_id=? AND logical_name=?",
                (tenant_id, logical_name),
            ).fetchone()
            if existing is not None:
                if (
                    existing["file_class"] != file_class
                    or existing["semantic_owner"] != semantic_owner
                    or existing["domain"] != domain
                ):
                    raise InvalidRecord(
                        f"logical_name={logical_name!r} already registered under a "
                        "different class/owner/domain"
                    )
                return str(existing["file_object_id"])
            object_id = _id("fo", f"{tenant_id}:{logical_name}:{uuid.uuid4().hex}".encode())
            created = _now()
            att = self.store._attest(
                db,
                tenant_id,
                f"file_object:{object_id}",
                created_by,
                {"logical_name": logical_name, "file_class": file_class, "owner": semantic_owner},
                (),
            )
            db.execute(
                "INSERT INTO file_objects VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    tenant_id,
                    object_id,
                    logical_name,
                    file_class,
                    semantic_owner,
                    domain,
                    mime_type
                    or mimetypes.guess_type(logical_name)[0]
                    or "application/octet-stream",
                    retention_policy,
                    created,
                    created_by,
                    None,
                    status,
                    att.id,
                ),
            )
        return object_id

    def register_version(
        self,
        tenant_id: str,
        file_object_id: str,
        content: bytes,
        *,
        storage_uri: str,
        logical_path: str,
        producer: str,
        producer_version: str = "",
        schema_version: int = 1,
        evidence_state: str = "MEASURED",
        custody_record_id: str | None = None,
        previous_version_id: str | None = None,
        ovid_lineage_id: str | None = None,
        transform_contract: str | None = None,
        transform_version: int | None = None,
        exactness: str | None = None,
        encryption_key_ref: str | None = None,
        compression: str | None = None,
        content_encoding: str = "identity",
        provenance: Mapping[str, Any] | None = None,
        actor: str | None = None,
    ) -> str:
        self._tenant(tenant_id)
        data = bytes(content)
        digest = _sha(data)
        evidence_state = evidence_state.upper()
        producer = str(producer).strip().lower()
        if evidence_state not in MINING_STATES:
            raise InvalidRecord(f"unknown evidence_state={evidence_state!r}")
        if not producer:
            raise InvalidRecord("producer is required")
        actor = actor or producer
        with self.store._tx() as db:
            obj = db.execute(
                "SELECT * FROM file_objects WHERE tenant_id=? AND file_object_id=?",
                (tenant_id, file_object_id),
            ).fetchone()
            if not obj:
                raise AccessDenied("file object not found in tenant")
            prov = self._normalise_provenance(
                obj,
                producer=producer,
                producer_version=producer_version,
                schema_version=int(schema_version),
                evidence_state=evidence_state,
                exactness=exactness,
                provenance=provenance,
            )
            prov_json = _json(prov)
            prov_digest = _sha(prov_json.encode())
            # Content bytes may be deduplicated without collapsing semantic
            # identity. Only the same bytes AND the same provenance are the
            # same immutable file version.
            same = db.execute(
                "SELECT fv.file_version_id,fp.provenance_sha256 "
                "FROM file_versions fv LEFT JOIN file_provenance fp "
                "ON fp.tenant_id=fv.tenant_id AND fp.file_version_id=fv.file_version_id "
                "WHERE fv.tenant_id=? AND fv.file_object_id=? AND fv.content_sha256=? "
                "ORDER BY fv.version DESC LIMIT 1",
                (tenant_id, file_object_id, digest),
            ).fetchone()
            if same and same["provenance_sha256"] == prov_digest:
                return str(same["file_version_id"])
            previous = previous_version_id or obj["current_version_id"]
            if previous:
                prev = db.execute(
                    "SELECT version FROM file_versions WHERE tenant_id=? AND file_version_id=?",
                    (tenant_id, previous),
                ).fetchone()
                if not prev:
                    raise AccessDenied("previous file version not found in tenant")
                version = int(prev[0]) + 1
            else:
                version = 1
            version_id = _id("fv", f"{tenant_id}:{file_object_id}:{version}:{digest}".encode())
            existing = db.execute(
                "SELECT file_version_id FROM file_versions WHERE tenant_id=? AND file_object_id=? AND version=?",
                (tenant_id, file_object_id, version),
            ).fetchone()
            if existing:
                if existing[0] != version_id:
                    raise InvalidRecord("conflicting content under an existing file version")
                return version_id
            lineage = list(prov.get("source_ids") or ())
            if previous:
                lineage.append(str(previous))
            if ovid_lineage_id:
                lineage.append(str(ovid_lineage_id))
            # Reserve tenant quota before crossing the external THESEUS boundary.
            # The reservation is transactional and rolls back if custody or any
            # subsequent database write fails.
            self.store._reserve(db, tenant_id, 1, len(data), version_id)
            custody_id = self._custody_id(
                tenant_id,
                version_id,
                data,
                producer,
                evidence_state,
                custody_record_id,
                producer_version=producer_version,
                schema_version=int(schema_version),
                lineage=lineage,
                correlation_ids=prov.get("correlation_ids") or {},
                meta=prov,
            )
            att = self.store._attest(
                db,
                tenant_id,
                f"file_version:{version_id}",
                actor,
                {
                    "file_object_id": file_object_id,
                    "version": version,
                    "sha256": digest,
                    "size_bytes": len(data),
                    "custody_record_id": custody_id,
                },
                (),
            )
            db.execute(
                "INSERT INTO file_versions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    tenant_id,
                    version_id,
                    file_object_id,
                    version,
                    digest,
                    len(data),
                    storage_uri,
                    logical_path,
                    _now(),
                    producer,
                    producer_version,
                    int(schema_version),
                    evidence_state,
                    custody_id,
                    previous,
                    ovid_lineage_id,
                    transform_contract,
                    transform_version,
                    exactness,
                    encryption_key_ref,
                    compression,
                    content_encoding,
                    "ACTIVE",
                    att.id,
                ),
            )
            prov_att = self.store._attest(
                db,
                tenant_id,
                f"file_provenance:{version_id}",
                actor,
                {
                    "file_version_id": version_id,
                    "provenance_sha256": prov_digest,
                    "migration_state": "NATIVE_V3",
                },
                (),
            )
            db.execute(
                "INSERT INTO file_provenance VALUES(?,?,?,?,?,?)",
                (tenant_id, version_id, prov_json, prov_digest, prov_att.id, _now()),
            )
            db.execute(
                "UPDATE file_objects SET current_version_id=?,status='ACTIVE' WHERE tenant_id=? AND file_object_id=?",
                (version_id, tenant_id, file_object_id),
            )
            self._event(
                db,
                tenant_id,
                version_id,
                "VERSIONED" if previous else "CREATED",
                actor,
                {"sha256": digest, "size_bytes": len(data)},
            )
            self._event(
                db, tenant_id, version_id, "REGISTERED", actor, {"storage_uri": storage_uri}
            )
            self._event(
                db, tenant_id, version_id, "CUSTODIED", actor, {"custody_record_id": custody_id}
            )
        return version_id

    def bind_storage_address(
        self,
        tenant_id: str,
        file_version_id: str,
        address: TheseusStorageAddress,
        *,
        migration_state: str = "NATIVE",
    ) -> str:
        """Bind one file version to its canonical THESEUS mathematical address.

        The SQLite row is a query projection.  The authoritative binding is
        independently present in the physical address journal and as a
        THESEUS OperationalRecord.
        """
        self._tenant(tenant_id)
        row = self.store._db.execute(
            "SELECT fv.*,fo.file_class FROM file_versions fv "
            "JOIN file_objects fo ON fo.tenant_id=fv.tenant_id "
            "AND fo.file_object_id=fv.file_object_id "
            "WHERE fv.tenant_id=? AND fv.file_version_id=?",
            (tenant_id, file_version_id),
        ).fetchone()
        if row is None:
            raise AccessDenied("file version not found in tenant")
        if address.tenant_id != tenant_id:
            raise IntegrityFailure("THESEUS storage address tenant mismatch")
        if address.scope != str(row["file_class"]):
            raise IntegrityFailure("THESEUS storage address scope mismatch")
        if address.content_sha256 != str(row["content_sha256"]):
            raise IntegrityFailure("THESEUS storage address digest mismatch")

        body = _json(address.to_dict())
        digest = _sha(body.encode("utf-8"))
        existing = self.store._db.execute(
            "SELECT * FROM theseus_storage_addresses "
            "WHERE tenant_id=? AND file_version_id=?",
            (tenant_id, file_version_id),
        ).fetchone()
        if existing is not None:
            if (
                existing["address_id"] != address.address_id
                or existing["address_sha256"] != digest
                or existing["address_json"] != body
            ):
                raise IntegrityFailure("conflicting THESEUS storage address binding")
            if self.custody is None or not self.custody.verify(
                tenant_id, str(existing["custody_record_id"])
            ):
                raise IntegrityFailure("storage-address custody binding is unavailable")
            return str(existing["custody_record_id"])

        custody_id = self._custody_id(
            tenant_id,
            f"storage_address.{file_version_id}.{address.address_id}",
            body.encode("utf-8"),
            "theseus",
            "MEASURED",
            None,
            kind="theseus_storage_address",
            producer_version="storage-topology/1",
            lineage=(file_version_id, str(row["custody_record_id"])),
            correlation_ids={
                "tenant_id": tenant_id,
                "file_version_id": file_version_id,
                "address_id": address.address_id,
            },
            meta={
                "file_version_id": file_version_id,
                "address_id": address.address_id,
                "storage_generation": address.storage_generation,
                "migration_state": str(migration_state),
            },
        )
        with self.store._tx() as db:
            att = self.store._attest(
                db,
                tenant_id,
                f"theseus_storage_address:{file_version_id}",
                "theseus",
                {
                    "file_version_id": file_version_id,
                    "address_id": address.address_id,
                    "address_sha256": digest,
                    "custody_record_id": custody_id,
                    "migration_state": str(migration_state),
                },
                (),
            )
            db.execute(
                "INSERT INTO theseus_storage_addresses VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    tenant_id,
                    file_version_id,
                    address.address_id,
                    body,
                    digest,
                    custody_id,
                    str(migration_state),
                    att.id,
                    _now(),
                ),
            )
        return str(custody_id)

    def storage_address(
        self, tenant_id: str, file_version_id: str
    ) -> TheseusStorageAddress:
        """Load and verify the rebuildable address projection."""
        self._tenant(tenant_id)
        row = self.store._db.execute(
            "SELECT * FROM theseus_storage_addresses "
            "WHERE tenant_id=? AND file_version_id=?",
            (tenant_id, file_version_id),
        ).fetchone()
        if row is None:
            raise InvalidRecord("file version has no THESEUS storage-address binding")
        if _sha(str(row["address_json"]).encode("utf-8")) != row["address_sha256"]:
            raise IntegrityFailure("THESEUS storage-address projection digest mismatch")
        try:
            address = TheseusStorageAddress.from_dict(json.loads(row["address_json"]))
        except (json.JSONDecodeError, StorageTopologyError) as exc:
            raise IntegrityFailure("invalid THESEUS storage-address projection") from exc
        if address.address_id != row["address_id"] or address.tenant_id != tenant_id:
            raise IntegrityFailure("THESEUS storage-address identity mismatch")
        if self.custody is None or not self.custody.verify(
            tenant_id, str(row["custody_record_id"])
        ):
            raise IntegrityFailure("THESEUS storage-address custody is unavailable")
        opener = getattr(self.custody, "open_tenant", None)
        if callable(opener):
            op = opener(tenant_id).get_record(str(row["custody_record_id"]))
            if (
                op.kind != "theseus_storage_address"
                or op.producer != "theseus"
                or op.content_digest != row["address_sha256"]
                or bytes(op.payload) != str(row["address_json"]).encode("utf-8")
            ):
                raise IntegrityFailure("THESEUS storage-address custody mismatch")
        return address

    def append_event(
        self,
        tenant_id: str,
        file_version_id: str,
        event_type: str,
        *,
        actor: str = "system",
        detail: Mapping[str, Any] | None = None,
    ) -> str:
        self._tenant(tenant_id)
        with self.store._tx() as db:
            row = db.execute(
                "SELECT 1 FROM file_versions WHERE tenant_id=? AND file_version_id=?",
                (tenant_id, file_version_id),
            ).fetchone()
            if not row:
                raise AccessDenied("file version not found in tenant")
            return self._event(db, tenant_id, file_version_id, event_type, actor, detail)

    def link(
        self,
        tenant_id: str,
        file_version_id: str,
        domain_type: str,
        domain_id: str,
        *,
        relationship: str = "supports",
    ) -> str:
        self._tenant(tenant_id)
        if not domain_type or not domain_id:
            raise InvalidRecord("domain_type and domain_id are required")
        with self.store._tx() as db:
            v = db.execute(
                "SELECT 1 FROM file_versions WHERE tenant_id=? AND file_version_id=?",
                (tenant_id, file_version_id),
            ).fetchone()
            if not v:
                raise AccessDenied("file version not found in tenant")
            if not self._domain_exists(db, tenant_id, domain_type, domain_id):
                raise AccessDenied(
                    f"domain link does not exist in tenant: {domain_type}:{domain_id}"
                )
            link_id = _id(
                "fl",
                f"{tenant_id}:{file_version_id}:{domain_type}:{domain_id}:{relationship}".encode(),
            )
            db.execute(
                "INSERT OR IGNORE INTO file_links VALUES(?,?,?,?,?,?,?)",
                (tenant_id, link_id, file_version_id, domain_type, domain_id, relationship, _now()),
            )
            self._event(
                db,
                tenant_id,
                file_version_id,
                "LINKED",
                "system",
                {"domain_type": domain_type, "domain_id": domain_id, "relationship": relationship},
            )
            return link_id

    def _domain_exists(self, db: Any, tenant_id: str, domain_type: str, domain_id: str) -> bool:
        if domain_type == "node":
            return bool(
                db.execute(
                    "SELECT 1 FROM nodes WHERE tenant_id=? AND id=?", (tenant_id, domain_id)
                ).fetchone()
            )
        if domain_type in {"attestation", "custody"}:
            return bool(
                db.execute(
                    "SELECT 1 FROM attestations WHERE tenant_id=? AND id=?", (tenant_id, domain_id)
                ).fetchone()
            )
        if domain_type == "file_object":
            return bool(
                db.execute(
                    "SELECT 1 FROM file_objects WHERE tenant_id=? AND file_object_id=?",
                    (tenant_id, domain_id),
                ).fetchone()
            )
        if domain_type == "file_version":
            return bool(
                db.execute(
                    "SELECT 1 FROM file_versions WHERE tenant_id=? AND file_version_id=?",
                    (tenant_id, domain_id),
                ).fetchone()
            )
        if domain_type in {"mining", "mining_lifecycle"}:
            return bool(
                db.execute(
                    "SELECT 1 FROM mining_lifecycle WHERE tenant_id=? AND record_id=?",
                    (tenant_id, domain_id),
                ).fetchone()
            )
        # External references are permitted only when explicitly named and are
        # still tenant-scoped by the link row; adapters must use a real local
        # object type whenever one exists.
        return domain_type.startswith("external:")

    def record_mining(
        self,
        tenant_id: str,
        kind: str,
        payload: Mapping[str, Any],
        *,
        parent_ids: Sequence[str] = (),
        evidence_state: str = "MEASURED",
        producer: str = "pythia",
        custody_record_id: str | None = None,
    ) -> str:
        self._tenant(tenant_id)
        kind = str(kind)
        producer = str(producer).strip().lower()
        evidence_state = str(evidence_state).upper()
        if kind not in MINING_KINDS:
            raise InvalidRecord(f"unknown mining lifecycle kind={kind!r}")
        if evidence_state not in MINING_STATES:
            raise InvalidRecord(f"unknown mining evidence_state={evidence_state!r}")
        body = dict(payload)
        parent_ids = tuple(str(x) for x in parent_ids)
        digest = _sha(_json(body).encode())
        record_id = _id(
            f"mining_{kind}", f"{tenant_id}:{kind}:{digest}:{uuid.uuid4().hex}".encode()
        )
        with self.store._tx() as db:
            rows = []
            for parent in parent_ids:
                row = db.execute(
                    "SELECT kind FROM mining_lifecycle WHERE tenant_id=? AND record_id=?",
                    (tenant_id, parent),
                ).fetchone()
                if not row:
                    raise AccessDenied(f"mining parent not found in tenant: {parent}")
                rows.append(row[0])
            if kind == "verified_proof":
                if (
                    not body.get("target_met")
                    or not body.get("host_verified")
                    or not any(x == "candidate_verification" for x in rows)
                ):
                    raise InvalidRecord(
                        "verified_proof requires a successful host-verified candidate"
                    )
            if kind == "submission" and "verified_proof" not in rows:
                raise InvalidRecord("submission requires a verified_proof parent")
            if kind == "pool_outcome" and "submission" not in rows:
                raise InvalidRecord("pool_outcome requires a submission parent")
            if kind == "candidate_verification" and evidence_state == "PASS":
                if not body.get("sha256d_valid") or not body.get("target_met"):
                    raise InvalidRecord(
                        "passed candidate verification must prove SHA256d and target"
                    )
            custody_id = self._custody_id(
                tenant_id,
                record_id,
                _json(body).encode(),
                producer,
                evidence_state,
                custody_record_id,
                kind="mining_lifecycle",
                producer_version=str(body.get("software_revision", "")),
                lineage=parent_ids,
                correlation_ids={
                    "tenant_id": tenant_id,
                    "mining_record_id": record_id,
                    "kind": kind,
                },
                meta={"semantic_owner": producer, "mining_kind": kind},
            )
            db.execute(
                "INSERT INTO mining_lifecycle VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    tenant_id,
                    record_id,
                    kind,
                    _json(body),
                    digest,
                    evidence_state,
                    _json(parent_ids),
                    _now(),
                    producer,
                    custody_id,
                ),
            )
        return record_id

    def _file_rows(self, tenant_id: str | None = None) -> list[Any]:
        if tenant_id:
            self._tenant(tenant_id)
            return list(
                self.store._db.execute(
                    "SELECT * FROM file_versions WHERE tenant_id=?", (tenant_id,)
                )
            )
        return list(self.store._db.execute("SELECT * FROM file_versions"))

    def verify_database(self, tenant_id: str | None = None) -> dict[str, Any]:
        errors: list[str] = []
        tids = (
            [tenant_id]
            if tenant_id
            else [r[0] for r in self.store._db.execute("SELECT tenant_id FROM tenants")]
        )
        for tid in tids:
            self._tenant(tid)
            for row in self.store._db.execute(
                "SELECT * FROM file_versions WHERE tenant_id=?", (tid,)
            ):
                if len(row["content_sha256"]) != 64 or row["size_bytes"] < 0:
                    errors.append(f"{tid}:{row['file_version_id']}:invalid digest/size")
                if not row["custody_record_id"]:
                    errors.append(f"{tid}:{row['file_version_id']}:missing custody")
                elif self.custody is None:
                    errors.append(f"{tid}:{row['file_version_id']}:custody adapter unavailable")
                elif not self.custody.verify(tid, row["custody_record_id"]):
                    errors.append(f"{tid}:{row['file_version_id']}:custody verification failed")
                else:
                    opener = getattr(self.custody, "open_tenant", None)
                    if callable(opener):
                        try:
                            op = opener(tid).get_record(row["custody_record_id"])
                            if (
                                op.content_digest != row["content_sha256"]
                                or op.producer != row["producer"]
                                or op.kind != "file_version"
                            ):
                                errors.append(
                                    f"{tid}:{row['file_version_id']}:custody binding mismatch"
                                )
                        except Exception as exc:
                            errors.append(
                                f"{tid}:{row['file_version_id']}:custody read-back:{exc}"
                            )
                prov = self.store._db.execute(
                    "SELECT * FROM file_provenance WHERE tenant_id=? AND file_version_id=?",
                    (tid, row["file_version_id"]),
                ).fetchone()
                if prov is None:
                    errors.append(f"{tid}:{row['file_version_id']}:missing provenance")
                else:
                    if _sha(prov["provenance_json"].encode()) != prov["provenance_sha256"]:
                        errors.append(f"{tid}:{row['file_version_id']}:provenance digest mismatch")
                    try:
                        self.store.verify_attestation(tid, prov["attestation_id"])
                        details = self.store.get_attestation(
                            tid, prov["attestation_id"]
                        ).details
                        if (
                            details.get("file_version_id") != row["file_version_id"]
                            or details.get("provenance_sha256") != prov["provenance_sha256"]
                        ):
                            raise IntegrityFailure("provenance attestation mismatch")
                    except Exception as exc:
                        errors.append(
                            f"{tid}:{row['file_version_id']}:provenance attestation:{exc}"
                        )
                if (
                    row["previous_version_id"]
                    and not self.store._db.execute(
                        "SELECT 1 FROM file_versions WHERE tenant_id=? AND file_version_id=?",
                        (tid, row["previous_version_id"]),
                    ).fetchone()
                ):
                    errors.append(f"{tid}:{row['file_version_id']}:missing previous version")
            for row in self.store._db.execute("SELECT * FROM file_links WHERE tenant_id=?", (tid,)):
                if not self._domain_exists(
                    self.store._db, tid, row["domain_type"], row["domain_id"]
                ):
                    errors.append(f"{tid}:{row['link_id']}:dangling domain link")
            for row in self.store._db.execute(
                "SELECT * FROM file_events WHERE tenant_id=? ORDER BY file_version_id,sequence",
                (tid,),
            ):
                if row["event_type"] not in FILE_EVENTS:
                    errors.append(f"{tid}:{row['event_id']}:unknown event")
            for row in self.store._db.execute(
                "SELECT * FROM mining_lifecycle WHERE tenant_id=?", (tid,)
            ):
                if not row["custody_record_id"]:
                    errors.append(f"{tid}:{row['record_id']}:missing mining custody")
                elif self.custody is None:
                    errors.append(f"{tid}:{row['record_id']}:mining custody adapter unavailable")
                elif not self.custody.verify(tid, row["custody_record_id"]):
                    errors.append(f"{tid}:{row['record_id']}:mining custody verification failed")
                else:
                    opener = getattr(self.custody, "open_tenant", None)
                    if callable(opener):
                        try:
                            op = opener(tid).get_record(row["custody_record_id"])
                            if (
                                op.content_digest != row["content_sha256"]
                                or op.producer != row["producer"]
                                or op.kind != "mining_lifecycle"
                            ):
                                errors.append(
                                    f"{tid}:{row['record_id']}:mining custody binding mismatch"
                                )
                        except Exception as exc:
                            errors.append(
                                f"{tid}:{row['record_id']}:mining custody read-back:{exc}"
                            )
                for parent in json.loads(row["parent_ids_json"]):
                    if not self.store._db.execute(
                        "SELECT 1 FROM mining_lifecycle WHERE tenant_id=? AND record_id=?",
                        (tid, parent),
                    ).fetchone():
                        errors.append(f"{tid}:{row['record_id']}:missing mining parent {parent}")
                if row["kind"] == "verified_proof" and row["evidence_state"] not in {
                    "PASS",
                    "MEASURED",
                }:
                    errors.append(f"{tid}:{row['record_id']}:verified proof not positive")
        return {"passed": not errors, "errors": tuple(errors), "file_plane_ok": not errors}

    def verify_mining(self, tenant_id: str | None = None) -> bool:
        tids = (
            [tenant_id]
            if tenant_id
            else [r[0] for r in self.store._db.execute("SELECT tenant_id FROM tenants")]
        )
        for tid in tids:
            self._tenant(tid)
            rows = list(
                self.store._db.execute("SELECT * FROM mining_lifecycle WHERE tenant_id=?", (tid,))
            )
            by_id = {row["record_id"]: row for row in rows}
            for row in rows:
                try:
                    parents = json.loads(row["parent_ids_json"])
                    parent_kinds = {by_id[parent]["kind"] for parent in parents}
                except (KeyError, TypeError, json.JSONDecodeError):
                    return False
                payload = json.loads(row["payload_json"])
                if row["kind"] == "verified_proof":
                    if (
                        "candidate_verification" not in parent_kinds
                        or not payload.get("target_met")
                        or not payload.get("host_verified")
                    ):
                        return False
                if row["kind"] == "submission" and "verified_proof" not in parent_kinds:
                    return False
                if row["kind"] == "pool_outcome" and "submission" not in parent_kinds:
                    return False
                if row["kind"] == "candidate_verification" and row["evidence_state"] == "PASS":
                    if not payload.get("sha256d_valid") or not payload.get("target_met"):
                        return False
                if not row["custody_record_id"]:
                    return False
        return True

    def import_existing(
        self,
        tenant_id: str,
        root: str | Path,
        source: str | Path,
        *,
        file_class: str = "legacy",
        semantic_owner: str = "hyba_db",
        domain: str = "bootstrap",
        producer: str = "hyba_db",
        evidence_state: str = "MEASURED",
        links: Sequence[tuple[str, str, str]] = (),
    ) -> dict[str, Any]:
        """§11 bootstrap: import pre-existing files into the plane.

        Every imported file gets the full pipeline — tenant scoping, CAS
        placement, custody, events, links — plus an ``imported_existing``
        marker on the REGISTERED event so the provenance is explicit: these
        artifacts existed before the registry did, and that fact is recorded
        rather than rewritten as fresh creation.
        """
        self._tenant(tenant_id)
        source_path = Path(source)
        files = (
            [source_path]
            if source_path.is_file()
            else sorted(p for p in source_path.rglob("*") if p.is_file())
        )
        imported: list[dict[str, str]] = []
        for path in files:
            content = path.read_bytes()
            logical = path.name if source_path.is_file() else str(path.relative_to(source_path))
            object_id, version_id = self.put_file(
                tenant_id,
                root,
                logical_name=f"imported/{logical}",
                file_class=file_class,
                semantic_owner=semantic_owner,
                domain=domain,
                content=content,
                producer=producer,
                evidence_state=evidence_state,
                links=links,
            )
            self.append_event(
                tenant_id,
                version_id,
                "REGISTERED",
                actor=producer,
                detail={"imported_existing": True, "source_path": str(path)},
            )
            imported.append(
                {
                    "source_path": str(path),
                    "file_object_id": object_id,
                    "file_version_id": version_id,
                    "content_sha256": _sha(content),
                }
            )
        return {"imported": imported, "count": len(imported)}

    def stats(
        self, tenant_id: str | None = None, *, root: str | Path | None = None
    ) -> dict[str, Any]:
        """§16 observability surface: counts, health and chain state.

        Read-only projection over the file plane — every number here is
        measured from the tables, not derived from flags. Statuses are
        derived, never optimistic: anything that cannot be measured from
        the given inputs reports ``UNAVAILABLE`` (e.g. reconcile truth needs
        the storage root; custody truth needs a custody adapter).
        """
        if tenant_id:
            self._tenant(tenant_id)
        tids = (
            [tenant_id]
            if tenant_id
            else [r[0] for r in self.store._db.execute("SELECT tenant_id FROM tenants")]
        )
        out: dict[str, Any] = {"schema": "hyba.file-plane-stats/v1", "tenants": {}}
        for tid in tids:
            db = self.store._db
            by_class = {
                r["file_class"]: r["n"]
                for r in db.execute(
                    "SELECT file_class, COUNT(*) n FROM file_objects "
                    "WHERE tenant_id=? GROUP BY file_class",
                    (tid,),
                )
            }
            by_status = {
                r["status"]: r["n"]
                for r in db.execute(
                    "SELECT status, COUNT(*) n FROM file_versions "
                    "WHERE tenant_id=? GROUP BY status",
                    (tid,),
                )
            }
            by_kind = {
                r["kind"]: r["n"]
                for r in db.execute(
                    "SELECT kind, COUNT(*) n FROM mining_lifecycle "
                    "WHERE tenant_id=? GROUP BY kind",
                    (tid,),
                )
            }
            uncustodied = db.execute(
                "SELECT COUNT(*) FROM file_versions WHERE tenant_id=? AND custody_record_id=''",
                (tid,),
            ).fetchone()[0]
            custody_unverified = 0
            custody_checked = 0
            if self.custody is not None:
                for (cid,) in db.execute(
                    "SELECT custody_record_id FROM file_versions WHERE tenant_id=?",
                    (tid,),
                ):
                    custody_checked += 1
                    if not self.custody.verify(tid, cid):
                        custody_unverified += 1
            intents = {
                r["state"]: r["n"]
                for r in db.execute(
                    "SELECT state, COUNT(*) n FROM file_intents WHERE tenant_id=? GROUP BY state",
                    (tid,),
                )
            }
            usage = db.execute(
                "SELECT used_records, used_blob_bytes, max_records, max_blob_bytes "
                "FROM tenants WHERE tenant_id=?",
                (tid,),
            ).fetchone()
            pending_recovery = sum(n for state, n in intents.items() if state not in {"COMMITTED"})
            # Post-recovery semantic revalidation belongs to the producing
            # subsystem; these versions carry a state that still owes one.
            pending_revalidation = sum(
                by_status.get(s, 0) for s in ("QUARANTINED", "RECOVERED", "MISSING")
            )
            last_verified = db.execute(
                "SELECT MAX(created_at) FROM file_events WHERE tenant_id=? "
                "AND event_type IN ('RECONCILED','CUSTODIED','RECOVERED')",
                (tid,),
            ).fetchone()[0]
            last_event = db.execute(
                "SELECT MAX(created_at) FROM file_events WHERE tenant_id=?", (tid,)
            ).fetchone()[0]
            if self.custody is None:
                custody_status = "VERIFIED" if custody_checked else "UNAVAILABLE"
            elif custody_unverified:
                custody_status = "VIOLATIONS"
            else:
                custody_status = "VERIFIED" if custody_checked else "EMPTY"
            if not by_status:
                registry_status = "EMPTY"
            elif uncustodied or pending_recovery:
                registry_status = "VIOLATIONS"
            else:
                registry_status = "VERIFIED"
            status: dict[str, Any] = {
                "registry_status": registry_status,
                "custody_status": custody_status,
                "pending_recovery": pending_recovery,
                "pending_semantic_revalidation": pending_revalidation,
                "last_verified_at": last_verified if last_verified else "UNAVAILABLE",
                "last_event_at": last_event if last_event else "UNAVAILABLE",
            }
            if root is not None:
                report = self.reconcile_files(tid, root)
                status.update(
                    {
                        "reconciliation_status": ("VERIFIED" if report.passed else "VIOLATIONS"),
                        "orphan_files": len(report.orphan_files),
                        "orphan_records": len(report.orphan_records),
                        "missing_blobs": len(report.missing_blobs),
                        "hash_mismatches": len(report.hash_mismatches),
                    }
                )
            else:
                status.update(
                    {
                        "reconciliation_status": "UNAVAILABLE",
                        "orphan_files": "UNAVAILABLE",
                        "orphan_records": "UNAVAILABLE",
                        "missing_blobs": "UNAVAILABLE",
                        "hash_mismatches": "UNAVAILABLE",
                    }
                )
            out["tenants"][tid] = {
                "file_objects_by_class": by_class,
                "file_versions_by_status": by_status,
                "mining_records_by_kind": by_kind,
                "uncustodied_versions": uncustodied,
                "custody_checked": custody_checked,
                "custody_unverified": custody_unverified,
                "intents_by_state": intents,
                "quota_used_records": usage["used_records"] if usage else 0,
                "quota_used_blob_bytes": usage["used_blob_bytes"] if usage else 0,
                "quota_max_records": usage["max_records"] if usage else 0,
                "quota_max_blob_bytes": usage["max_blob_bytes"] if usage else 0,
                "status": status,
                "links": db.execute(
                    "SELECT COUNT(*) FROM file_links WHERE tenant_id=?", (tid,)
                ).fetchone()[0],
                "events": db.execute(
                    "SELECT COUNT(*) FROM file_events WHERE tenant_id=?", (tid,)
                ).fetchone()[0],
                "provenance_rows": db.execute(
                    "SELECT COUNT(*) FROM file_provenance WHERE tenant_id=?", (tid,)
                ).fetchone()[0],
            }
        return out

    def replay_lineage(self, tenant_id: str, record_id: str) -> dict[str, Any]:
        """Reconstruct a mining lineage chain from persisted state.

        Walks ``parent_ids`` back to the chain root and re-hashes every
        payload against its stored ``content_sha256`` — replay proves the
        lineage is intact after a process restart, not just present.
        """
        self._tenant(tenant_id)
        rows = {
            row["record_id"]: row
            for row in self.store._db.execute(
                "SELECT * FROM mining_lifecycle WHERE tenant_id=?", (tenant_id,)
            )
        }
        if record_id not in rows:
            raise AccessDenied(f"mining record not found in tenant: {record_id}")
        chain: list[dict[str, Any]] = []
        seen: set[str] = set()
        stack = [record_id]
        while stack:
            rid = stack.pop()
            if rid in seen:
                continue
            seen.add(rid)
            row = rows.get(rid)
            if row is None:
                raise IntegrityFailure(f"lineage parent missing from store: {rid}")
            payload = row["payload_json"]
            digest_ok = _sha(payload.encode()) == row["content_sha256"]
            parents = tuple(json.loads(row["parent_ids_json"]))
            chain.append(
                {
                    "record_id": rid,
                    "kind": row["kind"],
                    "payload": json.loads(payload),
                    "content_sha256": row["content_sha256"],
                    "digest_ok": digest_ok,
                    "parents": parents,
                    "evidence_state": row["evidence_state"],
                    "custody_record_id": row["custody_record_id"],
                }
            )
            stack.extend(parents)
        order = {
            kind: i
            for i, kind in enumerate(
                (
                    "job",
                    "search_plan",
                    "lease",
                    "execution",
                    "candidate_verification",
                    "verified_proof",
                    "submission",
                    "pool_outcome",
                    "learning",
                    "recovery",
                )
            )
        }
        chain.sort(key=lambda item: order.get(item["kind"], 99))
        return {
            "record_id": record_id,
            "chain": chain,
            "digest_ok": all(item["digest_ok"] for item in chain),
            "length": len(chain),
        }

    def reconcile_files(self, tenant_id: str, root: str | Path) -> ReconciliationReport:
        """Compare declared root vs registry vs custody vs domain links.

        Classes follow the workflow taxonomy. ``ORPHAN_FILE`` is a blob with no
        registry row; ``MISSING_BLOB`` is a registered file:// version whose
        blob is absent under the root; ``ORPHAN_RECORD`` is a registry row
        whose storage URI cannot be resolved to any verifiable blob at all
        (non-file scheme or outside the reconciled root).
        """
        self._tenant(tenant_id)
        root_path = Path(root)
        root_path.mkdir(parents=True, exist_ok=True)
        resolved_root = root_path.resolve()
        rows = self._file_rows(tenant_id)
        pending_intents = self.store._db.execute(
            "SELECT intent_id FROM file_intents WHERE tenant_id=? AND state != 'COMMITTED'",
            (tenant_id,),
        ).fetchall()
        expected: dict[str, Any] = {}
        healthy: list[str] = []
        missing: list[str] = []
        hashes: list[str] = []
        orphan_records: list[str] = []
        version_conflicts: list[str] = []
        tenant_mismatches: list[str] = []
        custody_missing: list[str] = []
        domain_link_missing: list[str] = []
        transform_mismatches: list[str] = []
        retention_violations: list[str] = []
        attestation_invalid: list[str] = []
        attestation_cache: dict[str, bool] = {}
        for row in rows:
            version_id = row["file_version_id"]
            uri = str(row["storage_uri"])
            if not uri.startswith("file://"):
                orphan_records.append(version_id)
                continue
            path = Path(uri[7:])
            try:
                resolved = path.resolve()
            except OSError:
                orphan_records.append(version_id)
                continue
            try:
                rel = resolved.relative_to(resolved_root)
            except ValueError:
                orphan_records.append(version_id)
                continue
            expected[str(resolved)] = version_id
            # CAS layout is <root>/<tenant>/<file-class>/<sha-prefix>/<sha256>;
            # a blob filed under another tenant's segment is a tenant mismatch.
            parts = rel.parts
            if len(parts) >= 4 and parts[0] != tenant_id:
                tenant_mismatches.append(version_id)
                continue
            if not path.is_file():
                missing.append(version_id)
                continue
            data = path.read_bytes()
            if len(data) != row["size_bytes"] or _sha(data) != row["content_sha256"]:
                hashes.append(version_id)
                continue
            if row["status"] in {"MISSING", "QUARANTINED"}:
                version_conflicts.append(version_id)
                continue
            if row["status"] == "RETIRED":
                has_retention_event = self.store._db.execute(
                    "SELECT 1 FROM file_events WHERE tenant_id=? AND file_version_id=? "
                    "AND event_type IN ('RETENTION_APPLIED','DELETED_BY_POLICY')",
                    (tenant_id, version_id),
                ).fetchone()
                if not has_retention_event:
                    retention_violations.append(version_id)
                    continue
            custody_id = row["custody_record_id"]
            if (
                not custody_id
                or self.custody is None
                or not self.custody.verify(tenant_id, str(custody_id))
            ):
                custody_missing.append(version_id)
                continue
            # Read-side integrity: every version's attestation must verify
            # under the store's integrity key, or a wrong/forged key silently
            # 'reconciles' rows it cannot vouch for.
            aid = str(row["attestation_id"])
            if aid not in attestation_cache:
                try:
                    attestation_cache[aid] = bool(self.store.verify_attestation(tenant_id, aid))
                except IntegrityFailure:
                    attestation_cache[aid] = False
            if not attestation_cache[aid]:
                attestation_invalid.append(version_id)
                continue
            if not self.store._db.execute(
                "SELECT 1 FROM file_links WHERE tenant_id=? AND file_version_id=?",
                (tenant_id, version_id),
            ).fetchone():
                domain_link_missing.append(version_id)
                continue
            if (row["ovid_lineage_id"] is None) != (row["transform_contract"] is None):
                transform_mismatches.append(version_id)
                continue
            healthy.append(version_id)
        # Version-chain integrity: current_version_id must point at the highest
        # registered version and every previous link must resolve in-tenant.
        for obj in self.store._db.execute(
            "SELECT * FROM file_objects WHERE tenant_id=?", (tenant_id,)
        ).fetchall():
            versions = self.store._db.execute(
                "SELECT file_version_id, version FROM file_versions "
                "WHERE tenant_id=? AND file_object_id=? ORDER BY version",
                (tenant_id, obj["file_object_id"]),
            ).fetchall()
            if versions and obj["current_version_id"] != versions[-1]["file_version_id"]:
                version_conflicts.append(str(obj["file_object_id"]))
        actual = {
            str(p.resolve())
            for p in root_path.rglob("*")
            if p.is_file() and ".tmp." not in p.name and p.suffix != ".tmp"
        }
        orphan_files = sorted(actual - set(expected))
        unresolved_list = (
            missing
            + hashes
            + orphan_records
            + version_conflicts
            + tenant_mismatches
            + custody_missing
            + domain_link_missing
            + transform_mismatches
            + retention_violations
            + attestation_invalid
            + orphan_files
        )
        unresolved_list.extend(f"intent:{row['intent_id']}" for row in pending_intents)
        return ReconciliationReport(
            tenant_id=tenant_id,
            root=str(root_path),
            healthy=tuple(sorted(healthy)),
            orphan_files=tuple(orphan_files),
            orphan_records=tuple(sorted(orphan_records)),
            missing_blobs=tuple(sorted(missing)),
            hash_mismatches=tuple(sorted(hashes)),
            version_conflicts=tuple(sorted(set(version_conflicts))),
            tenant_mismatches=tuple(sorted(tenant_mismatches)),
            custody_missing=tuple(sorted(custody_missing)),
            domain_link_missing=tuple(sorted(domain_link_missing)),
            transform_mismatches=tuple(sorted(transform_mismatches)),
            retention_violations=tuple(sorted(retention_violations)),
            attestation_invalid=tuple(sorted(attestation_invalid)),
            unresolved=tuple(sorted(set(unresolved_list))),
            generated_at=_now(),
        )

    def recover_blob_from_custody(
        self,
        tenant_id: str,
        file_version_id: str,
        root: str | Path,
    ) -> dict[str, Any]:
        """Recover one missing/corrupt CAS blob from canonical THESEUS custody.

        The database row is a projection and supplies identity/placement only.
        Recovery trusts the authenticated THESEUS OperationalRecord bytes,
        verifies their digest/producer/kind against the projection, then writes
        them atomically to the canonical CAS path under the requested root.
        """
        self._tenant(tenant_id)
        if self.custody is None:
            raise InvalidRecord("THESEUS custody adapter required for blob recovery")
        opener = getattr(self.custody, "open_tenant", None)
        if not callable(opener):
            raise InvalidRecord("custody adapter does not expose recoverable record bytes")

        row = self.store._db.execute(
            "SELECT fv.*,fo.file_class FROM file_versions fv "
            "JOIN file_objects fo "
            "ON fo.tenant_id=fv.tenant_id AND fo.file_object_id=fv.file_object_id "
            "WHERE fv.tenant_id=? AND fv.file_version_id=?",
            (tenant_id, str(file_version_id)),
        ).fetchone()
        if row is None:
            raise AccessDenied("file version not found in tenant")
        custody_id = str(row["custody_record_id"] or "")
        if not custody_id:
            raise IntegrityFailure("file version has no THESEUS custody record")

        op = opener(tenant_id).get_record(custody_id)
        payload = bytes(op.payload)
        digest = _sha(payload)
        if (
            digest != row["content_sha256"]
            or len(payload) != int(row["size_bytes"])
            or op.content_digest != row["content_sha256"]
            or op.producer != row["producer"]
            or op.kind != "file_version"
        ):
            raise IntegrityFailure(
                f"THESEUS recovery binding mismatch for {file_version_id}"
            )

        base = Path(root) / tenant_id / str(row["file_class"]) / digest[:2]
        base.mkdir(parents=True, exist_ok=True)
        final = base / digest
        current_ok = (
            final.is_file()
            and final.stat().st_size == len(payload)
            and _sha(final.read_bytes()) == digest
        )
        if not current_ok:
            fd, temp_name = tempfile.mkstemp(prefix=f".{digest}.", suffix=".tmp", dir=base)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, final)
            except Exception:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
                raise

        with self.store._tx() as db:
            db.execute(
                "UPDATE file_versions SET storage_uri=?,logical_path=?,status='ACTIVE' "
                "WHERE tenant_id=? AND file_version_id=?",
                (f"file://{final}", str(final), tenant_id, str(file_version_id)),
            )
            self._event(
                db,
                tenant_id,
                str(file_version_id),
                "RECOVERED",
                "theseus",
                {
                    "custody_record_id": custody_id,
                    "content_sha256": digest,
                    "storage_uri": str(final),
                    "already_healthy": current_ok,
                },
            )
        return {
            "schema": "hyba.file-blob-recovery/v1",
            "tenant_id": tenant_id,
            "file_version_id": str(file_version_id),
            "custody_record_id": custody_id,
            "content_sha256": digest,
            "storage_uri": f"file://{final}",
            "recovered": not current_ok,
            "passed": True,
        }

    def recover_blobs_from_custody(
        self,
        tenant_id: str,
        root: str | Path,
        *,
        only_unhealthy: bool = True,
    ) -> dict[str, Any]:
        """Recover the tenant's projected file bytes from THESEUS.

        This restores the content plane for existing projection rows. It does
        not fabricate database rows or semantic links that are absent from the
        projection.
        """
        self._tenant(tenant_id)
        rows = list(
            self.store._db.execute(
                "SELECT fv.file_version_id,fv.storage_uri,fv.content_sha256,fv.size_bytes,"
                "fo.file_class FROM file_versions fv JOIN file_objects fo "
                "ON fo.tenant_id=fv.tenant_id AND fo.file_object_id=fv.file_object_id "
                "WHERE fv.tenant_id=? ORDER BY fv.created_at,fv.file_version_id",
                (tenant_id,),
            )
        )
        recovered: list[str] = []
        healthy: list[str] = []
        errors: list[str] = []
        for row in rows:
            path = (
                Path(str(row["storage_uri"])[7:])
                if str(row["storage_uri"]).startswith("file://")
                else None
            )
            canonical = (
                Path(root)
                / tenant_id
                / str(row["file_class"])
                / str(row["content_sha256"])[:2]
                / str(row["content_sha256"])
            )
            is_healthy = bool(
                path is not None
                and path.resolve() == canonical.resolve()
                and path.is_file()
                and path.stat().st_size == int(row["size_bytes"])
                and _sha(path.read_bytes()) == row["content_sha256"]
            )
            if only_unhealthy and is_healthy:
                healthy.append(str(row["file_version_id"]))
                continue
            try:
                result = self.recover_blob_from_custody(
                    tenant_id, str(row["file_version_id"]), root
                )
                if result["recovered"]:
                    recovered.append(str(row["file_version_id"]))
                else:
                    healthy.append(str(row["file_version_id"]))
            except Exception as exc:
                errors.append(
                    f"{row['file_version_id']}:{type(exc).__name__}:{exc}"
                )
        return {
            "schema": "hyba.file-blob-recovery-batch/v1",
            "tenant_id": tenant_id,
            "recovered": tuple(recovered),
            "healthy": tuple(healthy),
            "errors": tuple(errors),
            "passed": not errors,
        }

    def recover_intents(self, tenant_id: str, root: str | Path) -> list[dict[str, str]]:
        """Resolve interrupted writes without fabricating provenance."""
        self._tenant(tenant_id)
        root_path = Path(root)
        results: list[dict[str, str]] = []
        rows = self.store._db.execute(
            "SELECT * FROM file_intents WHERE tenant_id=? AND state != 'COMMITTED'",
            (tenant_id,),
        ).fetchall()
        for row in rows:
            state = "QUARANTINED"
            version_id = row["file_version_id"]
            recovered_by_custody = False
            final = Path(row["final_uri"]) if row["final_uri"] else None
            if final is not None and not final.is_absolute():
                final = root_path / final
            if version_id:
                version = self.store._db.execute(
                    "SELECT content_sha256,size_bytes FROM file_versions "
                    "WHERE tenant_id=? AND file_version_id=?",
                    (tenant_id, version_id),
                ).fetchone()
                if version and final is not None and final.is_file():
                    digest = _sha(final.read_bytes())
                    if digest == version["content_sha256"] and final.stat().st_size == int(
                        version["size_bytes"]
                    ):
                        state = "RECOVERED"
                if state != "RECOVERED" and version is not None and self.custody is not None:
                    try:
                        result = self.recover_blob_from_custody(
                            tenant_id, str(version_id), root_path
                        )
                        if result["passed"]:
                            state = "RECOVERED"
                            recovered_by_custody = True
                    except Exception:
                        # The intent remains quarantined. Recovery failures are
                        # preserved by state rather than converted to success.
                        pass
            with self.store._tx() as db:
                db.execute(
                    "UPDATE file_intents SET state=?,updated_at=? WHERE tenant_id=? AND intent_id=?",
                    (state, _now(), tenant_id, row["intent_id"]),
                )
                if version_id and not (state == "RECOVERED" and recovered_by_custody):
                    self._event(
                        db,
                        tenant_id,
                        version_id,
                        "RECOVERED" if state == "RECOVERED" else "QUARANTINED",
                        "recovery",
                        {"intent_id": row["intent_id"], "state": state},
                    )
            results.append({"intent_id": row["intent_id"], "state": state})
        return results

    def reconcile_and_record(
        self, tenant_id: str, root: str | Path, *, custody_record_id: str | None = None
    ) -> tuple[ReconciliationReport, tuple[str, str] | None]:
        report = self.reconcile_files(tenant_id, root)
        if custody_record_id is None and self.custody is None:
            return report, None
        payload = _json(report.to_dict()).encode()
        result = self.put_file(
            tenant_id,
            root,
            logical_name=f"reconciliation-{report.generated_at}.json",
            file_class="audit",
            semantic_owner="theseus",
            domain="reconciliation",
            content=payload,
            producer="theseus",
            evidence_state="PASS" if report.passed else "FAIL",
            custody_record_id=custody_record_id,
            links=(("external:reconciliation", report.generated_at, "describes"),),
        )
        return report, result

    def put_file(
        self,
        tenant_id: str,
        root: str | Path,
        *,
        logical_name: str,
        file_class: str,
        semantic_owner: str,
        domain: str,
        content: bytes,
        producer: str,
        custody_record_id: str | None = None,
        evidence_state: str = "MEASURED",
        producer_version: str = "",
        schema_version: int = 1,
        provenance: Mapping[str, Any] | None = None,
        links: Sequence[tuple[str, str, str]] = (),
        ovid_lineage_id: str | None = None,
        transform_contract: str | None = None,
        transform_version: int | None = None,
        exactness: str | None = None,
        encryption_key_ref: str | None = None,
        compression: str | None = None,
        content_encoding: str = "identity",
    ) -> tuple[str, str]:
        """Write through canonical THESEUS placement, then project into SQLite.

        The success boundary is deliberately strict:
        mathematical address -> fsynced primary -> verified replica -> address
        journal -> file-version custody -> storage-address custody -> links ->
        committed intent.  The caller never receives success for a flat-CAS
        bypass or for a placement that was merely computed as metadata.
        """
        self._tenant(tenant_id)
        data = bytes(content)
        digest = _sha(data)
        object_id = self.create_object(
            tenant_id, logical_name, file_class, semantic_owner, domain
        )
        physical = TheseusPhysicalStore(root)
        address = derive_storage_address(
            data, tenant_id=tenant_id, scope=file_class
        )
        final = physical.primary_path(address)
        intent_id = _id(
            "fi", f"{tenant_id}:{object_id}:{digest}:{uuid.uuid4().hex}".encode()
        )
        with self.store._tx() as db:
            db.execute(
                "INSERT INTO file_intents VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    tenant_id,
                    intent_id,
                    object_id,
                    None,
                    "",
                    str(final),
                    digest,
                    len(data),
                    "DECLARED",
                    _json(
                        {
                            "logical_name": logical_name,
                            "producer": producer,
                            "theseus_address_id": address.address_id,
                            "theseus_relative_path": address.relative_path,
                        }
                    ),
                    _now(),
                    _now(),
                ),
            )
        try:
            committed = physical.commit(
                data, tenant_id=tenant_id, scope=file_class
            )
            if committed != address or not physical.verify(committed, data):
                raise IntegrityFailure(
                    "THESEUS physical placement failed post-commit verification"
                )
            version_id = self.register_version(
                tenant_id,
                object_id,
                data,
                storage_uri=f"file://{final}",
                logical_path=str(final),
                producer=producer,
                producer_version=producer_version,
                schema_version=schema_version,
                evidence_state=evidence_state,
                custody_record_id=custody_record_id,
                ovid_lineage_id=ovid_lineage_id,
                transform_contract=transform_contract,
                transform_version=transform_version,
                exactness=exactness,
                encryption_key_ref=encryption_key_ref,
                compression=compression,
                content_encoding=content_encoding,
                provenance=provenance,
            )
            self.bind_storage_address(
                tenant_id,
                version_id,
                committed,
                migration_state="NATIVE_PHYLLOTAXIS",
            )
            for domain_type, domain_id, relationship in links:
                self.link(
                    tenant_id,
                    version_id,
                    domain_type,
                    domain_id,
                    relationship=relationship,
                )
            with self.store._tx() as db:
                db.execute(
                    "UPDATE file_intents SET file_version_id=?,temp_uri=?,"
                    "state='COMMITTED',updated_at=? "
                    "WHERE tenant_id=? AND intent_id=?",
                    (
                        version_id,
                        address.relative_path,
                        _now(),
                        tenant_id,
                        intent_id,
                    ),
                )
            self.append_event(
                tenant_id,
                version_id,
                "RECONCILED",
                actor=producer,
                detail={
                    "storage_uri": str(final),
                    "theseus_address_id": address.address_id,
                    "phyllotaxis_ring": address.phyllotaxis_ring,
                    "phyllotaxis_sector": address.phyllotaxis_sector,
                    "phyllotaxis_lane": address.phyllotaxis_lane,
                    "fibonacci_index": address.fibonacci_index,
                    "prime_key": address.prime_key,
                },
            )
            return object_id, version_id
        except Exception as exc:
            with self.store._tx() as db:
                db.execute(
                    "UPDATE file_intents SET state='ABANDONED_WITH_EVIDENCE',"
                    "detail_json=?,updated_at=? WHERE tenant_id=? AND intent_id=?",
                    (
                        _json(
                            {
                                "error": f"{type(exc).__name__}: {exc}",
                                "theseus_address_id": address.address_id,
                                "theseus_relative_path": address.relative_path,
                            }
                        ),
                        _now(),
                        tenant_id,
                        intent_id,
                    ),
                )
            raise

