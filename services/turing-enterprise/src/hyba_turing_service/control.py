"""Transactional pilot control plane. All entry points require signed authorization.

Authorities must implement AL HARAS SubscriptionAuthority.verify. Tokens are
verified on every call, including reads and idempotent retries. No signing keys,
HTTP server, payment rates, physical provisioning or alternate VQC live here.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import sqlite3
import time
from typing import Any, Callable, Protocol


class Denied(PermissionError):
    pass


class Conflict(ValueError):
    pass


class Unavailable(RuntimeError):
    pass


class Authority(Protocol):
    def verify(
        self, token: str, *, tenant_id: str, actor: str, capability: str, now: int
    ) -> Any: ...


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def text(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError("non-empty identifier up to 256 characters required")
    return value


def integer(value: int, minimum: int = 1, maximum: int = 2**31 - 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("integer outside admitted range")
    return value


DDL = """
CREATE TABLE IF NOT EXISTS customers (
 tenant TEXT PRIMARY KEY, billing_account TEXT NOT NULL, contract TEXT NOT NULL,
 approval TEXT NOT NULL, starts INTEGER NOT NULL, expires INTEGER NOT NULL,
 contracted INTEGER NOT NULL CHECK(contracted > 0),
 allowance INTEGER NOT NULL CHECK(allowance > 0),
 allocated INTEGER NOT NULL CHECK(allocated >= 0 AND allocated <= contracted),
 state TEXT NOT NULL CHECK(state IN ('pending','active','suspended','retired')));
CREATE TABLE IF NOT EXISTS jobs (
 tenant TEXT NOT NULL REFERENCES customers(tenant), job TEXT NOT NULL,
 actor TEXT NOT NULL, request TEXT NOT NULL, request_hash TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN
 ('admitted','running','completed','failed','cancelled','unknown')),
 report TEXT, contract TEXT, PRIMARY KEY(tenant,job));
CREATE TABLE IF NOT EXISTS consumed_tokens (
 namespace TEXT NOT NULL, nonce TEXT NOT NULL, expires INTEGER NOT NULL,
 PRIMARY KEY(namespace,nonce));
CREATE TABLE IF NOT EXISTS commands (
 command TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, response TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS usage (
 event TEXT PRIMARY KEY, tenant TEXT NOT NULL, job TEXT NOT NULL,
 payload TEXT NOT NULL, UNIQUE(tenant,job),
 FOREIGN KEY(tenant,job) REFERENCES jobs(tenant,job));
CREATE TABLE IF NOT EXISTS delivery (
 event TEXT PRIMARY KEY REFERENCES usage(event), receipt TEXT);
CREATE TABLE IF NOT EXISTS audit (
 seq INTEGER PRIMARY KEY, payload TEXT NOT NULL, previous TEXT NOT NULL,
 hash TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS usage_no_update BEFORE UPDATE ON usage
 BEGIN SELECT RAISE(ABORT,'usage is append-only'); END;
CREATE TRIGGER IF NOT EXISTS usage_no_delete BEFORE DELETE ON usage
 BEGIN SELECT RAISE(ABORT,'usage is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
 BEGIN SELECT RAISE(ABORT,'audit is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
 BEGIN SELECT RAISE(ABORT,'audit is append-only'); END;
"""


class ControlPlane:
    """One SQLite connection per worker; BEGIN IMMEDIATE serializes admissions.

    `operator_authority` must be separately configured from customer issuance.
    `clock` is a trusted server clock, never a caller-supplied request field.
    The DB and adapters are privileged process dependencies, not user inputs.
    """

    def __init__(
        self,
        path: str,
        *,
        customer_authority: Authority,
        operator_authority: Authority,
        clock: Callable[[], int] | None = None,
        capacity_slots: int | None = None,
    ):
        self.capacity_slots = integer(capacity_slots) if capacity_slots is not None else None
        self.project_context = None
        self.customer_authority = customer_authority
        self.operator_authority = operator_authority
        self.clock = clock or (lambda: int(time.time()))
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2):
            self.db.close()
            raise Unavailable("unsupported control-plane schema")
        self.db.executescript(DDL)
        columns = {r[1] for r in self.db.execute("PRAGMA table_info(jobs)")}
        if "contract" not in columns:
            with self._transaction():
                self.db.execute("ALTER TABLE jobs ADD COLUMN contract TEXT")
                self.db.execute(
                    "UPDATE jobs SET contract=(SELECT contract FROM customers c WHERE c.tenant=jobs.tenant)"
                )
        self.db.execute("PRAGMA user_version=2")

    def close(self):
        self.db.close()

    def _authorize(self, token, actor, tenant, capability, *, operator=False):
        text(actor)
        text(tenant)
        authority = self.operator_authority if operator else self.customer_authority
        if authority is None:
            raise Unavailable("authorization authority unavailable")
        try:
            claims = authority.verify(
                token,
                tenant_id="__service_ops__" if operator else tenant,
                actor=actor,
                capability=capability,
                now=self.clock(),
            )
            if getattr(claims, "jti", None) is not None:
                namespace = canonical([claims.issuer, claims.key_id, claims.tenant_id])
                with self._transaction():
                    self.db.execute("DELETE FROM consumed_tokens WHERE expires<=?", (self.clock(),))
                    self.db.execute(
                        "INSERT INTO consumed_tokens VALUES(?,?,?)",
                        (namespace, claims.jti, claims.expires_at),
                    )
            return claims
        except Exception as exc:
            raise Denied("authorization denied") from exc

    @contextmanager
    def _transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _audit(self, tenant, actor, action, detail):
        row = self.db.execute("SELECT seq,hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        seq, previous = (row["seq"] + 1, row["hash"]) if row else (1, "GENESIS")
        payload = canonical(
            dict(tenant=tenant, actor=actor, action=action, at=self.clock(), detail=detail)
        )
        checksum = digest([seq, previous, payload])
        self.db.execute("INSERT INTO audit VALUES(?,?,?,?)", (seq, payload, previous, checksum))

    def _customer(self, tenant, *, active=False):
        row = self.db.execute("SELECT * FROM customers WHERE tenant=?", (tenant,)).fetchone()
        if row is None:
            raise Denied("customer unavailable")
        if active and (
            row["state"] != "active" or not row["starts"] <= self.clock() < row["expires"]
        ):
            raise Denied("service not active within contract window")
        return row

    def _job(self, tenant, job):
        row = self.db.execute(
            "SELECT * FROM jobs WHERE tenant=? AND job=?", (tenant, job)
        ).fetchone()
        if row is None:
            raise Denied("job unavailable")
        return row

    def approve_customer(
        self,
        token,
        actor,
        *,
        tenant,
        billing_account,
        contract,
        approval,
        starts,
        expires,
        contracted,
        allowance,
        command,
    ):
        """Record operator-attested commercial approval; allocate nothing yet.

        The approval reference must be resolved to the approved commercial record
        by the operator workflow. It is not an electronic contract signature.
        """
        self._authorize(token, actor, tenant, "turing.ops.manage", operator=True)
        payload = dict(
            tenant=text(tenant),
            billing_account=text(billing_account),
            contract=text(contract),
            approval=text(approval),
            starts=integer(starts, 0),
            expires=integer(expires),
            contracted=integer(contracted),
            allowance=integer(allowance),
        )
        if expires <= starts:
            raise ValueError("invalid contract window")
        return self._command(
            actor,
            tenant,
            command,
            "approve",
            payload,
            lambda: self.db.execute(
                "INSERT INTO customers VALUES(?,?,?,?,?,?,?,?,0,'pending')", tuple(payload.values())
            ),
        )

    def _command(self, actor, tenant, command, action, payload, apply):
        key = text(command)
        checksum = digest([actor, tenant, action, payload])
        with self._transaction():
            row = self.db.execute("SELECT * FROM commands WHERE command=?", (key,)).fetchone()
            if row:
                if row["payload_hash"] != checksum:
                    raise Conflict("idempotency key reused with different command")
                return json.loads(row["response"])
            apply()
            response = dict(command=key, tenant=tenant, action=action)
            self._audit(tenant, actor, action, payload)
            self.db.execute(
                "INSERT INTO commands VALUES(?,?,?)", (key, checksum, canonical(response))
            )
            return response

    def provision(self, token, actor, *, tenant, slots, command):
        """Set a logical concurrency reservation, NOT deploy a runtime/VM."""
        self._authorize(token, actor, tenant, "turing.ops.manage", operator=True)
        integer(slots)

        def apply():
            c = self._customer(tenant)
            if c["state"] == "retired" or not c["starts"] <= self.clock() < c["expires"]:
                raise Denied("contract not provisionable")
            running = self.db.execute(
                "SELECT COUNT(*) FROM jobs WHERE tenant=? AND state IN ('admitted','running','unknown')",
                (tenant,),
            ).fetchone()[0]
            if slots > c["contracted"] or slots < running:
                raise Conflict("reservation outside contracted/in-flight capacity")
            if self.capacity_slots is not None:
                total = self.db.execute(
                    "SELECT COALESCE(SUM(allocated),0) FROM customers"
                ).fetchone()[0]
                if total - c["allocated"] + slots > self.capacity_slots:
                    raise Conflict("global configured slot capacity exhausted")
            self._before_provision(tenant, slots)
            self.db.execute(
                "UPDATE customers SET allocated=?,state='active' WHERE tenant=?", (slots, tenant)
            )

        return self._command(actor, tenant, command, "provision", dict(slots=slots), apply)

    def lifecycle(self, token, actor, *, tenant, state, reason, command):
        self._authorize(token, actor, tenant, "turing.ops.manage", operator=True)
        text(reason)
        if state not in {"suspended", "active", "retired"}:
            raise ValueError("unsupported state")

        def apply():
            c = self._customer(tenant)
            edges = {
                "pending": {"suspended", "retired"},
                "active": {"suspended", "retired"},
                "suspended": {"active", "retired"},
                "retired": set(),
            }
            if state not in edges[c["state"]]:
                raise Conflict("invalid lifecycle transition")
            if state == "active" and (
                not c["allocated"] or not c["starts"] <= self.clock() < c["expires"]
            ):
                raise Denied("activation requires valid reserved contract")
            if state == "retired":
                n = self.db.execute(
                    "SELECT COUNT(*) FROM jobs WHERE tenant=? AND state IN ('admitted','running','unknown')",
                    (tenant,),
                ).fetchone()[0]
                if n:
                    raise Conflict("drain jobs before retirement")
            self.db.execute(
                "UPDATE customers SET state=?,allocated=? WHERE tenant=?",
                (state, 0 if state == "retired" else c["allocated"], tenant),
            )

        return self._command(
            actor, tenant, command, "lifecycle", dict(state=state, reason=reason), apply
        )

    @staticmethod
    def _request(request):
        if not isinstance(request, dict) or set(request) - {"qasm", "shots", "seed"}:
            raise ValueError("only qasm/shots/seed are admitted")
        qasm = request.get("qasm")
        if not isinstance(qasm, str) or not qasm.strip() or len(qasm.encode()) > 65536:
            raise ValueError("QASM required, at most 64 KiB")
        if request.get("shots") is not None:
            integer(request["shots"], 1, 1_000_000)
        if request.get("seed") is not None:
            integer(request["seed"], 0)
        return json.loads(canonical(request))

    def submit(self, token, actor, *, tenant, job, request):
        claims = self._authorize(token, actor, tenant, "turing.jobs.submit")
        return self._submit_authorized(claims, actor, tenant=tenant, job=job, request=request)

    def _submit_authorized(self, claims, actor, *, tenant, job, request):
        text(job)
        request = self._request(request)
        if len(canonical(request).encode()) > claims.max_payload_bytes:
            raise Denied("subscription payload limit exceeded")
        checksum = digest(
            [actor, request]
            if self.project_context is None
            else [actor, request, self.project_context]
        )
        with self._transaction():
            c = self._customer(tenant, active=True)
            existing = self.db.execute(
                "SELECT * FROM jobs WHERE tenant=? AND job=?", (tenant, job)
            ).fetchone()
            if existing:
                if existing["request_hash"] != checksum:
                    raise Conflict("job key reused with different request or actor")
                return dict(job=job, state=existing["state"])
            counts = dict(
                self.db.execute(
                    "SELECT state,COUNT(*) FROM jobs WHERE tenant=? AND contract=? GROUP BY state",
                    (tenant, c["contract"]),
                )
            )
            inflight = sum(counts.get(s, 0) for s in ("admitted", "running", "unknown"))
            if inflight >= c["allocated"]:
                raise Conflict("reserved concurrency exhausted")
            if inflight + counts.get("completed", 0) >= c["allowance"]:
                raise Conflict("contract completion allowance exhausted")
            self._before_admit(tenant, actor, job)
            self.db.execute(
                "INSERT INTO jobs(tenant,job,actor,request,request_hash,state,report,contract) VALUES(?,?,?,?,?,'admitted',NULL,?)",
                (tenant, job, actor, canonical(request), checksum, c["contract"]),
            )
            self._audit(tenant, actor, "admit", dict(job=job, request_hash=checksum))
            return dict(job=job, state="admitted")

    def _before_provision(self, tenant, slots):
        """Transactional shared-policy hook for department/project reservations."""

    def _before_admit(self, tenant, actor, job):
        """Transactional policy hook; overridden by enterprise project policy."""

    def _before_dispatch(self, tenant, actor, job):
        """Transactional current-membership/revocation hook."""

    def cancel(self, token, actor, *, tenant, job):
        self._authorize(token, actor, tenant, "turing.jobs.submit")
        with self._transaction():
            row = self._job(tenant, job)
            if row["actor"] != actor:
                raise Denied("only submitting actor may cancel")
            if row["state"] == "cancelled":
                return
            if row["state"] != "admitted":
                raise Conflict("only undispatched jobs can be cancelled")
            self.db.execute(
                "UPDATE jobs SET state='cancelled' WHERE tenant=? AND job=?", (tenant, job)
            )
            self._audit(tenant, actor, "cancel", dict(job=job))

    def execute(self, token, actor, *, tenant, job, runtime):
        """Worker-only dispatch; runtime is injected trusted process configuration.

        A crash after the running commit NEVER auto-reexecutes. Reconciliation
        exposes it for operator investigation. This avoids duplicate external
        executions while honestly declining an exactly-once execution claim.
        """
        self._authorize(token, actor, tenant, "turing.ops.execute", operator=True)
        if runtime is None:
            raise Unavailable("runtime adapter unavailable")
        with self._transaction():
            self._customer(tenant, active=True)
            row = self._job(tenant, job)
            if row["state"] == "completed":
                return json.loads(row["report"])
            if row["state"] != "admitted":
                raise Conflict("job is not undispatched; investigate, do not retry execution")
            self._before_dispatch(tenant, row["actor"], job)
            self.db.execute(
                "UPDATE jobs SET state='running' WHERE tenant=? AND job=?", (tenant, job)
            )
            self._audit(tenant, actor, "dispatch", dict(job=job))
            request = json.loads(row["request"])
        # No database transaction is held over external execution.
        try:
            report = json.loads(canonical(runtime.run(request)))
            if not isinstance(report, dict):
                raise ValueError("runtime returned no report")
        except Exception:
            with self._transaction():
                self.db.execute(
                    "UPDATE jobs SET state='unknown' WHERE tenant=? AND job=? AND state='running'",
                    (tenant, job),
                )
                self._audit(tenant, actor, "execution_unknown", dict(job=job))
            raise Unavailable("execution outcome unknown; reconcile before release") from None
        return self._complete_report(actor, tenant=tenant, job=job, report=report)

    def _complete_report(
        self,
        actor,
        *,
        tenant,
        job,
        report,
        expected_states=("running",),
        expected_request_hash=None,
        recovery_reason=None,
    ):
        raw_stages = report.get("stages")
        stages = {}
        if isinstance(raw_stages, list):
            for stage in raw_stages:
                if isinstance(stage, dict) and isinstance(stage.get("stage"), str):
                    name = stage["stage"]
                    if name in stages:
                        stages[name] = "DUPLICATE"
                    else:
                        stages[name] = stage.get("state")
        passed = (
            report.get("schema") == "turing.vqc.pipeline_report.v1"
            and report.get("verdict") == "PASS"
            and stages.get("execution") == "PASS"
            and stages.get("verification") == "PASS"
            and isinstance(report.get("program_digest"), str)
            and bool(report["program_digest"])
            and isinstance(report.get("certificate"), dict)
            and bool(report["certificate"])
            and isinstance(report.get("witness"), dict)
            and bool(report["witness"])
        )
        with self._transaction():
            # Trusted adapter owns certificate verification; this is a transport
            # admission check, not an independent mathematical proof verifier.
            c = self._customer(tenant)
            row = self._job(tenant, job)
            if expected_request_hash is not None and row["request_hash"] != expected_request_hash:
                raise Conflict("admission identity changed during recovery")
            if row["state"] == "completed" and expected_request_hash is not None:
                if row["report"] != canonical(report):
                    raise Conflict("completed report conflicts with recovery evidence")
                return json.loads(row["report"])
            if row["state"] not in expected_states:
                raise Conflict(
                    "execution was fenced by operator resolution; recover evidence manually"
                )
            self.db.execute(
                "UPDATE jobs SET state=?,report=? WHERE tenant=? AND job=?",
                ("completed" if passed else "failed", canonical(report), tenant, job),
            )
            if passed:
                event = digest(["turing.usage.v1", tenant, job])
                payload = dict(
                    schema="turing.usage.v1",
                    event_id=event,
                    tenant=tenant,
                    job=job,
                    contract=c["contract"],
                    billing_account=c["billing_account"],
                    unit="verified_execution.v1",
                    billing_scope="deferred",
                    chargeable=False,
                    quantity=1,
                    occurred_at=self.clock(),
                    program_digest=report["program_digest"],
                    report_digest=digest(report),
                )
                payload.update(self._usage_details(tenant, job))
                if recovery_reason is not None:
                    payload.update(
                        recovered=True,
                        recovered_at=self.clock(),
                        execution_time_source="not_established_by_service_receipt",
                    )
                self.db.execute(
                    "INSERT INTO usage VALUES(?,?,?,?)", (event, tenant, job, canonical(payload))
                )
                self.db.execute("INSERT INTO delivery(event) VALUES(?)", (event,))
            self._audit(
                tenant,
                actor,
                (
                    ("recover_complete" if passed else "recover_fail")
                    if recovery_reason is not None
                    else ("complete" if passed else "fail")
                ),
                dict(
                    job=job,
                    digest=digest(report),
                    **({"reason": recovery_reason} if recovery_reason is not None else {}),
                ),
            )
        return report

    def _usage_details(self, tenant, job):
        return {}

    def recover_result(self, token, actor, *, tenant, job, reason, source):
        """Operator-only recovery of an authenticated durable service report.

        Does not execute work, infer an exactly-once computation guarantee or
        claim shared THESEUS semantic replay. Unsigned legacy files stay closed.
        """
        self._authorize(token, actor, tenant, "turing.ops.manage", operator=True)
        text(reason)
        if source is None:
            raise Unavailable("recovery source is not configured")
        with self._transaction():
            row = dict(self._job(tenant, job))
            if row["state"] not in {"running", "unknown", "completed"}:
                raise Conflict("job is not eligible for result recovery")
        report = source.recover(
            tenant, job, json.loads(row["request"]), admission_hash=row["request_hash"]
        )
        report = json.loads(canonical(report))
        if not isinstance(report, dict):
            raise Unavailable("recovery source returned no report")
        return self._complete_report(
            actor,
            tenant=tenant,
            job=job,
            report=report,
            expected_states=("running", "unknown"),
            expected_request_hash=row["request_hash"],
            recovery_reason=reason,
        )

    def resolve_unknown(self, token, actor, *, tenant, job, reason):
        """Release a quarantined job only after operator investigation.

        No usage is inferred and no success fabricated. Authenticated retained
        service reports may instead use recover_result; billing stays deferred.
        """
        self._authorize(token, actor, tenant, "turing.ops.manage", operator=True)
        text(reason)
        with self._transaction():
            row = self._job(tenant, job)
            if row["state"] not in {"running", "unknown"}:
                raise Conflict("job is not unresolved")
            self.db.execute(
                "UPDATE jobs SET state='failed' WHERE tenant=? AND job=?", (tenant, job)
            )
            self._audit(tenant, actor, "resolve_without_billing", dict(job=job, reason=reason))

    def overview(self, token, actor, *, tenant):
        self._authorize(token, actor, tenant, "turing.customer.read")
        with self._transaction():
            c = self._customer(tenant)
            counts = dict(
                self.db.execute(
                    "SELECT state,COUNT(*) FROM jobs WHERE tenant=? AND contract=? GROUP BY state",
                    (tenant, c["contract"]),
                )
            )
            busy = sum(counts.get(s, 0) for s in ("admitted", "running", "unknown"))
            return dict(
                tenant=tenant,
                state=c["state"],
                contracted=c["contracted"],
                allocated=c["allocated"],
                available=c["allocated"] - busy,
                in_flight=busy,
                consumed=counts.get("completed", 0),
                allowance=c["allowance"],
                expires=c["expires"],
            )

    def job(self, token, actor, *, tenant, job):
        self._authorize(token, actor, tenant, "turing.customer.read")
        row = self._job(tenant, job)
        return dict(
            job=job, state=row["state"], report=json.loads(row["report"]) if row["report"] else None
        )

    def usage(self, token, actor, *, tenant):
        self._authorize(token, actor, tenant, "turing.customer.read")
        return [
            json.loads(r[0])
            for r in self.db.execute(
                "SELECT payload FROM usage WHERE tenant=? ORDER BY event", (tenant,)
            )
        ]

    def audit(self, token, actor, *, tenant):
        self._authorize(token, actor, tenant, "turing.customer.read")
        # Do not expose global sequence/hash links or another tenant's events.
        return [
            p
            for r in self.db.execute("SELECT payload FROM audit ORDER BY seq")
            if (p := json.loads(r[0]))["tenant"] == tenant
        ]

    def reconcile(self, token, actor):
        self._authorize(token, actor, "__service_ops__", "turing.ops.manage", operator=True)
        issues = []
        for row in self.db.execute(
            "SELECT tenant,job,state FROM jobs WHERE state IN ('running','unknown')"
        ):
            issues.append(dict(row))
        previous = "GENESIS"
        expected_seq = 1
        for row in self.db.execute("SELECT * FROM audit ORDER BY seq"):
            if (
                row["seq"] != expected_seq
                or row["previous"] != previous
                or row["hash"] != digest([row["seq"], previous, row["payload"]])
            ):
                issues.append(dict(kind="audit_integrity"))
                break
            expected_seq += 1
            previous = row["hash"]
        for row in self.db.execute(
            "SELECT j.tenant,j.job FROM jobs j LEFT JOIN usage u ON j.tenant=u.tenant AND j.job=u.job "
            "WHERE (j.state='completed' AND u.event IS NULL) OR (j.state!='completed' AND u.event IS NOT NULL)"
        ):
            issues.append(dict(kind="usage_mismatch", **dict(row)))
        return dict(
            issues=issues,
            pending_billing=self.db.execute(
                "SELECT COUNT(*) FROM delivery WHERE receipt IS NULL"
            ).fetchone()[0],
        )

    def deliver_usage(self, token, actor, *, sink, limit=100):
        """At-least-once delivery. Receiver MUST deduplicate event_id atomically.

        A receipt is an import acknowledgement, NOT an invoice/payment. No
        production Hermitten transport is assumed; a missing sink fails closed.
        """
        self._authorize(token, actor, "__service_ops__", "turing.ops.billing", operator=True)
        integer(limit, 1, 1000)
        if sink is None:
            raise Unavailable("usage sink is not configured")
        rows = self.db.execute(
            "SELECT u.event,u.tenant,u.payload FROM usage u JOIN delivery d ON u.event=d.event "
            "WHERE d.receipt IS NULL ORDER BY u.event LIMIT ?",
            (limit,),
        ).fetchall()
        delivered = 0
        for row in rows:
            receipt = sink.accept_usage(json.loads(row["payload"]), idempotency_key=row["event"])
            # Receipt must echo identity, preventing a wrong-event acknowledgement.
            if (
                not isinstance(receipt, dict)
                or receipt.get("event_id") != row["event"]
                or not isinstance(receipt.get("receipt_id"), str)
                or not receipt["receipt_id"]
            ):
                raise Unavailable("invalid usage import acknowledgement")
            with self._transaction():
                updated = self.db.execute(
                    "UPDATE delivery SET receipt=? WHERE event=? AND receipt IS NULL",
                    (canonical(receipt), row["event"]),
                ).rowcount
                if updated:
                    self._audit(row["tenant"], actor, "usage_import_ack", receipt)
                    delivered += 1
        return delivered
