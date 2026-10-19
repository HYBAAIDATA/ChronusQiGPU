"""EUCLID Cognitive Gateway FastAPI Entry Point (`src/api/main.py`)."""

from __future__ import annotations

from fastapi import FastAPI

from src.api.routers import euclid_science, euclid_voice

app = FastAPI(title="EUCLID Cognitive Gateway")

app.include_router(euclid_voice.router)
app.include_router(euclid_science.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "EUCLID_ONLINE", "mode": "cognitive_architecture"}


__all__ = ["app"]
