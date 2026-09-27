"""Stub: hyba_post_quantum_civilization_api — post-quantum civilization layer."""

from fastapi import FastAPI

app = FastAPI(title="HYBA Post-Quantum Civilization API", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "civilization", "stub": True}
