"""FastAPI adapter for the portable AL HARAS package."""

from __future__ import annotations

from typing import Any

from .runtime import GuardianAPI


def create_router(api: GuardianAPI):
    try:
        from fastapi import APIRouter, Header, Request
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise RuntimeError("FastAPI is required for the AL HARAS router") from exc

    router = APIRouter(prefix="/api/v1/security", tags=["HYBA Security — AL HARAS"])

    @router.get("/status")
    async def status() -> dict[str, Any]:
        return api.public_status()

    @router.get("/subscribe")
    async def subscribe() -> dict[str, Any]:
        return {
            "product": "HYBA Security",
            "capability": api.settings.capability,
            "subscription_required": True,
            "subscription_url": api.settings.subscription_url,
        }

    @router.post("/evaluate")
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
