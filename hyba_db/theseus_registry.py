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

    def reconcile_files(self, tenant_id: str, root: str | Path) -> ReconciliationReport:
        self._tenant(tenant_id)
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        resolved_root = root.resolve()
        physical = TheseusPhysicalStore(root)
        pending = self.store._db.execute(
            "SELECT intent_id FROM file_intents WHERE tenant_id=? AND state!='COMMITTED'",
            (tenant_id,),
        ).fetchall()
        expected: dict[str, str] = {}
        healthy: list[str] = []
        missing: list[str] = []
        hashes: list[str] = []
        orphans: list[str] = []
        conflicts: list[str] = []
        tenant_mismatches: list[str] = []
        custody_missing: list[str] = []
        link_missing: list[str] = []
        transform_mismatches: list[str] = []
        retention_violations: list[str] = []
        attestation_invalid: list[str] = []

        for row in self._file_rows(tenant_id):
            vid = str(row["file_version_id"])
            uri = str(row["storage_uri"])
            if not uri.startswith("file://"):
                orphans.append(vid)
                continue
            path = Path(uri[7:])
            try:
                resolved = path.resolve()
                rel = resolved.relative_to(resolved_root)
            except (OSError, ValueError):
                orphans.append(vid)
                continue
            if not rel.parts or rel.parts[0] != tenant_id:
                tenant_mismatches.append(vid)
                continue
            try:
                address = self.storage_address(tenant_id, vid)
                canonical = physical.primary_path(address).resolve()
            except Exception:
                conflicts.append(vid)
                continue
            expected[str(canonical)] = vid
            if resolved != canonical or address.content_sha256 != row["content_sha256"]:
                conflicts.append(vid)
                continue
            if not path.is_file():
                missing.append(vid)
                continue
            try:
                data = path.read_bytes()
            except OSError:
                missing.append(vid)
                continue
            if len(data) != row["size_bytes"] or _sha(data) != row["content_sha256"]:
                hashes.append(vid)
                continue
            if not verify_storage_address(address, data) or not physical.verify(address, data):
                conflicts.append(vid)
                continue
            if row["status"] in {"MISSING", "QUARANTINED"}:
                conflicts.append(vid)
                continue
            cid = str(row["custody_record_id"] or "")
            if not cid or self.custody is None or not self.custody.verify(tenant_id, cid):
                custody_missing.append(vid)
                continue
            try:
                if not self.store.verify_attestation(tenant_id, str(row["attestation_id"])):
                    raise IntegrityFailure("invalid attestation")
            except Exception:
                attestation_invalid.append(vid)
                continue
            if not self.store._db.execute(
                "SELECT 1 FROM file_links WHERE tenant_id=? AND file_version_id=?",
                (tenant_id, vid),
            ).fetchone():
                link_missing.append(vid)
                continue
            if (row["ovid_lineage_id"] is None) != (row["transform_contract"] is None):
                transform_mismatches.append(vid)
                continue
            if row["status"] == "RETIRED" and not self.store._db.execute(
                "SELECT 1 FROM file_events WHERE tenant_id=? AND file_version_id=? "
                "AND event_type IN ('RETENTION_APPLIED','DELETED_BY_POLICY')",
                (tenant_id, vid),
            ).fetchone():
                retention_violations.append(vid)
                continue
            healthy.append(vid)

        for obj in self.store._db.execute(
            "SELECT * FROM file_objects WHERE tenant_id=?", (tenant_id,)
        ):
            versions = self.store._db.execute(
                "SELECT file_version_id FROM file_versions WHERE tenant_id=? "
                "AND file_object_id=? ORDER BY version",
                (tenant_id, obj["file_object_id"]),
            ).fetchall()
            if versions and obj["current_version_id"] != versions[-1][0]:
                conflicts.append(str(obj["file_object_id"]))

        primary_root = root / tenant_id / "theseus"
        actual = (
            {str(p.resolve()) for p in primary_root.rglob("*.blk") if p.is_file()}
            if primary_root.exists()
            else set()
        )
        orphan_files = sorted(actual - set(expected))
        unresolved = (
            missing + hashes + orphans + conflicts + tenant_mismatches
            + custody_missing + link_missing + transform_mismatches
            + retention_violations + attestation_invalid + orphan_files
            + [f"intent:{r['intent_id']}" for r in pending]
        )
        return ReconciliationReport(
            tenant_id=tenant_id,
            root=str(root),
            healthy=tuple(sorted(healthy)),
            orphan_files=tuple(orphan_files),
            orphan_records=tuple(sorted(orphans)),
            missing_blobs=tuple(sorted(missing)),
            hash_mismatches=tuple(sorted(hashes)),
            version_conflicts=tuple(sorted(set(conflicts))),
            tenant_mismatches=tuple(sorted(tenant_mismatches)),
            custody_missing=tuple(sorted(custody_missing)),
            domain_link_missing=tuple(sorted(link_missing)),
            transform_mismatches=tuple(sorted(transform_mismatches)),
            retention_violations=tuple(sorted(retention_violations)),
            attestation_invalid=tuple(sorted(attestation_invalid)),
            unresolved=tuple(sorted(set(unresolved))),
            generated_at=_now(),
        )

    def recover_blob_from_custody(
        self, tenant_id: str, file_version_id: str, root: str | Path
    ) -> dict[str, Any]:
        self._tenant(tenant_id)
        if self.custody is None:
            raise InvalidRecord("THESEUS custody required")
        row = self.store._db.execute(
            "SELECT fv.*,fo.file_class FROM file_versions fv JOIN file_objects fo "
            "ON fo.tenant_id=fv.tenant_id AND fo.file_object_id=fv.file_object_id "
            "WHERE fv.tenant_id=? AND fv.file_version_id=?",
            (tenant_id, file_version_id),
        ).fetchone()
        if row is None:
            raise AccessDenied("file version not found")
        op = self.custody.open_tenant(tenant_id).get_record(str(row["custody_record_id"]))
        data = bytes(op.payload)
        if (
            _sha(data) != row["content_sha256"]
            or len(data) != row["size_bytes"]
            or op.content_digest != row["content_sha256"]
            or op.producer != row["producer"]
            or op.kind != "file_version"
        ):
            raise IntegrityFailure("THESEUS recovery content binding mismatch")
        address = self.storage_address(tenant_id, file_version_id)
        expected = derive_storage_address(
            data, tenant_id=tenant_id, scope=str(row["file_class"])
        )
        if expected != address:
            raise IntegrityFailure("mathematical address mismatch")
        physical = TheseusPhysicalStore(root)
        already = physical.verify(address, data)
        committed = physical.commit(
            data, tenant_id=tenant_id, scope=str(row["file_class"])
        )
        if committed != address or not physical.verify(address, data):
            raise IntegrityFailure("THESEUS recovery verification failed")
        final = physical.primary_path(address)
        with self.store._tx() as db:
            db.execute(
                "UPDATE file_versions SET storage_uri=?,logical_path=?,status='ACTIVE' "
                "WHERE tenant_id=? AND file_version_id=?",
                (f"file://{final}", str(final), tenant_id, file_version_id),
            )
            self._event(
                db, tenant_id, file_version_id, "RECOVERED", "theseus",
                {"address_id": address.address_id, "already_healthy": already},
            )
        return {
            "schema": "hyba.file-blob-recovery/v2",
            "tenant_id": tenant_id,
            "file_version_id": file_version_id,
            "content_sha256": address.content_sha256,
            "address_id": address.address_id,
            "storage_uri": f"file://{final}",
            "recovered": not already,
            "passed": True,
        }

    def recover_blobs_from_custody(
        self, tenant_id: str, root: str | Path, *, only_unhealthy: bool = True
    ) -> dict[str, Any]:
        self._tenant(tenant_id)
        physical = TheseusPhysicalStore(root)
        recovered: list[str] = []
        healthy: list[str] = []
        errors: list[str] = []
        rows = self.store._db.execute(
            "SELECT file_version_id FROM file_versions WHERE tenant_id=?", (tenant_id,)
        ).fetchall()
        for row in rows:
            vid = str(row[0])
            try:
                address = self.storage_address(tenant_id, vid)
                if only_unhealthy and physical.verify(address):
                    healthy.append(vid)
                    continue
                result = self.recover_blob_from_custody(tenant_id, vid, root)
                (recovered if result["recovered"] else healthy).append(vid)
            except Exception as exc:
                errors.append(f"{vid}:{type(exc).__name__}:{exc}")
        return {
            "schema": "hyba.file-blob-recovery-batch/v2",
            "tenant_id": tenant_id,
            "recovered": tuple(recovered),
            "healthy": tuple(healthy),
            "errors": tuple(errors),
            "passed": not errors,
        }

    def migrate_legacy_storage(
        self, tenant_id: str, root: str | Path
    ) -> dict[str, Any]:
        self._tenant(tenant_id)
        physical = TheseusPhysicalStore(root)
        migrated: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []
        rows = self.store._db.execute(
            "SELECT fv.*,fo.file_class FROM file_versions fv JOIN file_objects fo "
            "ON fo.tenant_id=fv.tenant_id AND fo.file_object_id=fv.file_object_id "
            "WHERE fv.tenant_id=?",
            (tenant_id,),
        ).fetchall()
        for row in rows:
            vid = str(row["file_version_id"])
            bound = self.store._db.execute(
                "SELECT 1 FROM theseus_storage_addresses WHERE tenant_id=? "
                "AND file_version_id=?",
                (tenant_id, vid),
            ).fetchone()
            if bound:
                try:
                    address = self.storage_address(tenant_id, vid)
                    if physical.verify(address):
                        final = physical.primary_path(address)
                        if row["storage_uri"] != f"file://{final}":
                            with self.store._tx() as db:
                                db.execute(
                                    "UPDATE file_versions SET storage_uri=?,logical_path=? "
                                    "WHERE tenant_id=? AND file_version_id=?",
                                    (f"file://{final}", str(final), tenant_id, vid),
                                )
                        skipped.append(vid)
                        continue
                except Exception as exc:
                    errors.append(f"{vid}:{type(exc).__name__}:{exc}")
                    continue

            uri = str(row["storage_uri"])
            if not uri.startswith("file://"):
                errors.append(f"{vid}:non-file legacy URI")
                continue
            legacy = Path(uri[7:])
            try:
                data = legacy.read_bytes()
            except OSError as exc:
                errors.append(f"{vid}:legacy unreadable:{exc}")
                continue
            if len(data) != row["size_bytes"] or _sha(data) != row["content_sha256"]:
                errors.append(f"{vid}:legacy digest/size mismatch")
                continue
            try:
                address = physical.commit(
                    data, tenant_id=tenant_id, scope=str(row["file_class"])
                )
                if not physical.verify(address, data):
                    raise IntegrityFailure("new placement readback failed")
                self.bind_storage_address(
                    tenant_id,
                    vid,
                    address,
                    migration_state="MIGRATED_LEGACY_CAS",
                )
                final = physical.primary_path(address)
                with self.store._tx() as db:
                    db.execute(
                        "UPDATE file_versions SET storage_uri=?,logical_path=? "
                        "WHERE tenant_id=? AND file_version_id=?",
                        (f"file://{final}", str(final), tenant_id, vid),
                    )
                    self._event(
                        db,
                        tenant_id,
                        vid,
                        "MOVED",
                        "theseus",
                        {
                            "legacy_uri": uri,
                            "legacy_retained": True,
                            "address_id": address.address_id,
                            "migration": "MIGRATED_LEGACY_CAS",
                        },
                    )
                migrated.append(vid)
            except Exception as exc:
                errors.append(f"{vid}:{type(exc).__name__}:{exc}")
        seal = (
            self.seal_existing_rebuild_state(tenant_id)
            if not errors
            else {"passed": False, "reason": "migration errors"}
        )
        return {
            "schema": "hyba.theseus-storage-migration/v1",
            "tenant_id": tenant_id,
            "migrated": tuple(migrated),
            "skipped": tuple(skipped),
            "errors": tuple(errors),
            "rebuild_manifest_seal": seal,
            "passed": not errors and bool(seal.get("passed")),
        }

    def storage_proof(
        self, tenant_id: str, file_version_id: str, root: str | Path
    ) -> dict[str, Any]:
        row = self.store._db.execute(
            "SELECT fv.custody_record_id,tsa.custody_record_id AS address_custody_id "
            "FROM file_versions fv JOIN theseus_storage_addresses tsa "
            "ON tsa.tenant_id=fv.tenant_id AND tsa.file_version_id=fv.file_version_id "
            "WHERE fv.tenant_id=? AND fv.file_version_id=?",
            (tenant_id, file_version_id),
        ).fetchone()
        if row is None:
            raise AccessDenied("file/address binding not found")
        address = self.storage_address(tenant_id, file_version_id)
        physical = TheseusPhysicalStore(root)
        data = physical.read(address, heal=False)
        return {
            "schema": "hyba.theseus-storage-proof/v1",
            "file_version_id": file_version_id,
            "content_sha256": address.content_sha256,
            "readback_sha256": _sha(data),
            "fibonacci_index": address.fibonacci_index,
            "fibonacci_value": address.fibonacci_value,
            "cassini_witness": list(address.cassini_quadruple),
            "prime_key": address.prime_key,
            "anchor": address.anchor,
            "phyllotaxis": {
                "index": address.phyllotaxis_index,
                "ring": address.phyllotaxis_ring,
                "sector": address.phyllotaxis_sector,
                "lane": address.phyllotaxis_lane,
                "radius": address.phyllotaxis_radius,
                "theta": address.phyllotaxis_theta,
            },
            "relative_path": address.relative_path,
            "actual_path": str(physical.primary_path(address)),
            "custody_record_id": row["custody_record_id"],
            "address_custody_record_id": row["address_custody_id"],
            "placement_verified": physical.verify(address, data),
        }


    def _seal_mining_manifest(self, tenant_id: str, record_id: str) -> str:
        if self.custody is None:
            raise InvalidRecord("THESEUS custody required for mining rebuild manifest")
        row = self.store._db.execute(
            "SELECT * FROM mining_lifecycle WHERE tenant_id=? AND record_id=?",
            (tenant_id, record_id),
        ).fetchone()
        if row is None:
            raise AccessDenied("mining record not found")
        body = {
            "schema": "hyba.mining-projection-manifest/v1",
            "record_id": str(row["record_id"]),
            "kind": str(row["kind"]),
            "payload": json.loads(row["payload_json"]),
            "content_sha256": str(row["content_sha256"]),
            "evidence_state": str(row["evidence_state"]),
            "parent_ids": json.loads(row["parent_ids_json"]),
            "created_at": str(row["created_at"]),
            "producer": str(row["producer"]),
            "custody_record_id": str(row["custody_record_id"]),
        }
        op = OperationalRecord(
            record_id=f"mining_projection.{record_id}",
            producer="theseus",
            producer_version="hyba-db-projection/1",
            schema_version=1,
            kind="mining_projection_manifest",
            payload=_json(body).encode(),
            evidence_state="MEASURED",
            lineage=(record_id, *tuple(str(x) for x in body["parent_ids"])),
            correlation_ids={"tenant_id": tenant_id, "mining_record_id": record_id},
        )
        cid = self.custody.put_record(tenant_id, op)
        if not self.custody.verify(tenant_id, cid):
            raise IntegrityFailure("mining projection manifest custody failed")
        return str(cid)

    def record_mining(self, *args: Any, **kwargs: Any) -> str:
        record_id = super().record_mining(*args, **kwargs)
        tenant_id = str(args[0] if args else kwargs["tenant_id"])
        self._seal_mining_manifest(tenant_id, record_id)
        return record_id

    def seal_existing_rebuild_state(self, tenant_id: str) -> dict[str, Any]:
        """Backfill rebuild manifests without changing historical identities."""
        self._tenant(tenant_id)
        if self.custody is None:
            raise InvalidRecord("THESEUS custody required for rebuild sealing")
        file_ids: list[str] = []
        for row in self.store._db.execute(
            "SELECT fv.*,fp.provenance_json FROM file_versions fv "
            "JOIN file_provenance fp ON fp.tenant_id=fv.tenant_id "
            "AND fp.file_version_id=fv.file_version_id "
            "WHERE fv.tenant_id=? ORDER BY fv.created_at,fv.file_version_id",
            (tenant_id,),
        ).fetchall():
            op = self.custody.open_tenant(tenant_id).get_record(
                str(row["custody_record_id"])
            )
            rebuilt = self.register_version(
                tenant_id,
                str(row["file_object_id"]),
                bytes(op.payload),
                storage_uri=str(row["storage_uri"]),
                logical_path=str(row["logical_path"]),
                producer=str(row["producer"]),
                producer_version=str(row["producer_version"]),
                schema_version=int(row["schema_version"]),
                evidence_state=str(row["evidence_state"]),
                custody_record_id=str(row["custody_record_id"]),
                previous_version_id=row["previous_version_id"],
                ovid_lineage_id=row["ovid_lineage_id"],
                transform_contract=row["transform_contract"],
                transform_version=row["transform_version"],
                exactness=row["exactness"],
                encryption_key_ref=row["encryption_key_ref"],
                compression=row["compression"],
                content_encoding=str(row["content_encoding"]),
                provenance=json.loads(str(row["provenance_json"])),
                actor="theseus-manifest-seal",
            )
            if rebuilt != row["file_version_id"]:
                raise IntegrityFailure("file identity changed while sealing rebuild state")
            file_ids.append(str(rebuilt))

        link_ids: list[str] = []
        for row in self.store._db.execute(
            "SELECT * FROM file_links WHERE tenant_id=? ORDER BY link_id", (tenant_id,)
        ).fetchall():
            link_id = self.link(
                tenant_id,
                str(row["file_version_id"]),
                str(row["domain_type"]),
                str(row["domain_id"]),
                relationship=str(row["relationship"]),
            )
            if link_id != row["link_id"]:
                raise IntegrityFailure("link identity changed while sealing rebuild state")
            link_ids.append(str(link_id))

        mining_ids: list[str] = []
        for row in self.store._db.execute(
            "SELECT record_id FROM mining_lifecycle WHERE tenant_id=? ORDER BY record_id",
            (tenant_id,),
        ).fetchall():
            rid = str(row["record_id"])
            self._seal_mining_manifest(tenant_id, rid)
            mining_ids.append(rid)
        return {
            "schema": "hyba.rebuild-manifest-seal/v1",
            "tenant_id": tenant_id,
            "file_versions": tuple(file_ids),
            "links": tuple(link_ids),
            "mining_records": tuple(mining_ids),
            "passed": True,
        }


__all__ = ["TheseusFileRegistry"]
