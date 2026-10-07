"""Evidence-bound epistemic projection for HYBA / QuantumPhi.

THESEUS is the durable system of record. This module is deliberately a
rebuildable ontology/query projection over producer-authored, THESEUS-custodied
records. It answers what we currently know, why we think we know it, who owns
its meaning, and what superseded it without turning a database row into
semantic authority.

Knowledge is append-only. Corrections and changed understanding are expressed
through supersedes_id and typed relations; historical evidence is never
silently rewritten.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .models import AccessDenied, IntegrityFailure, InvalidRecord

KNOWLEDGE_KINDS = frozenset(
    {
        "observation",
        "measurement",
        "claim",
        "hypothesis",
        "decision",
        "constraint",
        "unknown",
        "refutation",
    }
)
KNOWLEDGE_RELATIONS = frozenset(
    {
        "supports",
        "refutes",
        "supersedes",
        "derives_from",
        "constrains",
        "equivalent_to",
        "about",
    }
)
CANONICAL_EVIDENCE_STATES = frozenset(
    {"PASS", "FAIL", "MEASURED", "GATED", "UNAVAILABLE", "MISSING", "REFUTED"}
)

KNOWLEDGE_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS knowledge_records(
 tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
 knowledge_id TEXT NOT NULL,
 subject TEXT NOT NULL,
 predicate TEXT NOT NULL,
 object_json TEXT NOT NULL,
 knowledge_kind TEXT NOT NULL,
 semantic_owner TEXT NOT NULL,
 producer TEXT NOT NULL,
 producer_version TEXT NOT NULL,
 schema_version INTEGER NOT NULL,
 evidence_state TEXT NOT NULL,
 evidence_class TEXT NOT NULL,
 content_sha256 TEXT NOT NULL,
 source_ids_json TEXT NOT NULL,
 parent_ids_json TEXT NOT NULL,
 correlation_ids_json TEXT NOT NULL,
 provenance_json TEXT NOT NULL,
 custody_record_id TEXT NOT NULL,
 supersedes_id TEXT,
 attestation_id TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,knowledge_id),
 FOREIGN KEY(tenant_id,supersedes_id)
   REFERENCES knowledge_records(tenant_id,knowledge_id),
 FOREIGN KEY(tenant_id,attestation_id)
   REFERENCES attestations(tenant_id,id)
);
CREATE TABLE IF NOT EXISTS knowledge_relations(
 tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
 relation_id TEXT NOT NULL,
 from_knowledge_id TEXT NOT NULL,
 to_knowledge_id TEXT NOT NULL,
 relation_type TEXT NOT NULL,
 producer TEXT NOT NULL,
 custody_record_id TEXT NOT NULL,
 attestation_id TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,relation_id),
 UNIQUE(tenant_id,from_knowledge_id,to_knowledge_id,relation_type),
 FOREIGN KEY(tenant_id,from_knowledge_id)
   REFERENCES knowledge_records(tenant_id,knowledge_id),
 FOREIGN KEY(tenant_id,to_knowledge_id)
   REFERENCES knowledge_records(tenant_id,knowledge_id),
 FOREIGN KEY(tenant_id,attestation_id)
   REFERENCES attestations(tenant_id,id)
);
CREATE INDEX IF NOT EXISTS idx_knowledge_subject
 ON knowledge_records(tenant_id,subject,predicate);
CREATE INDEX IF NOT EXISTS idx_knowledge_owner
 ON knowledge_records(tenant_id,semantic_owner,evidence_state);
CREATE INDEX IF NOT EXISTS idx_knowledge_supersedes
 ON knowledge_records(tenant_id,supersedes_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_rel_from
 ON knowledge_relations(tenant_id,from_knowledge_id,relation_type);
"""


def _json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise InvalidRecord(f"value is not canonical JSON: {exc}") from exc


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _id(prefix: str, material: bytes) -> str:
    return f"{prefix}_{_sha(material)[:32]}"


@dataclass(frozen=True)
class KnowledgeRecord:
    knowledge_id: str
    tenant_id: str
    subject: str
    predicate: str
    object: Any
    knowledge_kind: str
    semantic_owner: str
    producer: str
    producer_version: str
    schema_version: int
    evidence_state: str
    evidence_class: str
    content_sha256: str
    source_ids: tuple[str, ...]
    parent_ids: tuple[str, ...]
    correlation_ids: dict[str, str]
    provenance: dict[str, Any]
    custody_record_id: str
    supersedes_id: str | None
    attestation_id: str
    created_at: str


class KnowledgeProjection:
    """Rebuildable, custody-bound epistemic projection.

    The producer owns the meaning of a record, THESEUS owns durable custody,
    and this class owns only the queryable projection.
    """

    def __init__(self, store: Any, custody: Any | None = None) -> None:
        self.store = store
        self.custody = custody

    def _tenant(self, tenant_id: str) -> None:
        self.store._tenant(tenant_id)

    @staticmethod
    def _provenance(value: Mapping[str, Any] | None) -> dict[str, Any]:
        src = dict(value or {})
        defaults: dict[str, Any] = {
            "code_ref": "UNAVAILABLE",
            "package_ref": "UNAVAILABLE",
            "config_digest": "UNAVAILABLE",
            "backend": "UNAVAILABLE",
            "device_identity": "UNAVAILABLE",
            "precision_contract": "UNAVAILABLE",
            "exactness_contract": "UNAVAILABLE",
            "policy_refs": [],
            "owner_approval_ref": "UNAVAILABLE",
            "retention_class": "UNAVAILABLE",
            "recovery_class": "UNAVAILABLE",
        }
        defaults.update(src)
        defaults["policy_refs"] = [str(x) for x in defaults.get("policy_refs") or ()]
        return defaults

    def _payload(
        self,
        *,
        subject: str,
        predicate: str,
        object_value: Any,
        knowledge_kind: str,
        semantic_owner: str,
        producer: str,
        producer_version: str,
        schema_version: int,
        evidence_state: str,
        evidence_class: str,
        source_ids: Sequence[str],
        parent_ids: Sequence[str],
        correlation_ids: Mapping[str, str],
        provenance: Mapping[str, Any],
        supersedes_id: str | None,
    ) -> dict[str, Any]:
        return {
            "schema": "hyba.knowledge-projection/v1",
            "subject": subject,
            "predicate": predicate,
            "object": object_value,
            "knowledge_kind": knowledge_kind,
            "semantic_owner": semantic_owner,
            "producer": producer,
            "producer_version": producer_version,
            "schema_version": int(schema_version),
            "evidence_state": evidence_state,
            "evidence_class": evidence_class,
            "source_ids": [str(x) for x in source_ids],
            "parent_ids": [str(x) for x in parent_ids],
            "correlation_ids": {str(k): str(v) for k, v in correlation_ids.items()},
            "provenance": dict(provenance),
            "supersedes_id": supersedes_id,
        }

    def project(
        self,
        tenant_id: str,
        *,
        subject: str,
        predicate: str,
        object_value: Any,
        knowledge_kind: str,
        semantic_owner: str,
        producer: str,
        evidence_state: str,
        evidence_class: str | None = None,
        producer_version: str = "",
        schema_version: int = 1,
        source_ids: Sequence[str] = (),
        parent_ids: Sequence[str] = (),
        correlation_ids: Mapping[str, str] | None = None,
        provenance: Mapping[str, Any] | None = None,
        supersedes_id: str | None = None,
    ) -> KnowledgeRecord:
        self._tenant(tenant_id)
        if self.custody is None:
            raise InvalidRecord(
                "THESEUS custody adapter is required for production knowledge projection"
            )
        subject = str(subject).strip()
        predicate = str(predicate).strip()
        kind = str(knowledge_kind).strip().lower()
        owner = str(semantic_owner).strip()
        producer = str(producer).strip().lower()
        state = str(evidence_state).strip().upper()
        eclass = str(evidence_class or state).strip().upper()
        if not subject or not predicate or not owner or not producer:
            raise InvalidRecord("subject, predicate, semantic_owner and producer are required")
        if kind not in KNOWLEDGE_KINDS:
            raise InvalidRecord(f"unsupported knowledge_kind={kind!r}")
        if state not in CANONICAL_EVIDENCE_STATES:
            raise InvalidRecord(f"unsupported evidence_state={state!r}")
        if int(schema_version) < 1:
            raise InvalidRecord("schema_version must be >= 1")

        parents = tuple(str(x) for x in parent_ids)
        sources = tuple(str(x) for x in source_ids)
        corr = {str(k): str(v) for k, v in dict(correlation_ids or {}).items()}
        prov = self._provenance(provenance)

        with self.store._lock:
            for parent in parents:
                if not self.store._db.execute(
                    "SELECT 1 FROM knowledge_records WHERE tenant_id=? AND knowledge_id=?",
                    (tenant_id, parent),
                ).fetchone():
                    raise AccessDenied(f"knowledge parent not found in tenant: {parent}")
            if supersedes_id:
                previous = self.store._db.execute(
                    "SELECT subject,predicate,semantic_owner FROM knowledge_records "
                    "WHERE tenant_id=? AND knowledge_id=?",
                    (tenant_id, str(supersedes_id)),
                ).fetchone()
                if previous is None:
                    raise AccessDenied("superseded knowledge record not found in tenant")
                if (
                    previous["subject"] != subject
                    or previous["predicate"] != predicate
                    or previous["semantic_owner"] != owner
                ):
                    raise InvalidRecord(
                        "supersession must preserve subject, predicate and semantic owner"
                    )

        body = self._payload(
            subject=subject,
            predicate=predicate,
            object_value=object_value,
            knowledge_kind=kind,
            semantic_owner=owner,
            producer=producer,
            producer_version=str(producer_version),
            schema_version=int(schema_version),
            evidence_state=state,
            evidence_class=eclass,
            source_ids=sources,
            parent_ids=parents,
            correlation_ids=corr,
            provenance=prov,
            supersedes_id=str(supersedes_id) if supersedes_id else None,
        )
        payload = _json(body).encode("utf-8")
        digest = _sha(payload)
        knowledge_id = _id("knowledge", f"{tenant_id}:{digest}".encode())

        existing = self.store._db.execute(
            "SELECT 1 FROM knowledge_records WHERE tenant_id=? AND knowledge_id=?",
            (tenant_id, knowledge_id),
        ).fetchone()
        if existing:
            return self.read(tenant_id, knowledge_id)

        from aethel.enterprise.records import OperationalRecord

        custody = OperationalRecord(
            record_id=f"knowledge.{knowledge_id}",
            producer=producer,
            producer_version=str(producer_version),
            schema_version=int(schema_version),
            kind="knowledge_projection",
            payload=payload,
            evidence_state=state,
            lineage=tuple(dict.fromkeys((*parents, *sources))),
            correlation_ids={"tenant_id": tenant_id, "knowledge_id": knowledge_id, **corr},
            meta={
                "semantic_owner": owner,
                "knowledge_kind": kind,
                "evidence_class": eclass,
                "policy_refs": prov["policy_refs"],
                "owner_approval_ref": prov["owner_approval_ref"],
                "retention_class": prov["retention_class"],
                "recovery_class": prov["recovery_class"],
            },
        )
        custody_id = self.custody.put_record(tenant_id, custody)
        if not self.custody.verify(tenant_id, custody_id):
            raise IntegrityFailure("THESEUS did not verify the knowledge custody record")

        from .store import _now as store_now
        created = store_now()
        with self.store._tx() as db:
            # Recheck under the write transaction. The preceding custody put is
            # content/idempotency bound, so concurrent identical projections
            # converge without double-counting quota or minting extra rows.
            already = db.execute(
                "SELECT 1 FROM knowledge_records WHERE tenant_id=? AND knowledge_id=?",
                (tenant_id, knowledge_id),
            ).fetchone()
            if already is None:
                self.store._reserve(db, tenant_id, 1, len(payload), knowledge_id)
                att = self.store._attest(
                    db,
                    tenant_id,
                    f"knowledge:{knowledge_id}",
                    producer,
                    {
                        "content_sha256": digest,
                        "semantic_owner": owner,
                        "evidence_state": state,
                        "custody_record_id": custody_id,
                    },
                    (),
                )
                db.execute(
                    "INSERT INTO knowledge_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        tenant_id,
                        knowledge_id,
                        subject,
                        predicate,
                        _json(object_value),
                        kind,
                        owner,
                        producer,
                        str(producer_version),
                        int(schema_version),
                        state,
                        eclass,
                        digest,
                        _json(sources),
                        _json(parents),
                        _json(corr),
                        _json(prov),
                        custody_id,
                        str(supersedes_id) if supersedes_id else None,
                        att.id,
                        created,
                    ),
                )
        if supersedes_id:
            self.relate(
                tenant_id,
                knowledge_id,
                str(supersedes_id),
                "supersedes",
                producer=producer,
            )
        return self.read(tenant_id, knowledge_id)

    def _row_payload(self, row: Any) -> dict[str, Any]:
        return self._payload(
            subject=row["subject"],
            predicate=row["predicate"],
            object_value=json.loads(row["object_json"]),
            knowledge_kind=row["knowledge_kind"],
            semantic_owner=row["semantic_owner"],
            producer=row["producer"],
            producer_version=row["producer_version"],
            schema_version=row["schema_version"],
            evidence_state=row["evidence_state"],
            evidence_class=row["evidence_class"],
            source_ids=json.loads(row["source_ids_json"]),
            parent_ids=json.loads(row["parent_ids_json"]),
            correlation_ids=json.loads(row["correlation_ids_json"]),
            provenance=json.loads(row["provenance_json"]),
            supersedes_id=row["supersedes_id"],
        )

    def read(self, tenant_id: str, knowledge_id: str) -> KnowledgeRecord:
        self._tenant(tenant_id)
        row = self.store._db.execute(
            "SELECT * FROM knowledge_records WHERE tenant_id=? AND knowledge_id=?",
            (tenant_id, str(knowledge_id)),
        ).fetchone()
        if row is None:
            raise AccessDenied("knowledge record not found in tenant")
        body = self._row_payload(row)
        digest = _sha(_json(body).encode("utf-8"))
        if digest != row["content_sha256"]:
            raise IntegrityFailure(f"knowledge digest mismatch: {knowledge_id}")
        if _id("knowledge", f"{tenant_id}:{digest}".encode()) != row["knowledge_id"]:
            raise IntegrityFailure(f"knowledge content address mismatch: {knowledge_id}")
        self.store.verify_attestation(tenant_id, row["attestation_id"])
        details = self.store.get_attestation(tenant_id, row["attestation_id"]).details
        expected = {
            "content_sha256": digest,
            "semantic_owner": row["semantic_owner"],
            "evidence_state": row["evidence_state"],
            "custody_record_id": row["custody_record_id"],
        }
        if details != expected:
            raise IntegrityFailure(f"knowledge attestation mismatch: {knowledge_id}")
        if self.custody is None or not self.custody.verify(tenant_id, row["custody_record_id"]):
            raise IntegrityFailure(f"knowledge custody unavailable: {knowledge_id}")
        opener = getattr(self.custody, "open_tenant", None)
        if callable(opener):
            op = opener(tenant_id).get_record(row["custody_record_id"])
            if (
                op.content_digest != digest
                or bytes(op.payload) != _json(body).encode("utf-8")
                or op.producer != row["producer"]
                or op.kind != "knowledge_projection"
            ):
                raise IntegrityFailure(
                    f"knowledge custody binding mismatch: {knowledge_id}"
                )
        return KnowledgeRecord(
            knowledge_id=row["knowledge_id"],
            tenant_id=tenant_id,
            subject=row["subject"],
            predicate=row["predicate"],
            object=json.loads(row["object_json"]),
            knowledge_kind=row["knowledge_kind"],
            semantic_owner=row["semantic_owner"],
            producer=row["producer"],
            producer_version=row["producer_version"],
            schema_version=int(row["schema_version"]),
            evidence_state=row["evidence_state"],
            evidence_class=row["evidence_class"],
            content_sha256=row["content_sha256"],
            source_ids=tuple(json.loads(row["source_ids_json"])),
            parent_ids=tuple(json.loads(row["parent_ids_json"])),
            correlation_ids=dict(json.loads(row["correlation_ids_json"])),
            provenance=dict(json.loads(row["provenance_json"])),
            custody_record_id=row["custody_record_id"],
            supersedes_id=row["supersedes_id"],
            attestation_id=row["attestation_id"],
            created_at=row["created_at"],
        )

    def query(
        self,
        tenant_id: str,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        semantic_owner: str | None = None,
        evidence_state: str | None = None,
        knowledge_kind: str | None = None,
        latest_only: bool = True,
        limit: int = 100,
    ) -> tuple[KnowledgeRecord, ...]:
        self._tenant(tenant_id)
        if limit < 1 or limit > 10_000:
            raise InvalidRecord("limit must be between 1 and 10000")
        clauses = ["kr.tenant_id=?"]
        values: list[Any] = [tenant_id]
        for column, value in (
            ("subject", subject),
            ("predicate", predicate),
            ("semantic_owner", semantic_owner),
            ("evidence_state", evidence_state.upper() if evidence_state else None),
            ("knowledge_kind", knowledge_kind.lower() if knowledge_kind else None),
        ):
            if value is not None:
                clauses.append(f"kr.{column}=?")
                values.append(value)
        if latest_only:
            clauses.append(
                "NOT EXISTS (SELECT 1 FROM knowledge_records newer "
                "WHERE newer.tenant_id=kr.tenant_id "
                "AND newer.supersedes_id=kr.knowledge_id)"
            )
        sql = (
            "SELECT kr.knowledge_id FROM knowledge_records kr WHERE "
            + " AND ".join(clauses)
            + " ORDER BY kr.created_at,kr.knowledge_id LIMIT ?"
        )
        values.append(int(limit))
        return tuple(
            self.read(tenant_id, row[0])
            for row in self.store._db.execute(sql, tuple(values)).fetchall()
        )

    def relate(
        self,
        tenant_id: str,
        from_id: str,
        to_id: str,
        relation_type: str,
        *,
        producer: str,
    ) -> str:
        self._tenant(tenant_id)
        relation = str(relation_type).strip().lower()
        if relation not in KNOWLEDGE_RELATIONS:
            raise InvalidRecord(f"unsupported knowledge relation={relation!r}")
        for kid in (str(from_id), str(to_id)):
            if not self.store._db.execute(
                "SELECT 1 FROM knowledge_records WHERE tenant_id=? AND knowledge_id=?",
                (tenant_id, kid),
            ).fetchone():
                raise AccessDenied(f"knowledge relation endpoint not found in tenant: {kid}")
        relation_id = _id(
            "knowledge_relation",
            f"{tenant_id}:{from_id}:{to_id}:{relation}".encode(),
        )
        existing = self.store._db.execute(
            "SELECT relation_id FROM knowledge_relations "
            "WHERE tenant_id=? AND relation_id=?",
            (tenant_id, relation_id),
        ).fetchone()
        if existing:
            return str(existing[0])
        if self.custody is None:
            raise InvalidRecord("THESEUS custody adapter required for knowledge relations")
        from aethel.enterprise.records import OperationalRecord
        payload = _json(
            {
                "schema": "hyba.knowledge-relation/v1",
                "relation_id": relation_id,
                "from": str(from_id),
                "to": str(to_id),
                "relation": relation,
                "producer": str(producer).strip().lower(),
            }
        ).encode("utf-8")
        op = OperationalRecord(
            record_id=f"knowledge_relation.{relation_id}",
            producer=str(producer).strip().lower(),
            producer_version="knowledge-projection/1",
            schema_version=1,
            kind="knowledge_relation",
            payload=payload,
            evidence_state="MEASURED",
            lineage=(str(from_id), str(to_id)),
            correlation_ids={"tenant_id": tenant_id, "relation_id": relation_id},
            meta={"relation_type": relation},
        )
        custody_id = self.custody.put_record(tenant_id, op)
        if not self.custody.verify(tenant_id, custody_id):
            raise IntegrityFailure("THESEUS did not verify knowledge relation custody")
        with self.store._tx() as db:
            already = db.execute(
                "SELECT 1 FROM knowledge_relations WHERE tenant_id=? AND relation_id=?",
                (tenant_id, relation_id),
            ).fetchone()
            if already is None:
                att = self.store._attest(
                    db,
                    tenant_id,
                    f"knowledge_relation:{relation_id}",
                    str(producer).strip().lower(),
                    {
                        "from": str(from_id),
                        "to": str(to_id),
                        "relation": relation,
                        "custody_record_id": custody_id,
                    },
                    (),
                )
                from .store import _now as store_now
                db.execute(
                    "INSERT INTO knowledge_relations VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        tenant_id,
                        relation_id,
                        str(from_id),
                        str(to_id),
                        relation,
                        str(producer).strip().lower(),
                        custody_id,
                        att.id,
                        store_now(),
                    ),
                )
        return relation_id

    def restore_from_custody(self, tenant_id: str) -> dict[str, Any]:
        """Rebuild missing projection rows from authoritative THESEUS records."""
        self._tenant(tenant_id)
        if self.custody is None:
            raise InvalidRecord("THESEUS custody adapter required for projection restore")
        custody = self.custody.open_tenant(tenant_id)
        restored: list[str] = []
        skipped: list[str] = []
        pending: dict[str, tuple[Any, dict[str, Any]]] = {}
        for item in custody.list_records():
            if item.get("kind") != "knowledge_projection":
                continue
            op = custody.get_record(str(item["record_id"]))
            body = json.loads(op.payload.decode("utf-8"))
            if body.get("schema") != "hyba.knowledge-projection/v1":
                raise IntegrityFailure(f"unsupported knowledge payload schema: {body.get('schema')}")
            digest = _sha(op.payload)
            kid = _id("knowledge", f"{tenant_id}:{digest}".encode())
            pending[kid] = (op, body)

        # Parents and superseded records are inserted before their dependants.
        while pending:
            progressed = False
            for kid, (op, body) in list(pending.items()):
                if self.store._db.execute(
                    "SELECT 1 FROM knowledge_records WHERE tenant_id=? AND knowledge_id=?",
                    (tenant_id, kid),
                ).fetchone():
                    self.read(tenant_id, kid)
                    skipped.append(kid)
                    del pending[kid]
                    progressed = True
                    continue
                parents = tuple(body.get("parent_ids") or ())
                supersedes = body.get("supersedes_id")
                dependencies = tuple(parents) + ((supersedes,) if supersedes else ())
                if any(
                    dep
                    and not self.store._db.execute(
                        "SELECT 1 FROM knowledge_records WHERE tenant_id=? AND knowledge_id=?",
                        (tenant_id, dep),
                    ).fetchone()
                    for dep in dependencies
                ):
                    continue
                digest = _sha(op.payload)
                from .store import _now as store_now
                with self.store._tx() as db:
                    self.store._reserve(db, tenant_id, 1, len(op.payload), kid)
                    att = self.store._attest(
                        db,
                        tenant_id,
                        f"knowledge:{kid}",
                        op.producer,
                        {
                            "content_sha256": digest,
                            "semantic_owner": body["semantic_owner"],
                            "evidence_state": body["evidence_state"],
                            "custody_record_id": op.record_id,
                        },
                        (),
                    )
                    db.execute(
                        "INSERT INTO knowledge_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            tenant_id,
                            kid,
                            body["subject"],
                            body["predicate"],
                            _json(body["object"]),
                            body["knowledge_kind"],
                            body["semantic_owner"],
                            body["producer"],
                            body.get("producer_version", ""),
                            int(body.get("schema_version", 1)),
                            body["evidence_state"],
                            body.get("evidence_class", body["evidence_state"]),
                            digest,
                            _json(tuple(body.get("source_ids") or ())),
                            _json(parents),
                            _json(dict(body.get("correlation_ids") or {})),
                            _json(self._provenance(body.get("provenance"))),
                            op.record_id,
                            supersedes,
                            att.id,
                            store_now(),
                        ),
                    )
                restored.append(kid)
                del pending[kid]
                progressed = True
            if not progressed:
                raise IntegrityFailure(
                    "knowledge projection restore has unresolved lineage dependencies: "
                    + ",".join(sorted(pending))
                )
        restored_relations: list[str] = []
        for item in custody.list_records():
            if item.get("kind") != "knowledge_relation":
                continue
            op = custody.get_record(str(item["record_id"]))
            body = json.loads(op.payload.decode("utf-8"))
            if body.get("schema") != "hyba.knowledge-relation/v1":
                raise IntegrityFailure(
                    f"unsupported knowledge relation schema: {body.get('schema')}"
                )
            from_id, to_id = str(body["from"]), str(body["to"])
            if not all(
                self.store._db.execute(
                    "SELECT 1 FROM knowledge_records WHERE tenant_id=? AND knowledge_id=?",
                    (tenant_id, endpoint),
                ).fetchone()
                for endpoint in (from_id, to_id)
            ):
                raise IntegrityFailure(
                    f"cannot restore relation {body.get('relation_id')}: endpoint missing"
                )
            relation = str(body["relation"])
            expected_id = _id(
                "knowledge_relation",
                f"{tenant_id}:{from_id}:{to_id}:{relation}".encode(),
            )
            if expected_id != body.get("relation_id"):
                raise IntegrityFailure("knowledge relation content address mismatch")
            if self.store._db.execute(
                "SELECT 1 FROM knowledge_relations WHERE tenant_id=? AND relation_id=?",
                (tenant_id, expected_id),
            ).fetchone():
                continue
            with self.store._tx() as db:
                att = self.store._attest(
                    db,
                    tenant_id,
                    f"knowledge_relation:{expected_id}",
                    op.producer,
                    {
                        "from": from_id,
                        "to": to_id,
                        "relation": relation,
                        "custody_record_id": op.record_id,
                    },
                    (),
                )
                from .store import _now as store_now
                db.execute(
                    "INSERT INTO knowledge_relations VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        tenant_id,
                        expected_id,
                        from_id,
                        to_id,
                        relation,
                        op.producer,
                        op.record_id,
                        att.id,
                        store_now(),
                    ),
                )
            restored_relations.append(expected_id)
        return {
            "schema": "hyba.knowledge-restore/v1",
            "restored": tuple(restored),
            "restored_relations": tuple(restored_relations),
            "skipped": tuple(skipped),
            "passed": True,
        }

    def verify(self, tenant_id: str | None = None) -> dict[str, Any]:
        errors: list[str] = []
        tids = (
            [tenant_id]
            if tenant_id
            else [r[0] for r in self.store._db.execute("SELECT tenant_id FROM tenants")]
        )
        for tid in tids:
            self._tenant(tid)
            rows = list(
                self.store._db.execute(
                    "SELECT knowledge_id,parent_ids_json,supersedes_id "
                    "FROM knowledge_records WHERE tenant_id=?",
                    (tid,),
                )
            )
            ids = {row["knowledge_id"] for row in rows}
            for row in rows:
                try:
                    self.read(tid, row["knowledge_id"])
                except Exception as exc:
                    errors.append(f"{tid}:{row['knowledge_id']}:{type(exc).__name__}:{exc}")
                    continue
                for parent in json.loads(row["parent_ids_json"]):
                    if parent not in ids:
                        errors.append(f"{tid}:{row['knowledge_id']}:missing parent {parent}")
                if row["supersedes_id"] and row["supersedes_id"] not in ids:
                    errors.append(
                        f"{tid}:{row['knowledge_id']}:missing superseded {row['supersedes_id']}"
                    )
            for rel in self.store._db.execute(
                "SELECT * FROM knowledge_relations WHERE tenant_id=?", (tid,)
            ):
                if rel["relation_type"] not in KNOWLEDGE_RELATIONS:
                    errors.append(f"{tid}:{rel['relation_id']}:unknown relation")
                if rel["from_knowledge_id"] not in ids or rel["to_knowledge_id"] not in ids:
                    errors.append(f"{tid}:{rel['relation_id']}:dangling relation")
                try:
                    self.store.verify_attestation(tid, rel["attestation_id"])
                    details = self.store.get_attestation(tid, rel["attestation_id"]).details
                    expected = {
                        "from": rel["from_knowledge_id"],
                        "to": rel["to_knowledge_id"],
                        "relation": rel["relation_type"],
                        "custody_record_id": rel["custody_record_id"],
                    }
                    if details != expected:
                        raise IntegrityFailure("relation attestation mismatch")
                    if self.custody is None or not self.custody.verify(
                        tid, rel["custody_record_id"]
                    ):
                        raise IntegrityFailure("relation custody unavailable")
                    opener = getattr(self.custody, "open_tenant", None)
                    if callable(opener):
                        op = opener(tid).get_record(rel["custody_record_id"])
                        relation_payload = _json(
                            {
                                "schema": "hyba.knowledge-relation/v1",
                                "relation_id": rel["relation_id"],
                                "from": rel["from_knowledge_id"],
                                "to": rel["to_knowledge_id"],
                                "relation": rel["relation_type"],
                                "producer": rel["producer"],
                            }
                        ).encode("utf-8")
                        if (
                            bytes(op.payload) != relation_payload
                            or op.content_digest != _sha(relation_payload)
                            or op.producer != rel["producer"]
                            or op.kind != "knowledge_relation"
                        ):
                            raise IntegrityFailure("relation custody binding mismatch")
                except Exception as exc:
                    errors.append(
                        f"{tid}:{rel['relation_id']}:{type(exc).__name__}:{exc}"
                    )
        return {
            "schema": "hyba.knowledge-verification/v1",
            "passed": not errors,
            "errors": tuple(errors),
        }


__all__ = [
    "CANONICAL_EVIDENCE_STATES",
    "KNOWLEDGE_KINDS",
    "KNOWLEDGE_RELATIONS",
    "KNOWLEDGE_SCHEMA",
    "KnowledgeProjection",
    "KnowledgeRecord",
]
