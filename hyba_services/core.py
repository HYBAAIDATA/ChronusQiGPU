"""Canonical object, policy, lineage and proof reference services."""

from __future__ import annotations
from dataclasses import dataclass, replace
import hashlib
import hmac
import json
import sqlite3
import time
import uuid
from typing import Any, Callable, Mapping, Protocol
from hyba_contracts import (
    BackendCertificate,
    EnterprisePolicyContext,
    FoldContract,
    PRIMEObjectV2,
    canonical_hash,
)


class MathBackend(Protocol):
    def fib_pair(self, n: int) -> tuple[int, int]: ...
    def lucas(self, n: int) -> int: ...
    def zeckendorf(self, n: int) -> Any: ...
    def nth_prime(self, n: int) -> int: ...
    def route(self, n: int) -> Any: ...
    def binet(self, n: int) -> Any: ...
    def transform(self, n: int) -> Any: ...
    def cassini(self, n: int) -> int: ...


class ObjectService:
    def __init__(
        self,
        math: MathBackend,
        folds: Mapping[str, FoldContract],
        lineage_head: Callable[[str, str], str],
    ):
        self.math = math
        self.folds = folds
        self.head = lineage_head

    def create(
        self, payload: Any, family: str, scale: int, tenant: str, instance: str
    ) -> PRIMEObjectV2:
        if scale < 1 or family not in self.folds:
            raise ValueError("unsupported family/scale")
        pair = self.math.fib_pair(scale)
        folded, residual = self.folds[family].encode(pair)
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        draft = PRIMEObjectV2(
            family,
            self.math.lucas(scale),
            folded,
            pair,
            self.math.zeckendorf(scale),
            self.math.binet(scale),
            self.math.nth_prime(scale),
            self.math.route(scale),
            self.math.transform(scale),
            self.math.cassini(scale),
            {"prev_hash": self.head(tenant, instance), "at": int(time.time())},
            "",
            tenant,
            instance,
            payload_hash,
            residual,
        )
        obj = replace(draft, object_id=canonical_hash(draft))
        obj.validate()
        return obj


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    checks: dict[str, bool]
    object_id: str
    at: int


class PolicyService:
    def evaluate(
        self, action: str, ctx: EnterprisePolicyContext, obj: PRIMEObjectV2
    ) -> PolicyDecision:
        checks = {
            "identity": bool(ctx.actor_principal),
            "tenant": ctx.tenant == obj.tenant,
            "instance": ctx.instance == obj.instance,
            "purpose": bool(ctx.purpose),
            "residency": bool(ctx.residency),
            "retention": bool(ctx.retention),
            "exactness": not ctx.exactness_required or obj.residual_boundary in (None, 0, "0"),
            "operator": ctx.operator_allowed,
            "reconstruction": ctx.reconstruction_allowed or action != "reconstruct",
            "export": ctx.export_allowed or action != "export",
        }
        return PolicyDecision(all(checks.values()), checks, obj.object_id, int(time.time()))


class LineageStore:
    def __init__(self, path: str, key: bytes):
        if len(key) < 32:
            raise ValueError("lineage key too short")
        self.key = key
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS lineage(tenant TEXT,instance TEXT,seq INTEGER,prev_hash TEXT,payload TEXT,at INTEGER,hash TEXT,signature TEXT,PRIMARY KEY(tenant,instance,seq))"
        )

    def head(self, tenant, instance):
        row = self.db.execute(
            "SELECT hash FROM lineage WHERE tenant=? AND instance=? ORDER BY seq DESC LIMIT 1",
            (tenant, instance),
        ).fetchone()
        return row[0] if row else "GENESIS"

    def append(self, tenant, instance, entry):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT seq,hash FROM lineage WHERE tenant=? AND instance=? ORDER BY seq DESC LIMIT 1",
                (tenant, instance),
            ).fetchone()
            seq = row[0] + 1 if row else 1
            prev = row[1] if row else "GENESIS"
            payload = json.dumps(entry, sort_keys=True, separators=(",", ":"), default=str)
            at = int(time.time())
            digest = hashlib.sha256(
                f"{tenant}|{instance}|{seq}|{prev}|{payload}|{at}".encode()
            ).hexdigest()
            sig = hmac.new(self.key, digest.encode(), hashlib.sha256).hexdigest()
            self.db.execute(
                "INSERT INTO lineage VALUES(?,?,?,?,?,?,?,?)",
                (tenant, instance, seq, prev, payload, at, digest, sig),
            )
            self.db.execute("COMMIT")
            return {"seq": seq, "prev_hash": prev, "hash": digest, "signature": sig}
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def close(self):
        self.db.close()


@dataclass(frozen=True)
class ProofObject:
    proof_id: str
    operator: str
    input_object_id: str
    output_object_id: str
    invariants_checked: tuple[str, ...]
    invariant_results: tuple[bool, ...]
    backend_certificate: BackendCertificate
    residual_bound: str
    replay_command: tuple[str, ...]
    signature: str


class ProofService:
    def __init__(self, key: bytes):
        if len(key) < 32:
            raise ValueError("proof key too short")
        self.key = key

    def certify(
        self,
        operator,
        input_obj,
        output_obj,
        invariants: Mapping[str, Callable[[Any, Any], bool]],
        backend,
    ):
        results = tuple(bool(fn(input_obj, output_obj)) for fn in invariants.values())
        if not all(results):
            raise ValueError("invariant failed")
        unsigned = {
            "proof_id": str(uuid.uuid4()),
            "operator": operator,
            "input_object_id": input_obj.object_id,
            "output_object_id": output_obj.object_id,
            "invariants_checked": tuple(invariants),
            "invariant_results": results,
            "backend_certificate": backend,
            "residual_bound": str(output_obj.residual_boundary),
            "replay_command": ("hyba-replay", input_obj.object_id, operator),
        }
        sig = hmac.new(
            self.key, json.dumps(unsigned, sort_keys=True, default=str).encode(), hashlib.sha256
        ).hexdigest()
        return ProofObject(**unsigned, signature=sig)
