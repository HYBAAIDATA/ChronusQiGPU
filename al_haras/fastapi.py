"""FastAPI adapter for the portable AL HARAS package."""

from __future__ import annotations


from .runtime import GuardianAPI
from .mediation_runtime import (
    attach_receipt,
    evidence_attach,
    evaluate_guardian,
    guardian_middleware,
)


def create_router(api: GuardianAPI):
    try:
        from fastapi import APIRouter, Header, Request
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise RuntimeError("FastAPI is required for the AL HARAS router") from exc

    router = APIRouter(prefix="/api/v1/security", tags=["HYBA Security — AL HARAS"])

    @router.get("/status")
    @guardian_middleware
    @evidence_attach
    async def status(
        request: Request,
        authorization: str | None = Header(default=None),
        x_hyba_tenant: str | None = Header(default=None),
        x_hyba_actor: str | None = Header(default=None),
    ):
        headers = {
            "authorization": authorization or "",
            "x-hyba-tenant": x_hyba_tenant or "",
            "x-hyba-actor": x_hyba_actor or "",
        }
        decision = evaluate_guardian(api, headers, "security.status", "security/status")
        if not decision.allowed:
            return JSONResponse(status_code=decision.status_code, content=decision.receipt)
        return attach_receipt(api.public_status(), decision.receipt)

    @router.get("/subscribe")
    @guardian_middleware
    @evidence_attach
    async def subscribe(
        request: Request,
        authorization: str | None = Header(default=None),
        x_hyba_tenant: str | None = Header(default=None),
        x_hyba_actor: str | None = Header(default=None),
    ):
        headers = {
            "authorization": authorization or "",
            "x-hyba-tenant": x_hyba_tenant or "",
            "x-hyba-actor": x_hyba_actor or "",
        }
        decision = evaluate_guardian(api, headers, "security.subscribe", "security/subscribe")
        if not decision.allowed:
            return JSONResponse(status_code=decision.status_code, content=decision.receipt)
        return attach_receipt(
            {
                "product": "HYBA Security",
                "capability": api.settings.capability,
                "subscription_required": True,
                "subscription_url": api.settings.subscription_url,
            },
            decision.receipt,
        )

    @router.post("/evaluate")
    @guardian_middleware
    @evidence_attach
    async def evaluate(
        request: Request,
        authorization: str | None = Header(default=None),
        x_hyba_tenant: str | None = Header(default=None),
        x_hyba_actor: str | None = Header(default=None),
    ):
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"allowed": False, "reason": "INVALID_JSON"},
            )
        code, payload = api.evaluate(
            headers={
                "authorization": authorization or "",
                "x-hyba-tenant": x_hyba_tenant or "",
                "x-hyba-actor": x_hyba_actor or "",
            },
            body=body,
        )
        return JSONResponse(status_code=code, content=payload)

    return router
