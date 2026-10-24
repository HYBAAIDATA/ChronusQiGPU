"""Membership, projects, renewal and commercial events around the core owner."""

from __future__ import annotations

import json

from .control import ControlPlane, Conflict, Denied, canonical, digest, integer, text

TABLES = """
CREATE TABLE IF NOT EXISTS members (
 tenant TEXT NOT NULL, actor TEXT NOT NULL, role TEXT NOT NULL,
 active INTEGER NOT NULL, PRIMARY KEY(tenant,actor));
CREATE TABLE IF NOT EXISTS projects (
 tenant TEXT NOT NULL, project TEXT NOT NULL, slots INTEGER NOT NULL,
 allowance INTEGER NOT NULL, active INTEGER NOT NULL, PRIMARY KEY(tenant,project));
CREATE TABLE IF NOT EXISTS project_members (
 tenant TEXT NOT NULL, project TEXT NOT NULL, actor TEXT NOT NULL,
 PRIMARY KEY(tenant,project,actor));
CREATE TABLE IF NOT EXISTS job_projects (
 tenant TEXT NOT NULL, job TEXT NOT NULL, project TEXT NOT NULL, PRIMARY KEY(tenant,job));
CREATE TABLE IF NOT EXISTS cancellation (
 tenant TEXT NOT NULL, job TEXT NOT NULL, actor TEXT NOT NULL, PRIMARY KEY(tenant,job));
CREATE TABLE IF NOT EXISTS commercial_events (
 event TEXT PRIMARY KEY, tenant TEXT NOT NULL, payload TEXT NOT NULL, receipt TEXT);
CREATE TABLE IF NOT EXISTS contract_history (
 tenant TEXT NOT NULL, contract TEXT NOT NULL, snapshot TEXT NOT NULL, PRIMARY KEY(tenant,contract));
CREATE TABLE IF NOT EXISTS spend_intents (
 tenant TEXT NOT NULL,job TEXT NOT NULL,request_hash TEXT NOT NULL,
 authorization TEXT,state TEXT NOT NULL,PRIMARY KEY(tenant,job));
CREATE TABLE IF NOT EXISTS retirement (
 tenant TEXT PRIMARY KEY,purge_after INTEGER NOT NULL,purged INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS approval_records (
 approval TEXT PRIMARY KEY, tenant TEXT NOT NULL, contract TEXT NOT NULL,
 terms_hash TEXT NOT NULL, approved_by TEXT NOT NULL, expires INTEGER NOT NULL);
CREATE TRIGGER IF NOT EXISTS commercial_payload_immutable BEFORE UPDATE OF payload ON commercial_events
 BEGIN SELECT RAISE(ABORT,'commercial events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS commercial_no_delete BEFORE DELETE ON commercial_events
 BEGIN SELECT RAISE(ABORT,'commercial events are append-only'); END;
"""

ROLES = {
    "viewer": {"turing.customer.read"},
    "analyst": {"turing.customer.read", "turing.jobs.submit"},
    "admin": {"turing.customer.read", "turing.jobs.submit", "turing.customer.admin"},
}


class MembershipAuthority:
    """Re-check active membership on every signed-capability verification."""

    def __init__(self, authority, plane):
        self.authority = authority
        self.plane = plane

    def verify(self, token, **kwargs):
        claims = self.authority.verify(token, **kwargs)
        self.plane.require_member(kwargs["tenant_id"], kwargs["actor"], kwargs["capability"])
        return claims


class EnterprisePlane(ControlPlane):
    def __init__(
        self,
        *args,
        enforce_membership=True,
        retention_seconds=90 * 86400,
        require_spend=False,
        **kwargs,
    ):
        self.require_spend = require_spend
        self.retention_seconds = integer(retention_seconds, 0)
        super().__init__(*args, **kwargs)
        self.db.executescript(TABLES)
        if enforce_membership:
            self.customer_authority = MembershipAuthority(self.customer_authority, self)

    def activation_status(self, token, actor, *, tenant, project, job=None):
        """Authorized point-in-time first-outcome view; never provisions or executes.

        Completion facts are service envelope acceptance, not independent proof of
        mathematics, customer acceptance, business value or deployment readiness.
        This uses the same tenant/project/membership boundary as ordinary work.
        """
        self._authorize(token, actor, tenant, "turing.customer.read")
        text(project)
        if job is not None:
            text(job)
        with self._transaction():
            now = self.clock()
            c = self._customer(tenant)
            p = self._project_access(tenant, actor, project)
            self.require_member(tenant, actor, "turing.jobs.submit")
            rows = self.db.execute(
                "SELECT state,COUNT(*) AS n FROM jobs WHERE tenant=? AND contract=? GROUP BY state",
                (tenant, c["contract"]),
            ).fetchall()
            customer_counts = {r["state"]: r["n"] for r in rows}
            rows = self.db.execute(
                "SELECT j.state,COUNT(*) AS n FROM jobs j JOIN job_projects p USING(tenant,job) "
                "WHERE j.tenant=? AND p.project=? AND j.contract=? GROUP BY j.state",
                (tenant, project, c["contract"]),
            ).fetchall()
            project_counts = {r["state"]: r["n"] for r in rows}
            blockers = []
            if c["state"] != "active":
                blockers.append("contract_not_active")
            if not c["starts"] <= now < c["expires"]:
                blockers.append("outside_contract_window")
            for scope, counts, slots, allowance in (
                ("customer", customer_counts, c["allocated"], c["allowance"]),
                ("project", project_counts, p["slots"], p["allowance"]),
            ):
                busy = sum(counts.get(s, 0) for s in ("admitted", "running", "unknown"))
                if slots <= busy:
                    blockers.append(scope + "_capacity_exhausted")
                if busy + counts.get("completed", 0) >= allowance:
                    blockers.append(scope + "_allowance_exhausted")
            if self.require_spend:
                # A read must not invent or acquire financial authorization.
                blockers.append("per_job_spend_authorization_required")
            outcome = None
            if job is not None:
                binding = self.db.execute(
                    "SELECT project FROM job_projects WHERE tenant=? AND job=?", (tenant, job)
                ).fetchone()
                row = self._job(tenant, job)
                if not binding or binding["project"] != project or row["contract"] != c["contract"]:
                    raise Denied("job unavailable in current project and contract")
                outcome = dict(job=job, state=row["state"], completion_fact=None)
                if row["state"] == "completed":
                    usage = self.db.execute(
                        "SELECT payload FROM usage WHERE tenant=? AND job=?", (tenant, job)
                    ).fetchone()
                    if usage is None or row["report"] is None:
                        raise Conflict("completed job has no retained completion evidence")
                    fact = json.loads(usage["payload"])
                    report = json.loads(row["report"])
                    if (
                        fact.get("tenant") != tenant
                        or fact.get("job") != job
                        or fact.get("contract") != c["contract"]
                        or fact.get("report_digest") != digest(report)
                    ):
                        raise Conflict("completion evidence identity mismatch")
                    outcome["completion_fact"] = dict(
                        event_id=fact["event_id"],
                        report_digest=fact["report_digest"],
                        program_digest=fact["program_digest"],
                        recorded_at=fact["occurred_at"],
                        recovered=fact.get("recovered", False),
                        evidence_class="service_accepted_runtime_envelope",
                    )
            state = "blocked" if blockers else "ready_to_submit"
            if outcome is not None:
                state = {
                    "admitted": "queued",
                    "running": "executing",
                    "unknown": "reconciliation_required",
                    "failed": "execution_failed",
                    "cancelled": "cancelled",
                    "completed": "result_available",
                }[outcome["state"]]
            snapshot = dict(
                schema="turing.activation-status.v1",
                tenant=tenant,
                project=project,
                contract=c["contract"],
                observed_at=now,
                state=state,
                ready_to_submit=not blockers,
                blockers=blockers,
                outcome=outcome,
                runtime_health="not_probed",
                signature_status="not_assessed",
                customer_acceptance="not_recorded",
                business_value="not_established",
                deployment_qualification="not_assessed",
                billing_scope="deferred",
            )
            # Content identity only: not a signature, policy grant or capacity lease.
            snapshot["snapshot_digest"] = digest(snapshot)
            return snapshot

    def require_member(self, tenant, actor, capability="turing.customer.read"):
        row = self.db.execute(
            "SELECT role,active FROM members WHERE tenant=? AND actor=?", (tenant, actor)
        ).fetchone()
        if not row or not row["active"] or capability not in ROLES.get(row["role"], set()):
            raise Denied("active membership and role required")
        return row["role"]

    def _audit(self, tenant, actor, action, detail):
        super()._audit(tenant, actor, action, detail)
        if action == "admit":
            self.db.execute(
                "UPDATE spend_intents SET state='admitted' WHERE tenant=? AND job=? AND authorization IS NOT NULL AND state='intent'",
                (tenant, detail["job"]),
            )
        if action == "admit" and self.project_context is not None:
            self.db.execute(
                "INSERT INTO job_projects VALUES(?,?,?)",
                (tenant, detail["job"], self.project_context),
            )
        if action == "lifecycle" and detail.get("state") == "retired":
            self.db.execute(
                "INSERT OR REPLACE INTO retirement(tenant,purge_after,purged) VALUES(?,?,0)",
                (tenant, self.clock() + self.retention_seconds),
            )
        if action in {
            "cancel",
            "cancel_request",
            "policy_cancel_before_dispatch",
            "fail",
            "recover_fail",
            "resolve_without_billing",
        } and detail.get("job"):
            row = self.db.execute(
                "SELECT state FROM jobs WHERE tenant=? AND job=?", (tenant, detail["job"])
            ).fetchone()
            if row and row[0] in {"cancelled", "failed"}:
                self._spend_release(tenant, detail["job"], action)
        if action in {"approve", "provision", "lifecycle", "renew"}:
            c = dict(self._customer(tenant))
            payload = dict(
                schema="turing.reservation.v1",
                tenant=tenant,
                contract=c["contract"],
                billing_account=c["billing_account"],
                state=c["state"],
                slots=c["allocated"],
                action=action,
                occurred_at=self.clock(),
                audit_head=self.db.execute(
                    "SELECT hash FROM audit ORDER BY seq DESC LIMIT 1"
                ).fetchone()[0],
            )
            key = digest(payload)
            payload["event_id"] = key
            self.db.execute(
                "INSERT INTO commercial_events VALUES(?,?,?,NULL)",
                (key, tenant, canonical(payload)),
            )

    def register_approval(self, token, actor, *, approval, tenant, contract, terms_hash, expires):
        self._authorize(token, actor, tenant, "turing.ops.approve", operator=True)
        for v in (approval, tenant, contract, terms_hash):
            text(v)
        integer(expires)
        with self._transaction():
            row = self.db.execute(
                "SELECT * FROM approval_records WHERE approval=?", (approval,)
            ).fetchone()
            if row:
                if (row["tenant"], row["contract"], row["terms_hash"], row["expires"]) != (
                    tenant,
                    contract,
                    terms_hash,
                    expires,
                ):
                    raise Conflict("approval identity conflict")
                return
            self.db.execute(
                "INSERT INTO approval_records VALUES(?,?,?,?,?,?)",
                (approval, tenant, contract, terms_hash, actor, expires),
            )
            self._audit(
                tenant,
                actor,
                "commercial_approval",
                dict(approval=approval, contract=contract, terms_hash=terms_hash),
            )

    def approve_customer(self, token, actor, **kwargs):
        # Exact approved contract envelope must match. A naked reference is not enough.
        terms = {
            k: kwargs[k]
            for k in (
                "tenant",
                "billing_account",
                "contract",
                "starts",
                "expires",
                "contracted",
                "allowance",
            )
        }
        self._check_approval(kwargs["approval"], kwargs["tenant"], kwargs["contract"], terms)
        return super().approve_customer(token, actor, **kwargs)

    def _check_approval(self, approval, tenant, contract, terms):
        row = self.db.execute(
            "SELECT * FROM approval_records WHERE approval=?", (approval,)
        ).fetchone()
        if (
            not row
            or (row["tenant"], row["contract"], row["terms_hash"])
            != (tenant, contract, digest(terms))
            or row["expires"] <= self.clock()
        ):
            raise Denied("approved exact commercial terms required")

    def set_member(self, token, actor, *, tenant, member, role, active=True, operator=False):
        self._authorize(
            token,
            actor,
            tenant,
            "turing.ops.manage" if operator else "turing.customer.admin",
            operator=operator,
        )
        text(member)
        if role not in ROLES or type(active) is not bool:
            raise ValueError("invalid membership")
        with self._transaction():
            self._customer(tenant)
            old = self.db.execute(
                "SELECT * FROM members WHERE tenant=? AND actor=?", (tenant, member)
            ).fetchone()
            if old and old["active"] and old["role"] == "admin" and (not active or role != "admin"):
                n = self.db.execute(
                    "SELECT COUNT(*) FROM members WHERE tenant=? AND active=1 AND role='admin'",
                    (tenant,),
                ).fetchone()[0]
                if n <= 1 and not operator:
                    raise Conflict("cannot remove last customer admin")
            self.db.execute(
                "INSERT INTO members VALUES(?,?,?,?) ON CONFLICT(tenant,actor) DO UPDATE SET role=excluded.role,active=excluded.active",
                (tenant, member, role, int(active)),
            )
            self._audit(tenant, actor, "membership", dict(member=member, role=role, active=active))

    def set_project(self, token, actor, *, tenant, project, slots, allowance, members, active=True):
        self._authorize(token, actor, tenant, "turing.customer.admin")
        text(project)
        integer(slots)
        integer(allowance)
        if type(active) is not bool or not isinstance(members, list) or len(members) > 1000:
            raise ValueError("invalid project")
        members = sorted(set(text(m) for m in members))
        with self._transaction():
            c = self._customer(tenant, active=True)
            for member in members:
                self.require_member(tenant, member)
            total = self.db.execute(
                "SELECT COALESCE(SUM(slots),0) FROM projects WHERE tenant=? AND project!=? AND active=1",
                (tenant, project),
            ).fetchone()[0]
            if active and total + slots > c["allocated"]:
                raise Conflict("project slots exceed reservation")
            busy = self.db.execute(
                "SELECT COUNT(*) FROM jobs j JOIN job_projects p USING(tenant,job) WHERE j.tenant=? AND p.project=? AND j.state IN ('admitted','running','unknown')",
                (tenant, project),
            ).fetchone()[0]
            if busy and (not active or slots < busy):
                raise Conflict("drain project before resizing/deactivation")
            self.db.execute(
                "INSERT INTO projects VALUES(?,?,?,?,?) ON CONFLICT(tenant,project) DO UPDATE SET slots=excluded.slots,allowance=excluded.allowance,active=excluded.active",
                (tenant, project, slots, allowance, int(active)),
            )
            self.db.execute(
                "DELETE FROM project_members WHERE tenant=? AND project=?", (tenant, project)
            )
            self.db.executemany(
                "INSERT INTO project_members VALUES(?,?,?)", [(tenant, project, m) for m in members]
            )
            self._audit(
                tenant,
                actor,
                "project",
                dict(
                    project=project,
                    slots=slots,
                    allowance=allowance,
                    members=members,
                    active=active,
                ),
            )

    def _project_access(self, tenant, actor, project):
        role = self.require_member(tenant, actor)
        row = self.db.execute(
            "SELECT * FROM projects WHERE tenant=? AND project=? AND active=1", (tenant, project)
        ).fetchone()
        if not row:
            raise Denied("project unavailable")
        if (
            role != "admin"
            and not self.db.execute(
                "SELECT 1 FROM project_members WHERE tenant=? AND project=? AND actor=?",
                (tenant, project, actor),
            ).fetchone()
        ):
            raise Denied("project membership required")
        return row

    def _before_provision(self, tenant, slots):
        reserved = self.db.execute(
            "SELECT COALESCE(SUM(slots),0) FROM projects WHERE tenant=? AND active=1", (tenant,)
        ).fetchone()[0]
        if reserved > slots:
            raise Conflict("resize project allocations before reducing customer slots")

    def _before_admit(self, tenant, actor, job):
        if self.require_spend:
            row = self.db.execute(
                "SELECT authorization,state FROM spend_intents WHERE tenant=? AND job=?",
                (tenant, job),
            ).fetchone()
            if (
                not row
                or not row[0]
                or row[1] != "intent"
                or json.loads(row[0])["expires_at"] <= self.clock()
            ):
                raise Denied("current commercial spend authorisation required")
        if self.project_context is None:
            raise Denied("project required")
        p = self._project_access(tenant, actor, self.project_context)
        c = self._customer(tenant)
        counts = dict(
            self.db.execute(
                "SELECT j.state,COUNT(*) FROM jobs j JOIN job_projects p USING(tenant,job) WHERE j.tenant=? AND p.project=? AND j.contract=? GROUP BY j.state",
                (tenant, self.project_context, c["contract"]),
            )
        )
        busy = sum(counts.get(s, 0) for s in ("admitted", "running", "unknown"))
        if busy >= p["slots"] or busy + counts.get("completed", 0) >= p["allowance"]:
            raise Conflict("project capacity/allowance exhausted")

    def _before_dispatch(self, tenant, actor, job):
        spend = self.db.execute(
            "SELECT authorization,state FROM spend_intents WHERE tenant=? AND job=?", (tenant, job)
        ).fetchone()
        if self.require_spend and not spend:
            raise Denied("commercial spend authorisation required")
        if spend and (
            spend["state"] != "admitted"
            or json.loads(spend["authorization"])["expires_at"] <= self.clock()
        ):
            raise Denied("spend authorisation expired or not admitted")
        self.require_member(tenant, actor, "turing.jobs.submit")
        row = self.db.execute(
            "SELECT project FROM job_projects WHERE tenant=? AND job=?", (tenant, job)
        ).fetchone()
        if not row:
            raise Denied("job has no project policy")
        self._project_access(tenant, actor, row[0])
        if self.db.execute(
            "SELECT 1 FROM cancellation WHERE tenant=? AND job=?", (tenant, job)
        ).fetchone():
            raise Denied("cancellation requested")

    def submit_project(self, token, actor, *, tenant, project, job, request):
        self.project_context = text(project)
        try:
            return super().submit(token, actor, tenant=tenant, job=job, request=request)
        finally:
            self.project_context = None

    def scoped_job(self, token, actor, *, tenant, job):
        self._authorize(token, actor, tenant, "turing.customer.read")
        row = self.db.execute(
            "SELECT project FROM job_projects WHERE tenant=? AND job=?", (tenant, job)
        ).fetchone()
        if not row:
            raise Denied("job unavailable")
        self._project_access(tenant, actor, row[0])
        record = self._job(tenant, job)
        return dict(
            job=job,
            state=record["state"],
            report=json.loads(record["report"]) if record["report"] else None,
        )

    def request_cancel(self, token, actor, *, tenant, job):
        self._authorize(token, actor, tenant, "turing.jobs.submit")
        with self._transaction():
            row = self._job(tenant, job)
            if row["actor"] != actor:
                raise Denied("submitter required")
            if row["state"] == "admitted":
                self.db.execute(
                    "UPDATE jobs SET state='cancelled' WHERE tenant=? AND job=?", (tenant, job)
                )
            elif row["state"] == "running":
                self.db.execute(
                    "INSERT OR IGNORE INTO cancellation VALUES(?,?,?)", (tenant, job, actor)
                )
            elif row["state"] not in {"cancelled", "failed", "completed"}:
                raise Conflict("investigate unresolved execution")
            self._audit(tenant, actor, "cancel_request", dict(job=job))

    def renew(
        self, token, actor, *, tenant, contract, approval, starts, expires, allowance, command
    ):
        self._authorize(token, actor, tenant, "turing.ops.manage", operator=True)
        text(contract)
        integer(starts, 0)
        integer(expires)
        integer(allowance)
        if expires <= starts:
            raise ValueError("invalid contract window")

        def apply():
            c = dict(self._customer(tenant))
            if c["state"] == "retired":
                raise Conflict("retired customer")
            if self.db.execute(
                "SELECT 1 FROM jobs WHERE tenant=? AND state IN ('admitted','running','unknown')",
                (tenant,),
            ).fetchone():
                raise Conflict("drain before renewal")
            terms = dict(
                tenant=tenant,
                billing_account=c["billing_account"],
                contract=contract,
                starts=starts,
                expires=expires,
                contracted=c["contracted"],
                allowance=allowance,
            )
            self._check_approval(approval, tenant, contract, terms)
            if (
                contract == c["contract"]
                or self.db.execute(
                    "SELECT 1 FROM contract_history WHERE tenant=? AND contract=?",
                    (tenant, contract),
                ).fetchone()
            ):
                raise Conflict("contract identity reused")
            self.db.execute(
                "INSERT INTO contract_history VALUES(?,?,?)", (tenant, c["contract"], canonical(c))
            )
            self.db.execute(
                "UPDATE customers SET contract=?,approval=?,starts=?,expires=?,allowance=?,state='suspended' WHERE tenant=?",
                (contract, approval, starts, expires, allowance, tenant),
            )

        return self._command(
            actor,
            tenant,
            command,
            "renew",
            dict(
                contract=contract,
                approval=approval,
                starts=starts,
                expires=expires,
                allowance=allowance,
            ),
            apply,
        )

    def adjust_usage(self, token, actor, *, tenant, event, quantity, reason, approval, command):
        self._authorize(token, actor, tenant, "turing.ops.billing", operator=True)
        text(reason)
        text(approval)
        integer(abs(quantity) if type(quantity) is int else quantity)

        def apply():
            original = self.db.execute(
                "SELECT payload FROM usage WHERE tenant=? AND event=?", (tenant, event)
            ).fetchone()
            if not original:
                raise Denied("original usage unavailable")
            payload = dict(
                schema="turing.adjustment.v1",
                tenant=tenant,
                original_event=event,
                quantity=quantity,
                reason=reason,
                approval=approval,
                occurred_at=self.clock(),
            )
            key = digest([tenant, command, payload])
            payload["event_id"] = key
            self.db.execute(
                "INSERT INTO commercial_events VALUES(?,?,?,NULL)",
                (key, tenant, canonical(payload)),
            )

        return self._command(
            actor,
            tenant,
            command,
            "usage_adjustment",
            dict(event=event, quantity=quantity, reason=reason, approval=approval),
            apply,
        )

    def backup(self, token, actor, destination):
        import sqlite3

        self._authorize(token, actor, "__service_ops__", "turing.ops.manage", operator=True)
        target = sqlite3.connect(destination)
        try:
            self.db.backup(target)
        finally:
            target.close()

    def _usage_details(self, tenant, job):
        row = self.db.execute(
            "SELECT authorization FROM spend_intents WHERE tenant=? AND job=?", (tenant, job)
        ).fetchone()
        return (
            {"spend_authorization": json.loads(row[0])["authorization_id"]}
            if row and row[0]
            else {}
        )

    def _spend_release(self, tenant, job, reason):
        completed = self.db.execute(
            "SELECT state FROM jobs WHERE tenant=? AND job=?", (tenant, job)
        ).fetchone()
        if completed and completed[0] in {"completed", "running", "unknown"}:
            return  # No financial release while an outcome is billable or ambiguous.
        row = self.db.execute(
            "SELECT authorization FROM spend_intents WHERE tenant=? AND job=?", (tenant, job)
        ).fetchone()
        if not row or not row[0]:
            return
        authorization = json.loads(row[0])
        key = digest(["turing.spend_release.v1", tenant, job])
        payload = dict(
            schema="turing.spend_release.v1",
            event_id=key,
            tenant=tenant,
            job=job,
            authorization_id=authorization["authorization_id"],
            reason=reason,
        )
        self.db.execute(
            "INSERT OR IGNORE INTO commercial_events VALUES(?,?,?,NULL)",
            (key, tenant, canonical(payload)),
        )
        self.db.execute(
            "UPDATE spend_intents SET state='release_pending' WHERE tenant=? AND job=?",
            (tenant, job),
        )

    def submit_with_spend(self, token, actor, *, tenant, project, job, request, billing):
        from .billing import authorize_spend

        claims = self._authorize(token, actor, tenant, "turing.jobs.submit")
        text(job)
        self._request(request)
        self._project_access(tenant, actor, project)
        checksum = digest([actor, project, request])
        key = digest(["turing.spend.v1", tenant, job])
        with self._transaction():
            customer = self._customer(tenant, active=True)
            old = self.db.execute(
                "SELECT * FROM spend_intents WHERE tenant=? AND job=?", (tenant, job)
            ).fetchone()
            if old and old["request_hash"] != checksum:
                raise Conflict("spend idempotency identity conflict")
            existing = self.db.execute(
                "SELECT 1 FROM jobs WHERE tenant=? AND job=?", (tenant, job)
            ).fetchone()
            if existing:
                self.project_context = text(project)
                try:
                    # Validate immutable request identity without a second token consumption.
                    saved = self._job(tenant, job)
                    if saved["request_hash"] != digest([actor, request, project]):
                        raise Conflict("job key reused with different request or actor")
                    return dict(job=job, state=saved["state"])
                finally:
                    self.project_context = None
            if old and old["state"] == "release_pending":
                raise Conflict("spend release pending; use a new job identity")
            self.db.execute(
                "INSERT OR IGNORE INTO spend_intents VALUES(?,?,?,NULL,'intent')",
                (tenant, job, checksum),
            )
            account = customer["billing_account"]
        # Persist intent before crossing the billing boundary; a lost reply is
        # retried by the stable remote job_key, never a guessed local balance.
        authorization = (
            json.loads(old["authorization"])
            if old and old["authorization"]
            else authorize_spend(billing, account, job_key=key, request_digest=checksum)
        )
        with self._transaction():
            self.db.execute(
                "UPDATE spend_intents SET authorization=? WHERE tenant=? AND job=?",
                (canonical(authorization), tenant, job),
            )
        try:
            if authorization["expires_at"] <= self.clock():
                raise Denied("spend authorisation expired")
            self.project_context = text(project)
            try:
                return self._submit_authorized(
                    claims, actor, tenant=tenant, job=job, request=request
                )
            finally:
                self.project_context = None
        except Exception:
            with self._transaction():
                self._spend_release(tenant, job, "admission_not_completed")
            raise

    def purge_data(self, token, actor, *, tenant, reason, custody):
        self._authorize(token, actor, tenant, "turing.ops.manage", operator=True)
        text(reason)
        with self._transaction():
            c = self._customer(tenant)
            row = self.db.execute(
                "SELECT purge_after FROM retirement WHERE tenant=?", (tenant,)
            ).fetchone()
            if c["state"] != "retired" or not row or row[0] > self.clock():
                raise Conflict("retention/offboarding gate not met")
            custody.purge(tenant)
            count = self.db.execute(
                "UPDATE jobs SET request='{}',report=NULL WHERE tenant=?", (tenant,)
            ).rowcount
            self.db.execute("UPDATE retirement SET purged=1 WHERE tenant=?", (tenant,))
            self._audit(
                tenant,
                actor,
                "data_purge",
                dict(
                    reason=reason,
                    job_records=count,
                    scope="live service inputs/reports; backup retention remains separately governed",
                ),
            )
            return dict(job_records=count, state="live_data_purged")

    def reconcile(self, token, actor):
        result = super().reconcile(token, actor)
        for row in self.db.execute(
            "SELECT tenant,job,state FROM spend_intents WHERE state IN ('intent','release_pending')"
        ):
            result["issues"].append(dict(kind="spend_intent_reconciliation", **dict(row)))
        result["pending_commercial_billing"] = self.db.execute(
            "SELECT COUNT(*) FROM commercial_events WHERE receipt IS NULL"
        ).fetchone()[0]
        return result
