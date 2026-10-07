"""Production THESEUS-backed file-registry behaviour."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aethel.enterprise.records import OperationalRecord
from aethel.storage_topology import (
    TheseusPhysicalStore,
    derive_storage_address,
    verify_storage_address,
)
from .file_registry import FileRegistry, ReconciliationReport, _json, _now, _sha
from .models import AccessDenied, IntegrityFailure, InvalidRecord


class TheseusFileRegistry(FileRegistry):
    """File projection whose byte authority is mathematical THESEUS storage."""

    def register_version(self, *args: Any, **kwargs: Any) -> str:
        vid = super().register_version(*args, **kwargs)
        tenant_id = str(args[0] if args else kwargs["tenant_id"])
        row = self.store._db.execute(
            "SELECT fv.*,fo.logical_name,fo.file_class,fo.semantic_owner,fo.domain,"
            "fo.mime_type,fo.retention_policy,fo.created_at AS object_created_at,"
            "fo.created_by,fp.provenance_json FROM file_versions fv "
            "JOIN file_objects fo ON fo.tenant_id=fv.tenant_id "
            "AND fo.file_object_id=fv.file_object_id "
            "JOIN file_provenance fp ON fp.tenant_id=fv.tenant_id "
            "AND fp.file_version_id=fv.file_version_id "
            "WHERE fv.tenant_id=? AND fv.file_version_id=?",
            (tenant_id, vid),
        ).fetchone()
        if row is None or self.custody is None:
            raise IntegrityFailure("file projection cannot be durably manifested")
        tenant = self.store._tenant(tenant_id)
        body = {
            "schema": "hyba.file-projection-manifest/v1",
            "tenant": {
                "tenant_id": tenant_id,
                "namespace": tenant["namespace"],
                "max_records": tenant["max_records"],
                "max_blob_bytes": tenant["max_blob_bytes"],
                "created_at": tenant["created_at"],
            },
            "object": {
                "file_object_id": row["file_object_id"],
                "logical_name": row["logical_name"],
                "file_class": row["file_class"],
                "semantic_owner": row["semantic_owner"],
                "domain": row["domain"],
                "mime_type": row["mime_type"],
                "retention_policy": row["retention_policy"],
                "created_at": row["object_created_at"],
                "created_by": row["created_by"],
            },
            "version": {
                key: row[key]
                for key in (
                    "file_version_id", "version", "content_sha256", "size_bytes",
                    "created_at", "producer", "producer_version", "schema_version",
                    "evidence_state", "custody_record_id", "previous_version_id",
                    "ovid_lineage_id", "transform_contract", "transform_version",
                    "exactness", "encryption_key_ref", "compression",
                    "content_encoding", "status",
                )
            },
            "provenance": json.loads(row["provenance_json"]),
        }
        op = OperationalRecord(
            record_id=f"file_projection.{vid}",
            producer="theseus",
            producer_version="hyba-db-projection/1",
            schema_version=1,
            kind="file_projection_manifest",
            payload=_json(body).encode(),
            evidence_state="MEASURED",
            lineage=(vid, str(row["custody_record_id"])),
            correlation_ids={"tenant_id": tenant_id, "file_version_id": vid},
        )
        cid = self.custody.put_record(tenant_id, op)
        if not self.custody.verify(tenant_id, cid):
            raise IntegrityFailure("projection manifest custody failed")
        return vid

    def link(
        self,
        tenant_id: str,
        file_version_id: str,
        domain_type: str,
        domain_id: str,
        *,
        relationship: str = "describes",
    ) -> str:
        lid = super().link(
            tenant_id, file_version_id, domain_type, domain_id,
            relationship=relationship,
        )
        if self.custody is None:
            raise InvalidRecord("THESEUS custody required for durable links")
        body = {
            "schema": "hyba.file-projection-link/v1",
            "link_id": lid,
            "file_version_id": file_version_id,
            "domain_type": domain_type,
            "domain_id": domain_id,
            "relationship": relationship,
        }
        op = OperationalRecord(
            record_id=f"file_projection_link.{lid}",
            producer="theseus",
            producer_version="hyba-db-projection/1",
            schema_version=1,
            kind="file_projection_link",
            payload=_json(body).encode(),
            evidence_state="MEASURED",
            lineage=(file_version_id, domain_id),
            correlation_ids={"tenant_id": tenant_id, "file_version_id": file_version_id},
        )
        cid = self.custody.put_record(tenant_id, op)
        if not self.custody.verify(tenant_id, cid):
            raise IntegrityFailure("file-link custody failed")
        return lid
