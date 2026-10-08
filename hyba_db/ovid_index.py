"""OVID tenant-scoped data-organisation index over HYBA projections.

OVID owns data organisation and indexing; THESEUS remains durable custody.
This module never duplicates authoritative bytes.  It exposes deterministic
tenant-scoped views over the rebuildable SQLite projection and verifies that
the indexes required by production query paths are present.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class OvidIndexEntry:
    entity_kind: str
    entity_id: str
    semantic_owner: str
    domain: str
    evidence_state: str
    content_sha256: str
    storage_address_id: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OvidDataIndex:
    """Deterministic query/index organisation over THESEUS-backed projections."""

    REQUIRED_INDEXES = frozenset(
        {
            "idx_file_objects_owner_domain",
            "idx_file_versions_sha",
            "idx_file_versions_status",
            "idx_mining_kind_state",
            "idx_knowledge_subject",
            "idx_knowledge_owner",
            "idx_knowledge_domain_form",
            "idx_knowledge_supersedes",
            "idx_knowledge_rel_from",
        }
    )

    def __init__(self, store: Any) -> None:
        self.store = store

    def _tenant(self, tenant_id: str) -> None:
        self.store._tenant(tenant_id)

    def files(
        self,
        tenant_id: str,
        *,
        domain: str | None = None,
        semantic_owner: str | None = None,
    ) -> tuple[OvidIndexEntry, ...]:
        self._tenant(tenant_id)
        clauses = ["fv.tenant_id=?"]
        args: list[Any] = [tenant_id]
        if domain is not None:
            clauses.append("fo.domain=?")
            args.append(str(domain))
        if semantic_owner is not None:
            clauses.append("fo.semantic_owner=?")
            args.append(str(semantic_owner))
        rows = self.store._db.execute(
            "SELECT fv.file_version_id,fo.semantic_owner,fo.domain,"
            "fv.evidence_state,fv.content_sha256,tsa.address_id,fv.created_at "
            "FROM file_versions fv JOIN file_objects fo "
            "ON fo.tenant_id=fv.tenant_id AND fo.file_object_id=fv.file_object_id "
            "LEFT JOIN theseus_storage_addresses tsa "
            "ON tsa.tenant_id=fv.tenant_id AND tsa.file_version_id=fv.file_version_id "
            "WHERE " + " AND ".join(clauses) + " ORDER BY fv.file_version_id",
            tuple(args),
        ).fetchall()
        return tuple(
            OvidIndexEntry(
                "file_version",
                str(row["file_version_id"]),
                str(row["semantic_owner"]),
                str(row["domain"]),
                str(row["evidence_state"]),
                str(row["content_sha256"]),
                str(row["address_id"]) if row["address_id"] is not None else None,
                str(row["created_at"]),
            )
            for row in rows
        )

    def knowledge(
        self,
        tenant_id: str,
        *,
        domain: str | None = None,
        semantic_owner: str | None = None,
    ) -> tuple[OvidIndexEntry, ...]:
        self._tenant(tenant_id)
        clauses = ["tenant_id=?"]
        args: list[Any] = [tenant_id]
        if domain is not None:
            clauses.append("domain=?")
            args.append(str(domain).lower())
        if semantic_owner is not None:
            clauses.append("semantic_owner=?")
            args.append(str(semantic_owner))
        rows = self.store._db.execute(
            "SELECT knowledge_id,semantic_owner,domain,evidence_state,"
            "content_sha256,created_at FROM knowledge_records WHERE "
            + " AND ".join(clauses)
            + " ORDER BY knowledge_id",
            tuple(args),
        ).fetchall()
        return tuple(
            OvidIndexEntry(
                "knowledge",
                str(row["knowledge_id"]),
                str(row["semantic_owner"]),
                str(row["domain"]),
                str(row["evidence_state"]),
                str(row["content_sha256"]),
                None,
                str(row["created_at"]),
            )
            for row in rows
        )

    def mining(
        self,
        tenant_id: str,
        *,
        kind: str | None = None,
        producer: str | None = None,
    ) -> tuple[OvidIndexEntry, ...]:
        self._tenant(tenant_id)
        clauses = ["tenant_id=?"]
        args: list[Any] = [tenant_id]
        if kind is not None:
            clauses.append("kind=?")
            args.append(str(kind))
        if producer is not None:
            clauses.append("producer=?")
            args.append(str(producer).lower())
        rows = self.store._db.execute(
            "SELECT record_id,kind,producer,evidence_state,content_sha256,created_at "
            "FROM mining_lifecycle WHERE "
            + " AND ".join(clauses)
            + " ORDER BY record_id",
            tuple(args),
        ).fetchall()
        return tuple(
            OvidIndexEntry(
                "mining_record",
                str(row["record_id"]),
                str(row["producer"]),
                f"mining:{row['kind']}",
                str(row["evidence_state"]),
                str(row["content_sha256"]),
                None,
                str(row["created_at"]),
            )
            for row in rows
        )

    def organisation_digest(self, tenant_id: str) -> str:
        """Digest the complete ordered OVID organisation view for replay checks."""
        doc = {
            "schema": "hyba.ovid-data-index/v1",
            "tenant_id": tenant_id,
            "files": [entry.to_dict() for entry in self.files(tenant_id)],
            "knowledge": [entry.to_dict() for entry in self.knowledge(tenant_id)],
            "mining": [entry.to_dict() for entry in self.mining(tenant_id)],
        }
        return hashlib.sha256(_canonical(doc).encode("utf-8")).hexdigest()

    def verify(self, tenant_id: str) -> dict[str, Any]:
        """Fail closed on missing indexes or malformed content-address identities."""
        self._tenant(tenant_id)
        installed = {
            str(row[0])
            for row in self.store._db.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        errors: list[str] = []
        missing = sorted(self.REQUIRED_INDEXES - installed)
        if missing:
            errors.extend(f"missing_index:{name}" for name in missing)

        groups = {
            "files": self.files(tenant_id),
            "knowledge": self.knowledge(tenant_id),
            "mining": self.mining(tenant_id),
        }
        for group, entries in groups.items():
            for entry in entries:
                digest = entry.content_sha256
                if len(digest) != 64:
                    errors.append(f"{group}:{entry.entity_id}:invalid_content_sha256")
                else:
                    try:
                        bytes.fromhex(digest)
                    except ValueError:
                        errors.append(f"{group}:{entry.entity_id}:invalid_content_sha256")
        return {
            "schema": "hyba.ovid-data-index-verification/v1",
            "tenant_id": tenant_id,
            "passed": not errors,
            "errors": tuple(errors),
            "organisation_digest": self.organisation_digest(tenant_id),
            "counts": {name: len(entries) for name, entries in groups.items()},
        }


__all__ = ["OvidDataIndex", "OvidIndexEntry"]
