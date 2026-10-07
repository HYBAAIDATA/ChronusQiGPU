"""Deterministic rebuild of the HYBA query projection from THESEUS."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aethel.storage_topology import TheseusPhysicalStore, TheseusStorageAddress
from .file_registry import FileRegistry, _json, _sha
from .models import IntegrityFailure, InvalidRecord


def _bootstrap_tenant(store: Any, tenant_id: str, manifest: dict[str, Any]) -> None:
    if store._db.execute(
        "SELECT 1 FROM tenants WHERE tenant_id=?", (tenant_id,)
    ).fetchone():
        return
    tenant = dict(manifest["tenant"])
    if str(tenant["tenant_id"]) != tenant_id:
        raise IntegrityFailure("projection manifest tenant mismatch")
    with store._tx() as db:
        db.execute(
            "INSERT INTO tenants(tenant_id,namespace,max_records,max_blob_bytes,"
            "used_records,used_blob_bytes,created_at) VALUES(?,?,?,?,0,0,?)",
            (
                tenant_id,
                str(tenant["namespace"]),
                int(tenant["max_records"]),
                int(tenant["max_blob_bytes"]),
                str(tenant["created_at"]),
            ),
        )
        root = store._attest(
            db,
            tenant_id,
            f"tenant:{tenant['namespace']}",
            "theseus-rebuild",
            {"event": "projection_rebuild_from_custody"},
            (),
            root=True,
        )
        db.execute(
            "UPDATE tenants SET root_attestation_id=? WHERE tenant_id=?",
            (root.id, tenant_id),
        )


def restore_projection_from_custody(
    store: Any, tenant_id: str, root: str | Path
) -> dict[str, Any]:
    """Restore a fresh SQLite projection using only THESEUS-authoritative state."""
    registry = store.files
    if registry.custody is None:
        raise InvalidRecord("THESEUS custody required for database rebuild")
    custody = registry.custody.open_tenant(tenant_id)
    manifests: list[tuple[Any, dict[str, Any]]] = []
    links: list[dict[str, Any]] = []
    mining_manifests: list[dict[str, Any]] = []
    addresses: dict[str, tuple[Any, TheseusStorageAddress]] = {}

    for item in custody.list_records():
        op = custody.get_record(str(item["record_id"]))
        if op.kind == "file_projection_manifest":
            body = json.loads(op.payload.decode("utf-8"))
            if body.get("schema") != "hyba.file-projection-manifest/v1":
                raise IntegrityFailure("unsupported file projection manifest")
            manifests.append((op, body))
        elif op.kind == "file_projection_link":
            body = json.loads(op.payload.decode("utf-8"))
            if body.get("schema") != "hyba.file-projection-link/v1":
                raise IntegrityFailure("unsupported file-link manifest")
            links.append(body)
        elif op.kind == "mining_projection_manifest":
            body = json.loads(op.payload.decode("utf-8"))
            if body.get("schema") != "hyba.mining-projection-manifest/v1":
                raise IntegrityFailure("unsupported mining manifest")
            mining_manifests.append(body)
        elif op.kind == "theseus_storage_address":
            body = json.loads(op.payload.decode("utf-8"))
            address = TheseusStorageAddress.from_dict(body)
            vid = str(op.correlation_ids.get("file_version_id", ""))
            if not vid:
                raise IntegrityFailure("storage address lacks file-version correlation")
            addresses[vid] = (op, address)

    if not manifests:
        raise IntegrityFailure("no file projection manifests in THESEUS custody")
    _bootstrap_tenant(store, tenant_id, manifests[0][1])
    physical = TheseusPhysicalStore(root)
    restored_versions: list[str] = []

    manifests.sort(
        key=lambda item: (
            str(item[1]["object"]["file_object_id"]),
            int(item[1]["version"]["version"]),
        )
    )
    for _op, body in manifests:
        obj = dict(body["object"])
        ver = dict(body["version"])
        object_id = str(obj["file_object_id"])
        version_id = str(ver["file_version_id"])

        if not store._db.execute(
            "SELECT 1 FROM file_objects WHERE tenant_id=? AND file_object_id=?",
            (tenant_id, object_id),
        ).fetchone():
            with store._tx() as db:
                att = store._attest(
                    db,
                    tenant_id,
                    f"file_object:{object_id}",
                    "theseus-rebuild",
                    {
                        "logical_name": obj["logical_name"],
                        "file_class": obj["file_class"],
                        "owner": obj["semantic_owner"],
                    },
                    (),
                )
                db.execute(
                    "INSERT INTO file_objects VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        tenant_id,
                        object_id,
                        str(obj["logical_name"]),
                        str(obj["file_class"]),
                        str(obj["semantic_owner"]),
                        str(obj["domain"]),
                        str(obj["mime_type"]),
                        str(obj["retention_policy"]),
                        str(obj["created_at"]),
                        str(obj["created_by"]),
                        None,
                        "ACTIVE",
                        att.id,
                    ),
                )

        original = custody.get_record(str(ver["custody_record_id"]))
        payload = bytes(original.payload)
        pair = addresses.get(version_id)
        if pair is None:
            raise IntegrityFailure(f"missing mathematical address for {version_id}")
        address_op, address = pair
        if address.content_sha256 != _sha(payload):
            raise IntegrityFailure(f"address digest mismatch for {version_id}")
        if not physical.verify(address, payload):
            raise IntegrityFailure(f"physical block unavailable for {version_id}")
        final = physical.primary_path(address)

        rebuilt = FileRegistry.register_version(
            registry,
            tenant_id,
            object_id,
            payload,
            storage_uri=f"file://{final}",
            logical_path=str(final),
            producer=str(ver["producer"]),
            producer_version=str(ver["producer_version"]),
            schema_version=int(ver["schema_version"]),
            evidence_state=str(ver["evidence_state"]),
            custody_record_id=str(ver["custody_record_id"]),
            previous_version_id=ver.get("previous_version_id"),
            ovid_lineage_id=ver.get("ovid_lineage_id"),
            transform_contract=ver.get("transform_contract"),
            transform_version=ver.get("transform_version"),
            exactness=ver.get("exactness"),
            encryption_key_ref=ver.get("encryption_key_ref"),
            compression=ver.get("compression"),
            content_encoding=str(ver["content_encoding"]),
            provenance=dict(body.get("provenance") or {}),
            actor="theseus-rebuild",
        )
        if rebuilt != version_id:
            raise IntegrityFailure(
                f"rebuilt file identity changed: {version_id} -> {rebuilt}"
            )
        with store._tx() as db:
            db.execute(
                "UPDATE file_versions SET created_at=?,status=? "
                "WHERE tenant_id=? AND file_version_id=?",
                (str(ver["created_at"]), str(ver["status"]), tenant_id, version_id),
            )
            address_json = _json(address.to_dict())
            address_sha = _sha(address_json.encode())
            att = store._attest(
                db,
                tenant_id,
                f"theseus_storage_address:{version_id}",
                "theseus-rebuild",
                {
                    "file_version_id": version_id,
                    "address_id": address.address_id,
                    "address_sha256": address_sha,
                    "custody_record_id": address_op.record_id,
                },
                (),
            )
            db.execute(
                "INSERT INTO theseus_storage_addresses VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    tenant_id,
                    version_id,
                    address.address_id,
                    address_json,
                    address_sha,
                    address_op.record_id,
                    str(address_op.meta.get("migration_state", "REBUILT")),
                    att.id,
                    str(ver["created_at"]),
                ),
            )
        restored_versions.append(version_id)

    restored_mining: list[str] = []
    pending = list(mining_manifests)
    while pending:
        progressed = False
        for body in list(pending):
            record_id = str(body["record_id"])
            parents = tuple(str(x) for x in body.get("parent_ids") or ())
            if any(
                not store._db.execute(
                    "SELECT 1 FROM mining_lifecycle WHERE tenant_id=? AND record_id=?",
                    (tenant_id, parent),
                ).fetchone()
                for parent in parents
            ):
                continue
            custody_id = str(body["custody_record_id"])
            if not registry.custody.verify(tenant_id, custody_id):
                raise IntegrityFailure(f"mining custody unavailable: {record_id}")
            payload = dict(body["payload"])
            payload_json = _json(payload)
            if _sha(payload_json.encode()) != str(body["content_sha256"]):
                raise IntegrityFailure(f"mining manifest digest mismatch: {record_id}")
            with store._tx() as db:
                db.execute(
                    "INSERT OR IGNORE INTO mining_lifecycle VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        tenant_id,
                        record_id,
                        str(body["kind"]),
                        payload_json,
                        str(body["content_sha256"]),
                        str(body["evidence_state"]),
                        _json(parents),
                        str(body["created_at"]),
                        str(body["producer"]),
                        custody_id,
                    ),
                )
            restored_mining.append(record_id)
            pending.remove(body)
            progressed = True
        if not progressed:
            raise IntegrityFailure("mining custody graph cannot be topologically rebuilt")

    restored_links: list[str] = []
    for body in links:
        link_id = FileRegistry.link(
            registry,
            tenant_id,
            str(body["file_version_id"]),
            str(body["domain_type"]),
            str(body["domain_id"]),
            relationship=str(body["relationship"]),
        )
        if link_id != str(body["link_id"]):
            raise IntegrityFailure("rebuilt file-link identity changed")
        restored_links.append(link_id)

    knowledge = store.knowledge.restore_from_custody(tenant_id)
    return {
        "schema": "hyba.database-rebuild/v1",
        "tenant_id": tenant_id,
        "file_versions": tuple(restored_versions),
        "file_links": tuple(restored_links),
        "mining_records": tuple(restored_mining),
        "knowledge": knowledge,
        "passed": True,
    }


def projection_fingerprint(store: Any, tenant_id: str) -> dict[str, Any]:
    """Canonical comparison surface for destructive rebuild acceptance tests."""
    store._tenant(tenant_id)
    q = store._db.execute
    objects = tuple(
        tuple(row)
        for row in q(
            "SELECT file_object_id,logical_name,file_class,semantic_owner,domain,"
            "current_version_id,status FROM file_objects WHERE tenant_id=? "
            "ORDER BY file_object_id",
            (tenant_id,),
        ).fetchall()
    )
    versions = tuple(
        tuple(row)
        for row in q(
            "SELECT file_version_id,file_object_id,version,content_sha256,"
            "previous_version_id,ovid_lineage_id,transform_contract,"
            "transform_version,exactness,status FROM file_versions "
            "WHERE tenant_id=? ORDER BY file_object_id,version",
            (tenant_id,),
        ).fetchall()
    )
    addresses = tuple(
        tuple(row)
        for row in q(
            "SELECT file_version_id,address_id,address_sha256 FROM "
            "theseus_storage_addresses WHERE tenant_id=? ORDER BY file_version_id",
            (tenant_id,),
        ).fetchall()
    )
    links = tuple(
        tuple(row)
        for row in q(
            "SELECT link_id,file_version_id,domain_type,domain_id,relationship "
            "FROM file_links WHERE tenant_id=? ORDER BY link_id",
            (tenant_id,),
        ).fetchall()
    )
    mining = tuple(
        tuple(row)
        for row in q(
            "SELECT record_id,kind,content_sha256,evidence_state,parent_ids_json,"
            "producer,custody_record_id FROM mining_lifecycle WHERE tenant_id=? "
            "ORDER BY record_id",
            (tenant_id,),
        ).fetchall()
    )
    knowledge = tuple(
        tuple(row)
        for row in q(
            "SELECT knowledge_id,subject,predicate,domain,knowledge_kind,"
            "knowledge_form,semantic_owner,evidence_state,content_sha256,"
            "supersedes_id,custody_record_id FROM knowledge_records "
            "WHERE tenant_id=? ORDER BY knowledge_id",
            (tenant_id,),
        ).fetchall()
    )
    relations = tuple(
        tuple(row)
        for row in q(
            "SELECT relation_id,from_knowledge_id,to_knowledge_id,relation_type,"
            "producer,custody_record_id FROM knowledge_relations WHERE tenant_id=? "
            "ORDER BY relation_id",
            (tenant_id,),
        ).fetchall()
    )
    return {
        "objects": objects,
        "versions": versions,
        "addresses": addresses,
        "links": links,
        "mining": mining,
        "knowledge": knowledge,
        "relations": relations,
    }


__all__ = ["projection_fingerprint", "restore_projection_from_custody"]
