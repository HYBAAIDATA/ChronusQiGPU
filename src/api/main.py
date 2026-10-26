"""EUCLID Cognitive Gateway FastAPI entry point."""

from __future__ import annotations

from fastapi import FastAPI

from src.api.routers import euclid_science, euclid_voice


def create_app() -> FastAPI:
    """Create the configured EUCLID API application."""
    app = FastAPI(title="EUCLID Cognitive Gateway")
    app.include_router(euclid_voice.router)
    app.include_router(euclid_science.router)
    return app


app = create_app()


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "EUCLID_ONLINE", "mode": "cognitive_architecture"}


__all__ = ["app", "create_app"]
