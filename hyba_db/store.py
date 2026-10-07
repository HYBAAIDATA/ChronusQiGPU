"""Attested, replayable, multi-tenant HYBA ontology/topology store.

The store deliberately uses only the Python standard library.  SQLite supplies
atomicity and foreign-key enforcement; SHA-256/HMAC supply content addressing
and tamper evidence.  Every public read is tenant scoped.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import sqlite3
import struct
import threading
import uuid
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from .models import (
    AccessDenied, Attestation, Certificate, Client, DatabaseVerification,
    EdgeRecord, FoldRecord, IntegrityFailure, InvalidRecord, NodeRecord,
    Quota, QuotaExceeded, TensorRecord,
)
from .file_registry import FILE_REGISTRY_SCHEMA
from .theseus_registry import TheseusFileRegistry
from .knowledge import KNOWLEDGE_SCHEMA, KnowledgeProjection


class NodeKind(StrEnum):
    DEVICE = "device"; KERNEL = "kernel"; BUFFER = "buffer"; JOB = "job"
    SHARE = "share"; CERTIFICATE = "certificate"; INTELLIGENCE = "intelligence"
    MODE = "mode"; GUARDIAN = "guardian"; POOL = "pool"; ASIC = "asic"
    IGPU = "igpu"; GPU = "gpu"; TENSOR = "tensor"


class EdgeKind(StrEnum):
    ROTATES = "rotates"; FOLDS = "folds"; UNFOLDS = "unfolds"
    CERTIFIES = "certifies"; CONTRACTS = "contracts"; COMPRESSES = "compresses"
    CONNECTS = "connects"; BOUNDS = "bounds"; PERSISTS = "persists"
    ATTESTS = "attests"; VERIFIES = "verifies"; REPLAYS = "replays"
    ENTANGLES = "entangles"; MULTIPLIES = "multiplies"; SWARMS = "swarms"
    HONEY_POTS = "honey_pots"; WILLOWS = "willows"; EXPOSES = "exposes"
    DISPATCHES = "dispatches"; HASHES = "hashes"; SUBMITS = "submits"
    ACCEPTS = "accepts"


class ProofStatus(StrEnum):
    PROVED = "proved"; TESTED = "tested"; MODELED = "modeled"; GAP = "gap"


_NAMESPACE = re.compile(r"^[a-z][a-z0-9_-]{2,62}$")
_KIND = {x.value for x in NodeKind}
_EDGE = {x.value for x in EdgeKind}
_STATUS = {x.value for x in ProofStatus}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise InvalidRecord(f"value is not canonical JSON: {exc}") from exc


def _load(value: str) -> Any:
    return json.loads(value)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ident(prefix: str, material: bytes) -> str:
    return f"{prefix}_{_sha(material)[:32]}"


def _fibonacci_to(n: int) -> list[int]:
    values = [1, 2]
    while values[-1] <= n:
        values.append(values[-1] + values[-2])
    return values


def _zeckendorf(n: int) -> int:
    """Return a bit mask of non-consecutive Fibonacci terms for signed n."""
    sign = -1 if n < 0 else 1
    remaining = abs(n)
    if not remaining:
        return 0
    fib = _fibonacci_to(remaining)
    if fib[-1] > remaining:
        fib.pop()
    mask = 0
    for index in range(len(fib) - 1, -1, -1):
        if fib[index] <= remaining:
            remaining -= fib[index]
            mask |= 1 << index
    if remaining:
        raise IntegrityFailure("Zeckendorf encoding did not terminate")
    return sign * mask


def _zeckendorf_value(mask: int) -> int:
    sign = -1 if mask < 0 else 1
    bits = abs(mask)
    a, b, total = 1, 2, 0
    index = 0
    previous = False
    while bits:
        selected = bool(bits & 1)
        if selected and previous:
            raise IntegrityFailure("certificate has adjacent Fibonacci terms")
        if selected:
            total += a
        previous = selected
        bits >>= 1
        a, b = b, a + b
        index += 1
    return sign * total


def _lucas(depth: int) -> tuple[int, ...]:
    if depth < 0:
        return ()
    values = [2]
    if depth:
        values.append(1)
    while len(values) <= depth:
        values.append(values[-1] + values[-2])
    return tuple(values)


_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tenants(
 tenant_id TEXT PRIMARY KEY, namespace TEXT NOT NULL UNIQUE, max_records INTEGER NOT NULL,
 max_blob_bytes INTEGER NOT NULL, used_records INTEGER NOT NULL DEFAULT 0,
 used_blob_bytes INTEGER NOT NULL DEFAULT 0, root_attestation_id TEXT, root_node_id TEXT,
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tenant_heads(tenant_id TEXT PRIMARY KEY REFERENCES tenants(tenant_id), attestation_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attestations(
 tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id), id TEXT NOT NULL, subject TEXT NOT NULL,
 issuer TEXT NOT NULL, signature TEXT NOT NULL, timestamp TEXT NOT NULL, sequence INTEGER NOT NULL,
 chain_root TEXT NOT NULL, details_json TEXT NOT NULL, PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,sequence));
CREATE TABLE IF NOT EXISTS attestation_parents(
 tenant_id TEXT NOT NULL, child_id TEXT NOT NULL, parent_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
 PRIMARY KEY(tenant_id,child_id,parent_id),
 FOREIGN KEY(tenant_id,child_id) REFERENCES attestations(tenant_id,id),
 FOREIGN KEY(tenant_id,parent_id) REFERENCES attestations(tenant_id,id));
CREATE TABLE IF NOT EXISTS quota_events(
 tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id), id INTEGER PRIMARY KEY AUTOINCREMENT,
 record_delta INTEGER NOT NULL, byte_delta INTEGER NOT NULL, subject TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS certificates(
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, masks_json TEXT NOT NULL, digest TEXT NOT NULL,
 vector_digest TEXT NOT NULL, lucas_json TEXT NOT NULL, depth INTEGER NOT NULL, scale INTEGER NOT NULL,
 attestation_id TEXT NOT NULL, PRIMARY KEY(tenant_id,id),
 FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id));
CREATE TABLE IF NOT EXISTS folds(
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, vector BLOB NOT NULL, certificate_id TEXT NOT NULL,
 parent_id TEXT, created_at TEXT NOT NULL, attestation_id TEXT NOT NULL, PRIMARY KEY(tenant_id,id),
 FOREIGN KEY(tenant_id,certificate_id) REFERENCES certificates(tenant_id,id),
 FOREIGN KEY(tenant_id,parent_id) REFERENCES folds(tenant_id,id),
 FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id));
CREATE TABLE IF NOT EXISTS physical_blocks(
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, fibonacci_address INTEGER NOT NULL, payload BLOB NOT NULL,
 digest TEXT NOT NULL, fold_id TEXT NOT NULL, attestation_id TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,fibonacci_address),
 FOREIGN KEY(tenant_id,fold_id) REFERENCES folds(tenant_id,id),
 FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id));
CREATE TABLE IF NOT EXISTS tensors(
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('mps','tt','mpo')),
 fold_id TEXT NOT NULL, payload BLOB NOT NULL, format TEXT NOT NULL, dimensions_json TEXT NOT NULL,
 norm REAL NOT NULL, entropy REAL, trace REAL, invariants_json TEXT NOT NULL, digest TEXT NOT NULL,
 attestation_id TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(tenant_id,id),
 FOREIGN KEY(tenant_id,fold_id) REFERENCES folds(tenant_id,id),
 FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id));
CREATE TABLE IF NOT EXISTS nodes(
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL,
 betti_json TEXT, persistence REAL, attestation_id TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,id), FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id));
CREATE TABLE IF NOT EXISTS edges(
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, from_node TEXT NOT NULL, to_node TEXT NOT NULL,
 kind TEXT NOT NULL, weight REAL NOT NULL, attestation_id TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,id),
 FOREIGN KEY(tenant_id,from_node) REFERENCES nodes(tenant_id,id),
 FOREIGN KEY(tenant_id,to_node) REFERENCES nodes(tenant_id,id),
 FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id));
CREATE TABLE IF NOT EXISTS invariants(
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, layer INTEGER NOT NULL,
 statement TEXT NOT NULL, proof_status TEXT NOT NULL, evidence_attestation_id TEXT NOT NULL,
 attestation_id TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,name),
 FOREIGN KEY(tenant_id,evidence_attestation_id) REFERENCES attestations(tenant_id,id),
 FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id));
CREATE TABLE IF NOT EXISTS contracts(
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, schema_json TEXT NOT NULL,
 invariant_ids_json TEXT NOT NULL, attestation_id TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,name),
 FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id));
CREATE TABLE IF NOT EXISTS ontology(
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, term TEXT NOT NULL, definition TEXT NOT NULL,
 relations_json TEXT NOT NULL, attestation_id TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,term),
 FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id));
CREATE TABLE IF NOT EXISTS computations(
 tenant_id TEXT NOT NULL, id TEXT NOT NULL, operation TEXT NOT NULL, input_ids_json TEXT NOT NULL,
 result_json TEXT NOT NULL, attestation_id TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(tenant_id,id), FOREIGN KEY(tenant_id,attestation_id) REFERENCES attestations(tenant_id,id));
CREATE VIEW IF NOT EXISTS mps AS SELECT * FROM tensors WHERE kind='mps';
CREATE VIEW IF NOT EXISTS tt AS SELECT * FROM tensors WHERE kind='tt';
CREATE VIEW IF NOT EXISTS mpo AS SELECT * FROM tensors WHERE kind='mpo';
CREATE VIEW IF NOT EXISTS fold_children AS SELECT tenant_id,parent_id,id AS child_id FROM folds WHERE parent_id IS NOT NULL;
""" + FILE_REGISTRY_SCHEMA + KNOWLEDGE_SCHEMA


class OntologyStore:
    """Six-layer attested store. Callers must carry an explicit tenant id."""

    SCALE = 1_000_000_000

    def __init__(self, path: str | Path, integrity_key: bytes, *, custody: Any | None = None):
        if len(integrity_key) < 32:
            raise InvalidRecord("integrity_key must contain at least 32 bytes")
        self._key = bytes(integrity_key)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript(_SCHEMA)
        # The schema marker is promoted only after the v3 migration/projection
        # constructors complete. A failed legacy provenance migration therefore
        # cannot advertise a schema version the database did not finish.
        self.files = TheseusFileRegistry(self, custody=custody)
        self.knowledge = KnowledgeProjection(self, custody=custody)
        self._db.execute("INSERT OR REPLACE INTO metadata VALUES('schema_version','3')")

    def close(self) -> None:
        custody_close = getattr(self.files.custody, "close", None)
        if callable(custody_close):
            custody_close()
        self._db.close()

    def __enter__(self) -> "OntologyStore": return self
    def __exit__(self, *_: Any) -> None: self.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
            except Exception:
                self._db.rollback(); raise
            else:
                self._db.commit()

    def _tenant(self, tenant_id: str) -> sqlite3.Row:
        row = self._db.execute("SELECT * FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()
        if not row: raise AccessDenied("unknown or inaccessible tenant")
        return row

    def _reserve(self, db: sqlite3.Connection, tenant_id: str, records: int, blob_bytes: int, subject: str) -> None:
        row = db.execute("SELECT * FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()
        if not row: raise AccessDenied("unknown or inaccessible tenant")
        if row["used_records"] + records > row["max_records"] or row["used_blob_bytes"] + blob_bytes > row["max_blob_bytes"]:
            raise QuotaExceeded(f"quota exceeded while storing {subject}")
        db.execute("UPDATE tenants SET used_records=used_records+?,used_blob_bytes=used_blob_bytes+? WHERE tenant_id=?", (records, blob_bytes, tenant_id))
        db.execute("INSERT INTO quota_events(tenant_id,record_delta,byte_delta,subject,created_at) VALUES(?,?,?,?,?)", (tenant_id, records, blob_bytes, subject, _now()))

    def provision_client(self, namespace: str, quota: Quota, *, issuer: str = "hyba") -> Client:
        if not _NAMESPACE.fullmatch(namespace):
            raise InvalidRecord("namespace must be a 3-63 character lowercase slug")
        tenant_id = f"tenant_{uuid.uuid4().hex}"
        created = _now()
        with self._tx() as db:
            db.execute("INSERT INTO tenants(tenant_id,namespace,max_records,max_blob_bytes,created_at) VALUES(?,?,?,?,?)", (tenant_id, namespace, quota.max_records, quota.max_blob_bytes, created))
            root = self._attest(db, tenant_id, f"tenant:{namespace}", issuer, {"event":"provision"}, (), root=True)
            root_payload={"namespace":namespace}; root_betti=(1,)
            node_material=_json({"kind":NodeKind.GUARDIAN.value,"payload":root_payload,"betti":root_betti,"persistence":None,"created_at":created}).encode()
            node_id = _ident("node",node_material)
            db.execute("INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?)", (tenant_id,node_id,NodeKind.GUARDIAN.value,_json(root_payload),_json(root_betti),None,root.id,created))
            db.execute("UPDATE tenants SET root_attestation_id=?,root_node_id=? WHERE tenant_id=?", (root.id,node_id,tenant_id))
        return Client(tenant_id, namespace, quota, root.id, node_id, created)

    def get_client(self, tenant_id: str) -> Client:
        r = self._tenant(tenant_id)
        return Client(r["tenant_id"],r["namespace"],Quota(r["max_records"],r["max_blob_bytes"]),r["root_attestation_id"],r["root_node_id"],r["created_at"])

    def _attest(self, db: sqlite3.Connection, tenant_id: str, subject: str, issuer: str, details: dict[str,Any], evidence: Iterable[str], *, root: bool=False) -> Attestation:
        details_json = _json(details); timestamp = _now()
        head = db.execute("SELECT attestation_id FROM tenant_heads WHERE tenant_id=?", (tenant_id,)).fetchone()
        parents = [] if root else ([head[0]] if head else [])
        for parent in evidence:
            found = db.execute("SELECT 1 FROM attestations WHERE tenant_id=? AND id=?", (tenant_id,parent)).fetchone()
            if not found: raise AccessDenied("evidence attestation is outside tenant")
            if parent not in parents: parents.append(parent)
        seq = db.execute("SELECT COALESCE(MAX(sequence),-1)+1 FROM attestations WHERE tenant_id=?", (tenant_id,)).fetchone()[0]
        root_id = "pending" if root else db.execute("SELECT root_attestation_id FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()[0]
        material = _json({"tenant":tenant_id,"subject":subject,"issuer":issuer,"timestamp":timestamp,"sequence":seq,"parents":parents,"details":details}).encode()
        aid = _ident("att", material)
        if root: root_id = aid
        signature = hmac.new(self._key, aid.encode(), hashlib.sha256).hexdigest()
        db.execute("INSERT INTO attestations VALUES(?,?,?,?,?,?,?,?,?)", (tenant_id,aid,subject,issuer,signature,timestamp,seq,root_id,details_json))
        for ordinal,parent in enumerate(parents): db.execute("INSERT INTO attestation_parents VALUES(?,?,?,?)", (tenant_id,aid,parent,ordinal))
        if head: db.execute("UPDATE tenant_heads SET attestation_id=? WHERE tenant_id=?", (aid,tenant_id))
        else: db.execute("INSERT INTO tenant_heads VALUES(?,?)", (tenant_id,aid))
        return Attestation(aid,tenant_id,subject,issuer,signature,timestamp,seq,root_id,tuple(parents),details)

    def attest(self, tenant_id: str, subject: str, details: dict[str,Any], *, issuer: str="hyba", evidence: Sequence[str]=()) -> Attestation:
        self._tenant(tenant_id)
        with self._tx() as db: return self._attest(db,tenant_id,subject,issuer,details,evidence)

    def get_attestation(self, tenant_id: str, attestation_id: str) -> Attestation:
        self._tenant(tenant_id)
        r = self._db.execute("SELECT * FROM attestations WHERE tenant_id=? AND id=?",(tenant_id,attestation_id)).fetchone()
        if not r: raise AccessDenied("attestation not found in tenant")
        parents = tuple(x[0] for x in self._db.execute("SELECT parent_id FROM attestation_parents WHERE tenant_id=? AND child_id=? ORDER BY ordinal",(tenant_id,attestation_id)))
        return Attestation(r["id"],tenant_id,r["subject"],r["issuer"],r["signature"],r["timestamp"],r["sequence"],r["chain_root"],parents,_load(r["details_json"]))

    def verify_attestation(self, tenant_id: str, attestation_id: str) -> bool:
        root = self._tenant(tenant_id)["root_attestation_id"]
        visiting: set[str] = set()
        verified: set[str] = set()
        def visit(aid: str) -> None:
            if aid in verified: return
            if aid in visiting: raise IntegrityFailure("attestation cycle detected")
            visiting.add(aid); a = self.get_attestation(tenant_id,aid)
            material = _json({"tenant":tenant_id,"subject":a.subject,"issuer":a.issuer,"timestamp":a.timestamp,"sequence":a.sequence,"parents":list(a.parents),"details":a.details}).encode()
            if _ident("att",material) != a.id:
                raise IntegrityFailure("attestation content address mismatch")
            if a.chain_root != root or not hmac.compare_digest(a.signature,hmac.new(self._key,a.id.encode(),hashlib.sha256).hexdigest()):
                raise IntegrityFailure("attestation root or signature mismatch")
            if a.sequence == 0:
                if a.id != root or a.parents: raise IntegrityFailure("invalid root attestation")
            else:
                if not a.parents: raise IntegrityFailure("orphan attestation")
                for p in a.parents:
                    parent = self.get_attestation(tenant_id,p)
                    if parent.sequence >= a.sequence: raise IntegrityFailure("non-monotonic attestation parent")
                    visit(p)
            visiting.remove(aid); verified.add(aid)
        visit(attestation_id); return True

    @staticmethod
    def _pack_vector(vector: Sequence[float]) -> tuple[tuple[float,...],bytes]:
        if len(vector) != 11: raise InvalidRecord("fold vectors must contain exactly 11 components")
        values = tuple(float(x) for x in vector)
        if not all(math.isfinite(x) for x in values): raise InvalidRecord("fold vector must be finite")
        return values, struct.pack(">11d",*values)

    def write_fold(self, tenant_id: str, vector: Sequence[float], *, parent_id: str|None=None, issuer: str="hyba", evidence: Sequence[str]=()) -> FoldRecord:
        self._tenant(tenant_id); values, blob = self._pack_vector(vector)
        masks = tuple(_zeckendorf(round(x*self.SCALE)) for x in values)
        depth = max((abs(m).bit_length()-1 for m in masks if m), default=0)
        lucas = _lucas(depth); vector_digest = _sha(blob)
        cert_material = _json({"masks":masks,"vector_digest":vector_digest,"lucas":lucas,"depth":depth,"scale":self.SCALE}).encode()
        cert_digest = _sha(cert_material); cert_id = _ident("cert",cert_material)
        fold_material = blob + cert_id.encode() + (parent_id or "").encode(); fold_id = _ident("fold",fold_material); created=_now()
        with self._tx() as db:
            if parent_id and not db.execute("SELECT 1 FROM folds WHERE tenant_id=? AND id=?",(tenant_id,parent_id)).fetchone(): raise AccessDenied("parent fold not found in tenant")
            existing = db.execute("SELECT id FROM folds WHERE tenant_id=? AND id=?",(tenant_id,fold_id)).fetchone()
            if existing: return self.read_fold(tenant_id,fold_id)
            self._reserve(db,tenant_id,2,len(blob)+len(cert_material),fold_id)
            ca=self._attest(db,tenant_id,f"certificate:{cert_id}",issuer,{"digest":cert_digest},evidence)
            db.execute("INSERT INTO certificates VALUES(?,?,?,?,?,?,?,?,?)",(tenant_id,cert_id,_json(masks),cert_digest,vector_digest,_json(lucas),depth,self.SCALE,ca.id))
            fa=self._attest(db,tenant_id,f"fold:{fold_id}",issuer,{"certificate":cert_id,"parent":parent_id},(ca.id,*evidence))
            db.execute("INSERT INTO folds VALUES(?,?,?,?,?,?,?)",(tenant_id,fold_id,blob,cert_id,parent_id,created,fa.id))
        return self.read_fold(tenant_id,fold_id)

    def _certificate(self, tenant_id: str, cert_id: str) -> Certificate:
        r=self._db.execute("SELECT * FROM certificates WHERE tenant_id=? AND id=?",(tenant_id,cert_id)).fetchone()
        if not r: raise AccessDenied("certificate not found in tenant")
        return Certificate(r["id"],tenant_id,tuple(_load(r["masks_json"])),r["digest"],r["vector_digest"],tuple(_load(r["lucas_json"])),r["depth"],r["scale"],r["attestation_id"])

    def verify_certificate(self, tenant_id: str, certificate_id: str, vector: Sequence[float]|None=None) -> bool:
        c=self._certificate(tenant_id,certificate_id); self.verify_attestation(tenant_id,c.attestation_id)
        material=_json({"masks":c.masks,"vector_digest":c.vector_digest,"lucas":c.lucas,"depth":c.depth,"scale":c.scale}).encode()
        expected_depth=max((abs(m).bit_length()-1 for m in c.masks if m),default=0)
        if c.scale < 1 or c.depth != expected_depth or _sha(material)!=c.digest or _ident("cert",material)!=c.id or c.lucas!=_lucas(c.depth):
            raise IntegrityFailure("certificate digest, depth, scale or Lucas witness mismatch")
        integers=tuple(_zeckendorf_value(m) for m in c.masks)
        if len(integers)!=11: raise IntegrityFailure("certificate does not encode 11 dimensions")
        if vector is not None:
            values,blob=self._pack_vector(vector)
            if _sha(blob)!=c.vector_digest or integers!=tuple(round(x*c.scale) for x in values): raise IntegrityFailure("certificate replay mismatch")
        return True

    def read_fold(self, tenant_id: str, fold_id: str) -> FoldRecord:
        self._tenant(tenant_id); r=self._db.execute("SELECT * FROM folds WHERE tenant_id=? AND id=?",(tenant_id,fold_id)).fetchone()
        if not r: raise AccessDenied("fold not found in tenant")
        if len(r["vector"])!=88: raise IntegrityFailure("invalid fold vector encoding")
        vector=tuple(struct.unpack(">11d",r["vector"])); cert=self._certificate(tenant_id,r["certificate_id"])
        self.verify_attestation(tenant_id,r["attestation_id"]); self.verify_certificate(tenant_id,cert.id,vector)
        if _ident("fold",r["vector"]+cert.id.encode()+(r["parent_id"] or "").encode())!=r["id"]: raise IntegrityFailure("fold content address mismatch")
        return FoldRecord(r["id"],tenant_id,vector,cert,r["parent_id"],r["created_at"],r["attestation_id"])

    def children_of(self, tenant_id: str, fold_id: str) -> tuple[str,...]:
        self.read_fold(tenant_id,fold_id)
        return tuple(r[0] for r in self._db.execute("SELECT child_id FROM fold_children WHERE tenant_id=? AND parent_id=? ORDER BY child_id",(tenant_id,fold_id)))

    def write_physical_block(self, tenant_id: str, fibonacci_address: int, payload: bytes, fold_id: str, *, issuer: str="hyba") -> str:
        if fibonacci_address < 1: raise InvalidRecord("Fibonacci address must be positive")
        self.read_fold(tenant_id,fold_id); data=bytes(payload); digest=_sha(data)
        bid=_ident("block",f"{fibonacci_address}:{digest}:{fold_id}".encode()); created=_now()
        with self._tx() as db:
            self._reserve(db,tenant_id,1,len(data),bid)
            a=self._attest(db,tenant_id,f"block:{bid}",issuer,{"address":fibonacci_address,"digest":digest,"fold":fold_id},())
            db.execute("INSERT INTO physical_blocks VALUES(?,?,?,?,?,?,?,?)",(tenant_id,bid,fibonacci_address,data,digest,fold_id,a.id,created))
        return bid

    def read_physical_block(self, tenant_id: str, block_id: str) -> bytes:
        self._tenant(tenant_id); r=self._db.execute("SELECT * FROM physical_blocks WHERE tenant_id=? AND id=?",(tenant_id,block_id)).fetchone()
        if not r: raise AccessDenied("physical block not found in tenant")
        self.verify_attestation(tenant_id,r["attestation_id"])
        if _sha(r["payload"])!=r["digest"] or _ident("block",f"{r['fibonacci_address']}:{r['digest']}:{r['fold_id']}".encode())!=r["id"]:
            raise IntegrityFailure("physical block digest or content address mismatch")
        return bytes(r["payload"])

    def write_tensor(self, tenant_id: str, kind: str, fold_id: str, payload: bytes, *, format: str="application/octet-stream", dimensions: Sequence[int]=(), norm: float=0.0, entropy: float|None=None, trace: float|None=None, invariants: dict[str,Any]|None=None, issuer: str="hyba") -> TensorRecord:
        kind=str(kind).lower()
        if kind not in {"mps","tt","mpo"}: raise InvalidRecord("tensor kind must be mps, tt or mpo")
        dims=tuple(int(x) for x in dimensions)
        if any(x<1 for x in dims) or not math.isfinite(float(norm)): raise InvalidRecord("invalid tensor dimensions or norm")
        for x in (entropy,trace):
            if x is not None and not math.isfinite(float(x)): raise InvalidRecord("tensor metrics must be finite")
        self.read_fold(tenant_id,fold_id); data=bytes(payload); inv=invariants or {}; inv_json=_json(inv); digest=_sha(data)
        norm=float(norm); entropy=float(entropy) if entropy is not None else None; trace=float(trace) if trace is not None else None
        tid=_ident("tensor",_json({"kind":kind,"fold":fold_id,"digest":digest,"format":format,"dimensions":dims,"norm":norm,"entropy":entropy,"trace":trace,"invariants":inv}).encode()); created=_now()
        with self._tx() as db:
            self._reserve(db,tenant_id,1,len(data),tid)
            a=self._attest(db,tenant_id,f"tensor:{tid}",issuer,{"kind":kind,"digest":digest,"fold":fold_id},())
            db.execute("INSERT INTO tensors VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(tenant_id,tid,kind,fold_id,data,format,_json(dims),float(norm),entropy,trace,inv_json,digest,a.id,created))
        return self.read_tensor(tenant_id,tid)

    def read_tensor(self, tenant_id: str, tensor_id: str) -> TensorRecord:
        self._tenant(tenant_id); r=self._db.execute("SELECT * FROM tensors WHERE tenant_id=? AND id=?",(tenant_id,tensor_id)).fetchone()
        if not r: raise AccessDenied("tensor not found in tenant")
        self.verify_attestation(tenant_id,r["attestation_id"]); self.read_fold(tenant_id,r["fold_id"])
        material=_json({"kind":r["kind"],"fold":r["fold_id"],"digest":r["digest"],"format":r["format"],"dimensions":tuple(_load(r["dimensions_json"])),"norm":r["norm"],"entropy":r["entropy"],"trace":r["trace"],"invariants":_load(r["invariants_json"])}).encode()
        if _sha(r["payload"])!=r["digest"] or _ident("tensor",material)!=r["id"]:
            raise IntegrityFailure("tensor payload digest or content address mismatch")
        return TensorRecord(r["id"],tenant_id,r["kind"],r["fold_id"],bytes(r["payload"]),r["format"],tuple(_load(r["dimensions_json"])),r["norm"],r["entropy"],r["trace"],_load(r["invariants_json"]),r["digest"],r["attestation_id"],r["created_at"])

    def _node(self, tenant_id: str, node_id: str) -> NodeRecord:
        self._tenant(tenant_id); r=self._db.execute("SELECT * FROM nodes WHERE tenant_id=? AND id=?",(tenant_id,node_id)).fetchone()
        if not r: raise AccessDenied("node not found in tenant")
        self.verify_attestation(tenant_id,r["attestation_id"])
        payload=_load(r["payload_json"]); betti=tuple(_load(r["betti_json"])) if r["betti_json"] else None
        material=_json({"kind":r["kind"],"payload":payload,"betti":betti,"persistence":r["persistence"],"created_at":r["created_at"]}).encode()
        if _ident("node",material)!=r["id"]: raise IntegrityFailure("node content address mismatch")
        return NodeRecord(r["id"],tenant_id,r["kind"],payload,betti,r["persistence"],r["attestation_id"],r["created_at"])

    def add_node(self, tenant_id: str, kind: str|NodeKind, payload: dict[str,Any]|None=None, *, betti: Sequence[int]|None=None, persistence: float|None=None, connect_from: str|None=None, edge_kind: str|EdgeKind=EdgeKind.CONNECTS, issuer: str="hyba") -> NodeRecord:
        k=str(kind); k=k.split(".")[-1].lower() if k not in _KIND else k
        if k not in _KIND: raise InvalidRecord(f"unsupported node kind: {kind}")
        b=tuple(int(x) for x in betti) if betti is not None else None
        if b is not None and any(x<0 for x in b): raise InvalidRecord("Betti numbers cannot be negative")
        if persistence is not None and (not math.isfinite(persistence) or persistence<0): raise InvalidRecord("persistence must be finite and nonnegative")
        client=self.get_client(tenant_id); source=connect_from or client.root_node_id
        if source!=client.root_node_id: self._node(tenant_id,source)
        body=payload or {}; created=_now(); material=_json({"kind":k,"payload":body,"betti":b,"persistence":persistence,"created_at":created}).encode(); nid=_ident("node",material)
        with self._tx() as db:
            self._reserve(db,tenant_id,2,len(_json(body).encode()),nid)
            a=self._attest(db,tenant_id,f"node:{nid}",issuer,{"kind":k,"record_digest":_sha(material)},())
            db.execute("INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?)",(tenant_id,nid,k,_json(body),_json(b) if b is not None else None,persistence,a.id,created))
            self._add_edge_tx(db,tenant_id,source,nid,str(edge_kind),1.0,issuer,reserve=False)
        return self._node(tenant_id,nid)

    def _add_edge_tx(self, db: sqlite3.Connection, tenant_id: str, from_node: str, to_node: str, kind: str, weight: float, issuer: str, *, reserve: bool=True) -> str:
        kind=kind.split(".")[-1].lower() if kind not in _EDGE else kind
        if kind not in _EDGE or not math.isfinite(weight): raise InvalidRecord("unsupported edge kind or non-finite weight")
        for node in (from_node,to_node):
            if not db.execute("SELECT 1 FROM nodes WHERE tenant_id=? AND id=?",(tenant_id,node)).fetchone(): raise AccessDenied("edge endpoint not found in tenant")
        created=_now(); material=_json({"from":from_node,"to":to_node,"kind":kind,"weight":float(weight),"created_at":created}).encode(); eid=_ident("edge",material)
        if reserve: self._reserve(db,tenant_id,1,0,eid)
        a=self._attest(db,tenant_id,f"edge:{eid}",issuer,{"from":from_node,"to":to_node,"kind":kind,"record_digest":_sha(material)},())
        db.execute("INSERT INTO edges VALUES(?,?,?,?,?,?,?,?)",(tenant_id,eid,from_node,to_node,kind,float(weight),a.id,created))
        return eid

    def add_edge(self, tenant_id: str, from_node: str, to_node: str, kind: str|EdgeKind, *, weight: float=1.0, issuer: str="hyba") -> EdgeRecord:
        self._tenant(tenant_id)
        with self._tx() as db: eid=self._add_edge_tx(db,tenant_id,from_node,to_node,str(kind),weight,issuer)
        return self.get_edge(tenant_id,eid)

    def get_edge(self, tenant_id: str, edge_id: str) -> EdgeRecord:
        self._tenant(tenant_id); r=self._db.execute("SELECT * FROM edges WHERE tenant_id=? AND id=?",(tenant_id,edge_id)).fetchone()
        if not r: raise AccessDenied("edge not found in tenant")
        self.verify_attestation(tenant_id,r["attestation_id"])
        material=_json({"from":r["from_node"],"to":r["to_node"],"kind":r["kind"],"weight":r["weight"],"created_at":r["created_at"]}).encode()
        if _ident("edge",material)!=r["id"]: raise IntegrityFailure("edge content address mismatch")
        return EdgeRecord(r["id"],tenant_id,r["from_node"],r["to_node"],r["kind"],r["weight"],r["attestation_id"],r["created_at"])

    def traverse(self, tenant_id: str, start_node: str, *, max_depth: int=8, edge_kinds: Sequence[str]|None=None) -> tuple[NodeRecord,...]:
        self._node(tenant_id,start_node)
        allowed=set(edge_kinds) if edge_kinds else None; seen={start_node}; out=[]; queue=deque([(start_node,0)])
        while queue:
            node,depth=queue.popleft(); out.append(self._node(tenant_id,node))
            if depth>=max_depth: continue
            for r in self._db.execute("SELECT to_node,kind FROM edges WHERE tenant_id=? AND from_node=? ORDER BY id",(tenant_id,node)):
                if allowed is not None and r["kind"] not in allowed: continue
                if r["to_node"] not in seen: seen.add(r["to_node"]); queue.append((r["to_node"],depth+1))
        return tuple(out)

    def topology(self, tenant_id: str) -> dict[str,Any]:
        self._tenant(tenant_id)
        nodes=self._db.execute("SELECT COUNT(*) FROM nodes WHERE tenant_id=?",(tenant_id,)).fetchone()[0]
        edges=self._db.execute("SELECT COUNT(*) FROM edges WHERE tenant_id=?",(tenant_id,)).fetchone()[0]
        components=self._components(tenant_id)
        betti1=max(0,edges-nodes+components)
        persistence=[r[0] for r in self._db.execute("SELECT persistence FROM nodes WHERE tenant_id=? AND persistence IS NOT NULL",(tenant_id,))]
        return {"nodes":nodes,"edges":edges,"components":components,"betti":[components,betti1],"persistence":persistence}

    def _components(self, tenant_id: str) -> int:
        nodes={r[0] for r in self._db.execute("SELECT id FROM nodes WHERE tenant_id=?",(tenant_id,))}; adj={n:set() for n in nodes}
        for a,b in self._db.execute("SELECT from_node,to_node FROM edges WHERE tenant_id=?",(tenant_id,)): adj[a].add(b); adj[b].add(a)
        count=0
        while nodes:
            count+=1; stack=[nodes.pop()]
            while stack:
                for n in adj[stack.pop()] & nodes: nodes.remove(n); stack.append(n)
        return count

    def register_invariant(self, tenant_id: str, name: str, layer: int, statement: str, proof_status: str|ProofStatus, evidence_attestation_id: str, *, issuer: str="hyba") -> str:
        status=str(proof_status); status=status.split(".")[-1].lower() if status not in _STATUS else status
        if layer not in range(6) or status not in _STATUS: raise InvalidRecord("invalid invariant layer or proof status")
        self.get_attestation(tenant_id,evidence_attestation_id)
        iid=_ident("inv",f"{tenant_id}:{name}".encode()); created=_now()
        with self._tx() as db:
            self._reserve(db,tenant_id,1,len(statement.encode()),iid)
            a=self._attest(db,tenant_id,f"invariant:{name}",issuer,{"layer":layer,"status":status,"statement_digest":_sha(statement.encode()),"evidence":evidence_attestation_id},(evidence_attestation_id,))
            db.execute("INSERT INTO invariants VALUES(?,?,?,?,?,?,?,?,?)",(tenant_id,iid,name,layer,statement,status,evidence_attestation_id,a.id,created))
        return iid

    def query_by_invariant(self, tenant_id: str, name: str) -> dict[str,Any]:
        self._tenant(tenant_id); r=self._db.execute("SELECT * FROM invariants WHERE tenant_id=? AND name=?",(tenant_id,name)).fetchone()
        if not r: raise AccessDenied("invariant not found in tenant")
        self.verify_attestation(tenant_id,r["attestation_id"])
        details=self.get_attestation(tenant_id,r["attestation_id"]).details
        if details != {"layer":r["layer"],"status":r["proof_status"],"statement_digest":_sha(r["statement"].encode()),"evidence":r["evidence_attestation_id"]}:
            raise IntegrityFailure("invariant record mismatch")
        return dict(r)

    def register_contract(self, tenant_id: str, name: str, schema: dict[str,Any], invariant_ids: Sequence[str], *, issuer: str="hyba") -> str:
        for iid in invariant_ids:
            if not self._db.execute("SELECT 1 FROM invariants WHERE tenant_id=? AND id=?",(tenant_id,iid)).fetchone(): raise AccessDenied("contract invariant not found in tenant")
        cid=_ident("contract",f"{tenant_id}:{name}".encode()); payload=_json(schema); created=_now()
        with self._tx() as db:
            self._reserve(db,tenant_id,1,len(payload.encode()),cid)
            a=self._attest(db,tenant_id,f"contract:{name}",issuer,{"invariants":list(invariant_ids),"schema_digest":_sha(payload.encode())},())
            db.execute("INSERT INTO contracts VALUES(?,?,?,?,?,?,?)",(tenant_id,cid,name,payload,_json(tuple(invariant_ids)),a.id,created))
        return cid

    def register_term(self, tenant_id: str, term: str, definition: str, relations: dict[str,Any]|None=None, *, issuer: str="hyba") -> str:
        oid=_ident("term",f"{tenant_id}:{term}".encode()); rel=_json(relations or {}); created=_now()
        with self._tx() as db:
            self._reserve(db,tenant_id,1,len(definition.encode())+len(rel.encode()),oid)
            a=self._attest(db,tenant_id,f"ontology:{term}",issuer,{"term":term,"definition_digest":_sha(definition.encode()),"relations_digest":_sha(rel.encode())},())
            db.execute("INSERT INTO ontology VALUES(?,?,?,?,?,?,?)",(tenant_id,oid,term,definition,rel,a.id,created))
        return oid

    def materialize(self, tenant_id: str, operation: str, input_ids: Sequence[str], result: Any, *, issuer: str="hyba") -> str:
        result_json=_json(result); cid=_ident("computation",_json({"tenant":tenant_id,"operation":operation,"inputs":input_ids,"result":result,"nonce":uuid.uuid4().hex}).encode()); created=_now()
        with self._tx() as db:
            self._reserve(db,tenant_id,1,len(result_json.encode()),cid)
            a=self._attest(db,tenant_id,f"computation:{cid}",issuer,{"operation":operation,"inputs":list(input_ids),"result_digest":_sha(result_json.encode())},())
            db.execute("INSERT INTO computations VALUES(?,?,?,?,?,?,?)",(tenant_id,cid,operation,_json(tuple(input_ids)),result_json,a.id,created))
        return cid

    def store_pool_connection(self, tenant_id: str, endpoint: str, *, metadata: dict[str,Any]|None=None) -> NodeRecord:
        return self.add_node(tenant_id,NodeKind.POOL,{"endpoint":endpoint,**(metadata or {})})

    def store_job(self, tenant_id: str, pool_node_id: str, job_id: str, target: str, *, metadata: dict[str,Any]|None=None) -> NodeRecord:
        self._node(tenant_id,pool_node_id)
        return self.add_node(tenant_id,NodeKind.JOB,{"job_id":job_id,"target":target,**(metadata or {})},connect_from=pool_node_id,edge_kind=EdgeKind.DISPATCHES)

    def store_share(self, tenant_id: str, job_node_id: str, share_hash: str, vector: Sequence[float], *, nonce: int, accepted: bool=False, metadata: dict[str,Any]|None=None) -> NodeRecord:
        job=self._node(tenant_id,job_node_id); fold=self.write_fold(tenant_id,vector)
        share=self.add_node(tenant_id,NodeKind.SHARE,{"hash":share_hash.lower(),"nonce":nonce,"accepted":bool(accepted),"fold_id":fold.id,**(metadata or {})},connect_from=job.id,edge_kind=EdgeKind.SUBMITS)
        cert=self.add_node(tenant_id,NodeKind.CERTIFICATE,{"certificate_id":fold.certificate.id},connect_from=share.id,edge_kind=EdgeKind.CERTIFIES)
        if accepted: self.add_edge(tenant_id,job.id,share.id,EdgeKind.ACCEPTS)
        return share

    def find_shares(self, tenant_id: str, target: str) -> tuple[NodeRecord,...]:
        try: target_int=int(target,16)
        except ValueError as exc: raise InvalidRecord("target must be hexadecimal") from exc
        out=[]
        for r in self._db.execute("SELECT id,payload_json FROM nodes WHERE tenant_id=? AND kind=?",(tenant_id,NodeKind.SHARE.value)):
            payload=_load(r["payload_json"])
            try: value=int(payload["hash"],16)
            except (KeyError,ValueError,TypeError): continue
            if value<=target_int: out.append(self._node(tenant_id,r["id"]))
        return tuple(out)

    def pool_to_shares(self, tenant_id: str, pool_node_id: str, *, max_depth: int=8) -> tuple[NodeRecord,...]:
        return tuple(n for n in self.traverse(tenant_id,pool_node_id,max_depth=max_depth) if n.kind==NodeKind.SHARE.value)

    def verify_database(self, tenant_id: str|None=None, *, storage_roots: Mapping[str, str]|None=None) -> DatabaseVerification:
        errors=[]; tenants=[tenant_id] if tenant_id else [r[0] for r in self._db.execute("SELECT tenant_id FROM tenants")]
        fk=list(self._db.execute("PRAGMA foreign_key_check")); foreign_keys_ok=not fk
        if fk: errors.append(f"foreign key violations: {len(fk)}")
        attestations_ok=certificates_ok=fold_dag_ok=tenant_usage_ok=graph_connected=True
        for tid in tenants:
            try: self._tenant(tid)
            except AccessDenied as exc: errors.append(str(exc)); continue
            try:
                for r in self._db.execute("SELECT id FROM attestations WHERE tenant_id=?",(tid,)): self.verify_attestation(tid,r[0])
            except Exception as exc: attestations_ok=False; errors.append(f"{tid} attestations: {exc}")
            try:
                for r in self._db.execute("SELECT id FROM folds WHERE tenant_id=?",(tid,)): self.read_fold(tid,r[0])
            except Exception as exc: certificates_ok=False; errors.append(f"{tid} certificates: {exc}")
            try:
                for r in self._db.execute("SELECT id FROM physical_blocks WHERE tenant_id=?",(tid,)): self.read_physical_block(tid,r[0])
                for r in self._db.execute("SELECT id FROM tensors WHERE tenant_id=?",(tid,)): self.read_tensor(tid,r[0])
                for r in self._db.execute("SELECT id FROM nodes WHERE tenant_id=?",(tid,)): self._node(tid,r[0])
                for r in self._db.execute("SELECT id FROM edges WHERE tenant_id=?",(tid,)): self.get_edge(tid,r[0])
                for r in self._db.execute("SELECT name FROM invariants WHERE tenant_id=?",(tid,)): self.query_by_invariant(tid,r[0])
                for r in self._db.execute("SELECT * FROM contracts WHERE tenant_id=?",(tid,)):
                    details=self.get_attestation(tid,r["attestation_id"]).details
                    expected={"invariants":_load(r["invariant_ids_json"]),"schema_digest":_sha(r["schema_json"].encode())}
                    if details!=expected: raise IntegrityFailure(f"contract {r['id']} mismatch")
                for r in self._db.execute("SELECT * FROM ontology WHERE tenant_id=?",(tid,)):
                    details=self.get_attestation(tid,r["attestation_id"]).details
                    expected={"term":r["term"],"definition_digest":_sha(r["definition"].encode()),"relations_digest":_sha(r["relations_json"].encode())}
                    if details!=expected: raise IntegrityFailure(f"ontology term {r['id']} mismatch")
                for r in self._db.execute("SELECT * FROM computations WHERE tenant_id=?",(tid,)):
                    details=self.get_attestation(tid,r["attestation_id"]).details
                    expected={"operation":r["operation"],"inputs":_load(r["input_ids_json"]),"result_digest":_sha(r["result_json"].encode())}
                    if details!=expected: raise IntegrityFailure(f"computation {r['id']} mismatch")
            except Exception as exc:
                attestations_ok=False; errors.append(f"{tid} record integrity: {exc}")
            try:
                parents={r[0]:r[1] for r in self._db.execute("SELECT id,parent_id FROM folds WHERE tenant_id=?",(tid,))}
                for start in parents:
                    seen=set(); cur=start
                    while cur:
                        if cur in seen: raise IntegrityFailure("fold cycle")
                        seen.add(cur); cur=parents.get(cur)
            except Exception as exc: fold_dag_ok=False; errors.append(f"{tid} fold DAG: {exc}")
            row=self._db.execute("SELECT used_records,used_blob_bytes FROM tenants WHERE tenant_id=?",(tid,)).fetchone(); sums=self._db.execute("SELECT COALESCE(SUM(record_delta),0),COALESCE(SUM(byte_delta),0) FROM quota_events WHERE tenant_id=?",(tid,)).fetchone()
            if tuple(row)!=tuple(sums): tenant_usage_ok=False; errors.append(f"{tid} quota ledger mismatch")
            if self._components(tid)!=1: graph_connected=False; errors.append(f"{tid} graph is disconnected")
        file_report = self.files.verify_database(tenant_id)
        file_plane_ok = bool(file_report.get("passed"))
        if not file_plane_ok:
            errors.extend(str(item) for item in file_report.get("errors", ()))
        mining_chain_ok = self.files.verify_mining(tenant_id)
        if not mining_chain_ok:
            errors.append("mining lifecycle continuity failed")
        knowledge_report = self.knowledge.verify(tenant_id)
        knowledge_ok = bool(knowledge_report.get("passed"))
        if not knowledge_ok:
            errors.extend(str(item) for item in knowledge_report.get("errors", ()))
        # reconciliation_ok is computed, never assumed: True only when a
        # reconciliation ran against declared storage roots and reported zero
        # unresolved violations. Absent roots mean unreconciled, not healthy.
        reconciliation_ok = False
        if storage_roots:
            reconciliation_ok = True
            for tid, root in storage_roots.items():
                report = self.files.reconcile_files(tid, root)
                if not report.passed:
                    reconciliation_ok = False
                    for item in report.unresolved:
                        errors.append(f"reconciliation {tid}: {item}")
        return DatabaseVerification(
            foreign_keys_ok, attestations_ok, certificates_ok, fold_dag_ok,
            tenant_usage_ok, graph_connected, tuple(errors),
            file_plane_ok=file_plane_ok, mining_chain_ok=mining_chain_ok,
            reconciliation_ok=reconciliation_ok, knowledge_ok=knowledge_ok,
        )
