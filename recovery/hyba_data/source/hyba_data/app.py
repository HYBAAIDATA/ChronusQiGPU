"""Vercel-supported FastAPI entrypoint.

Vercel imports the module-level ``app`` instance from this file.
The application itself remains defined in ``hyba_data.api.app``.
"""
from hyba_data.api.app import app


@app.get("/", include_in_schema=False)
async def root():
    """Deployment identification endpoint."""
    return {
        "service": "HYBA_DATA API",
        "version": "9.0.0",
        "status": "running",
        "health": "/health",
        "readiness": "/ready",
        "docs": "/docs",
    }
