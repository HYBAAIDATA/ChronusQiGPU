"""Same-origin BFF and programmatic API. No user-supplied actor/runtime/clock."""

from dataclasses import dataclass
import json
from pathlib import Path
import secrets
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from .control import Conflict, Denied, Unavailable
from .enterprise import ROLES
from .billing import deliver_commercial


@dataclass
class Dependencies:
    plane_factory: object
    identity_verifier: object
    customer_issuer: object
    operator_issuer: object
    claims_factory: object
    key_id: str
    operator_subjects: frozenset
    approver_subjects: frozenset
    origin: str
    sessions: object = None
    billing: object = None
    readiness: object = None
    require_spend: bool = False
    custody: object = None


def create_app(deps: Dependencies):
    app = FastAPI(
        title="TURING Enterprise Service",
        version="0.2.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    static = Path(__file__).parent / "static"

    @app.middleware("http")
    async def boundary(request, call_next):
        request_id = secrets.token_hex(16)
        try:
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                if request.headers.get("content-type", "").split(";")[0] not in {
                    "application/json",
                    "application/x-www-form-urlencoded",
                }:
                    return JSONResponse({"error": "content type required"}, status_code=415)
                raw = bytearray()
                async for chunk in request.stream():
                    raw.extend(chunk)
                    if len(raw) > 131072:
                        return JSONResponse({"error": "payload too large"}, status_code=413)
                request._body = bytes(raw)
            response = await call_next(request)
        except Exception:
            response = JSONResponse(
                {"error": "request unavailable", "request_id": request_id}, status_code=503
            )
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
                "Strict-Transport-Security": "max-age=31536000",
                "X-Request-ID": request_id,
            }
        )
        return response

    def identity(request):
        bearer = request.headers.get("authorization", "")
        if bearer.startswith("Bearer "):
            return deps.identity_verifier.verify(bearer[7:])
        if deps.sessions is None:
            raise Denied("SSO unavailable; access token required")
        result, csrf = deps.sessions.get(request.cookies.get("turing_session"))
        if request.method not in {"GET", "HEAD"}:
            if request.headers.get("origin") != deps.origin or not secrets.compare_digest(
                request.headers.get("x-csrf-token", ""), csrf
            ):
                raise Denied("CSRF validation failed")
        return result

    def issue(plane, who, tenant, capability, operator):
        issuer = deps.operator_issuer if operator else deps.customer_issuer
        if operator:
            allowed = (
                deps.approver_subjects
                if capability == "turing.ops.approve"
                else deps.operator_subjects
            )
            if who.subject not in allowed:
                raise Denied("operator identity required")
        else:
            plane.require_member(tenant, who.subject, capability)
        now = int(time.time())
        claims = deps.claims_factory(
            subscription_id="service:" + tenant,
            tenant_id="__service_ops__" if operator else tenant,
            issuer=issuer.issuer,
            key_id=deps.key_id,
            capabilities=(capability,),
            actors=(who.subject,),
            not_before=max(0, now - 1),
            expires_at=now + 60,
            max_payload_bytes=131072,
        )
        return issuer.issue(claims)

    async def operation(request, tenant, capability, action, *, operator=False, body=False):
        try:
            who = identity(request)
            payload = await request.json() if body else None
            if body and not isinstance(payload, dict):
                raise ValueError("object body required")

            def execute():
                plane = deps.plane_factory()
                try:
                    token = issue(plane, who, tenant, capability, operator)
                    # Bounded authenticated request rate. Counter is shared by API replicas.
                    with plane._transaction():
                        plane.db.execute(
                            "CREATE TABLE IF NOT EXISTS request_rates(actor TEXT,window INTEGER,n INTEGER,PRIMARY KEY(actor,window))"
                        )
                        window = int(time.time()) // 60
                        plane.db.execute("DELETE FROM request_rates WHERE window<?", (window - 1,))
                        plane.db.execute(
                            "INSERT INTO request_rates VALUES(?,?,1) ON CONFLICT(actor,window) DO UPDATE SET n=n+1",
                            (who.subject, window),
                        )
                        if (
                            plane.db.execute(
                                "SELECT n FROM request_rates WHERE actor=? AND window=?",
                                (who.subject, window),
                            ).fetchone()[0]
                            > 300
                        ):
                            raise Conflict("request rate limit exceeded")
                    return action(plane, token, who.subject, payload)
                finally:
                    plane.close()

            return JSONResponse(await run_in_threadpool(execute))
        except Denied:
            return JSONResponse({"error": "access denied"}, status_code=403)
        except Conflict as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)
        except (TypeError, ValueError, KeyError):
            return JSONResponse({"error": "invalid request"}, status_code=422)
        except Unavailable:
            return JSONResponse({"error": "dependency unavailable"}, status_code=503)

    @app.get("/health/live")
    def live():
        return {"state": "live"}

    @app.get("/health/ready")
    def ready():
        ok = deps.readiness is not None and deps.readiness()
        return JSONResponse(
            {"state": "ready" if ok else "unavailable"}, status_code=200 if ok else 503
        )

    @app.get("/login")
    def login():
        if deps.sessions is None:
            return JSONResponse({"error": "SSO not configured"}, status_code=503)
        state, url = deps.sessions.start()
        response = RedirectResponse(url, status_code=303)
        response.set_cookie(
            "turing_login",
            state,
            max_age=300,
            secure=True,
            httponly=True,
            samesite="lax",
            path="/auth/callback",
        )
        return response

    @app.get("/auth/callback")
    def callback(request: Request, state: str = "", code: str = ""):
        if deps.sessions is None:
            return JSONResponse({"error": "SSO unavailable"}, status_code=503)
        try:
            handle = deps.sessions.finish(state, code, request.cookies.get("turing_login"))
        except Denied:
            return JSONResponse({"error": "login denied"}, status_code=403)
        response = RedirectResponse("/workspace", status_code=303)
        response.set_cookie(
            "turing_session",
            handle,
            max_age=3600,
            secure=True,
            httponly=True,
            samesite="lax",
            path="/",
        )
        response.delete_cookie(
            "turing_login", path="/auth/callback", secure=True, httponly=True, samesite="lax"
        )
        return response

    @app.get("/api/session")
    def session(request: Request):
        try:
            who = identity(request)
            csrf = None
            if deps.sessions and request.cookies.get("turing_session"):
                _, csrf = deps.sessions.get(request.cookies.get("turing_session"))
            plane = deps.plane_factory()
            try:
                memberships = [
                    dict(r)
                    for r in plane.db.execute(
                        "SELECT tenant,role FROM members WHERE actor=? AND active=1", (who.subject,)
                    )
                ]
            finally:
                plane.close()
            return {
                "subject": who.subject,
                "memberships": memberships,
                "operator": who.subject in deps.operator_subjects,
                "approver": who.subject in deps.approver_subjects,
                "csrf": csrf,
            }
        except Denied:
            return JSONResponse({"error": "sign in required"}, status_code=401)

    @app.post("/api/logout")
    def logout(request: Request):
        try:
            identity(request)
        except Denied:
            return JSONResponse({"error": "access denied"}, status_code=403)
        if deps.sessions:
            deps.sessions.delete(request.cookies.get("turing_session"))
        response = JSONResponse({"state": "signed out"})
        response.delete_cookie(
            "turing_session", path="/", secure=True, httponly=True, samesite="lax"
        )
        return response

    @app.get("/api/ops/customers")
    async def customers(request: Request, after: str = "", limit: int = 50):
        def action(p, t, a, b):
            if not 1 <= limit <= 100:
                raise ValueError()
            p._authorize(t, a, "__service_ops__", "turing.ops.manage", operator=True)
            return {
                "customers": [
                    dict(r)
                    for r in p.db.execute(
                        "SELECT tenant,contract,state,contracted,allocated,expires FROM customers WHERE tenant>? ORDER BY tenant LIMIT ?",
                        (after, limit),
                    )
                ]
            }

        return await operation(
            request, "__service_ops__", "turing.ops.manage", action, operator=True
        )

    @app.post("/api/ops/customers/{tenant}/{action}")
    async def operator_action(request: Request, tenant: str, action: str):
        methods = {
            "approve": ("turing.ops.manage", "approve_customer"),
            "approval": ("turing.ops.approve", "register_approval"),
            "provision": ("turing.ops.manage", "provision"),
            "lifecycle": ("turing.ops.manage", "lifecycle"),
            "renew": ("turing.ops.manage", "renew"),
            "member": ("turing.ops.manage", "set_member"),
            "resolve": ("turing.ops.manage", "resolve_unknown"),
            "adjust": ("turing.ops.billing", "adjust_usage"),
        }
        if action == "purge-data":

            def purge_call(p, t, a, b):
                if deps.custody is None:
                    raise Unavailable("custody unavailable")
                return p.purge_data(t, a, tenant=tenant, custody=deps.custody, **b)

            return await operation(
                request, tenant, "turing.ops.manage", purge_call, operator=True, body=True
            )
        if action not in methods:
            return JSONResponse({"error": "not found"}, status_code=404)
        capability, method = methods[action]

        def call(p, t, a, b):
            if action == "member":
                b = {**b, "operator": True}
            return {"result": getattr(p, method)(t, a, tenant=tenant, **b)}

        return await operation(request, tenant, capability, call, operator=True, body=True)

    @app.get("/api/ops/reconcile")
    async def reconciliation(request: Request):
        def call(p, t, a, b):
            report = p.reconcile(t, a)
            report["pending_commercial"] = p.db.execute(
                "SELECT COUNT(*) FROM commercial_events WHERE receipt IS NULL"
            ).fetchone()[0]
            return report

        return await operation(request, "__service_ops__", "turing.ops.manage", call, operator=True)

    @app.post("/api/ops/billing/deliver")
    async def deliver(request: Request):
        def call(p, t, a, b):
            return {
                "usage": p.deliver_usage(t, a, sink=deps.billing),
                "commercial": deliver_commercial(p, t, a, deps.billing),
            }

        return await operation(
            request, "__service_ops__", "turing.ops.billing", call, operator=True
        )

    @app.get("/api/customer/{tenant}/overview")
    async def overview(request: Request, tenant: str):
        return await operation(
            request,
            tenant,
            "turing.customer.read",
            lambda p, t, a, b: p.overview(t, a, tenant=tenant),
        )

    @app.get("/api/customer/{tenant}/{resource}")
    async def customer_list(
        request: Request, tenant: str, resource: str, after: str = "", limit: int = 50
    ):
        cap = (
            "turing.customer.admin"
            if resource in {"members", "usage", "audit", "billing"}
            else "turing.customer.read"
        )

        def call(p, t, a, b):
            if not 1 <= limit <= 100:
                raise ValueError()
            p._authorize(t, a, tenant, cap)
            if resource == "members":
                return {
                    "members": [
                        dict(r)
                        for r in p.db.execute(
                            "SELECT actor,role,active FROM members WHERE tenant=? AND actor>? ORDER BY actor LIMIT ?",
                            (tenant, after, limit),
                        )
                    ]
                }
            if resource == "projects":
                role = p.require_member(tenant, a)
                return {
                    "projects": [
                        dict(r)
                        for r in p.db.execute(
                            "SELECT p.* FROM projects p WHERE p.tenant=? AND p.project>? AND (?='admin' OR EXISTS(SELECT 1 FROM project_members m WHERE m.tenant=p.tenant AND m.project=p.project AND m.actor=?)) ORDER BY p.project LIMIT ?",
                            (tenant, after, role, a, limit),
                        )
                    ]
                }
            if resource == "jobs":
                role = p.require_member(tenant, a)
                return {
                    "jobs": [
                        dict(r)
                        for r in p.db.execute(
                            "SELECT j.job,j.state,j.actor,p.project FROM jobs j JOIN job_projects p USING(tenant,job) WHERE j.tenant=? AND j.job>? AND (?='admin' OR EXISTS(SELECT 1 FROM project_members m WHERE m.tenant=p.tenant AND m.project=p.project AND m.actor=?)) ORDER BY j.job LIMIT ?",
                            (tenant, after, role, a, limit),
                        )
                    ]
                }
            if resource == "usage":
                return {
                    "usage": [
                        json.loads(r[0])
                        for r in p.db.execute(
                            "SELECT payload FROM usage WHERE tenant=? AND event>? ORDER BY event LIMIT ?",
                            (tenant, after, limit),
                        )
                    ]
                }
            if resource == "audit":
                rows = p.db.execute(
                    "SELECT seq,payload FROM audit WHERE seq>? AND json_extract(payload,'$.tenant')=? ORDER BY seq LIMIT ?",
                    (int(after or 0), tenant, limit),
                )
                return {"audit": [dict(cursor=r[0], **json.loads(r[1])) for r in rows]}
            if resource == "billing":
                if deps.billing is None:
                    raise Unavailable()
                return deps.billing.account(p._customer(tenant)["billing_account"])
            raise ValueError("unknown resource")

        return await operation(request, tenant, cap, call)

    @app.post("/api/customer/{tenant}/members")
    async def member(request: Request, tenant: str):
        return await operation(
            request,
            tenant,
            "turing.customer.admin",
            lambda p, t, a, b: {"result": p.set_member(t, a, tenant=tenant, **b)},
            body=True,
        )

    @app.post("/api/customer/{tenant}/projects")
    async def project(request: Request, tenant: str):
        return await operation(
            request,
            tenant,
            "turing.customer.admin",
            lambda p, t, a, b: {"result": p.set_project(t, a, tenant=tenant, **b)},
            body=True,
        )

    @app.post("/api/customer/{tenant}/spend-limit")
    async def spend_limit(request: Request, tenant: str):
        from .billing import set_spend_limit

        def call(p, t, a, b):
            p._authorize(t, a, tenant, "turing.customer.admin")
            if deps.billing is None:
                raise Unavailable("billing unavailable")
            return set_spend_limit(deps.billing, p._customer(tenant)["billing_account"], **b)

        return await operation(request, tenant, "turing.customer.admin", call, body=True)

    @app.post("/api/customer/{tenant}/jobs")
    async def submit(request: Request, tenant: str):
        def call(p, t, a, b):
            if deps.require_spend:
                return p.submit_with_spend(t, a, tenant=tenant, billing=deps.billing, **b)
            return p.submit_project(t, a, tenant=tenant, **b)

        return await operation(request, tenant, "turing.jobs.submit", call, body=True)

    @app.get("/api/customer/{tenant}/jobs/{job}")
    async def job(request: Request, tenant: str, job: str):
        return await operation(
            request,
            tenant,
            "turing.customer.read",
            lambda p, t, a, b: p.scoped_job(t, a, tenant=tenant, job=job),
        )

    @app.post("/api/customer/{tenant}/jobs/{job}/cancel")
    async def cancel(request: Request, tenant: str, job: str):
        return await operation(
            request,
            tenant,
            "turing.jobs.submit",
            lambda p, t, a, b: {"result": p.request_cancel(t, a, tenant=tenant, job=job)},
        )

    @app.get("/api/openapi.json")
    async def schema(request: Request):
        return await operation(
            request,
            "__service_ops__",
            "turing.ops.manage",
            lambda p, t, a, b: app.openapi(),
            operator=True,
        )

    @app.get("/assets/{name}")
    def asset(name: str):
        if name not in {"portal.js", "portal.css"}:
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(static / name)

    @app.get("/{surface}")
    def portal(surface: str):
        if surface not in {"ops", "admin", "workspace"}:
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(static / "portal.html")

    return app
