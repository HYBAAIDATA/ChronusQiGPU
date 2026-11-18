"""Minimal CPU execution service without legacy workload/mining/admin routes.

Candidate deployment entry point. Target-host security, backup/rollback and
release admission remain external gates; this module cannot grant admission.
"""
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI

from chronus.execution.authority import ExecutionAuthority
from chronus.service.execution_body_limit import ExecutionBodyLimit
from chronus.service.routers.execute import router
from chronus.security.al_haras.authorizer import LocalALHarasAuthorizer


@asynccontextmanager
async def lifespan(app):
    path = os.environ["CHRONUS_EXECUTION_STATE_PATH"]
    if not os.getenv("CHRONUS_TENANT_TOKENS") and not os.getenv("CHRONUS_JWT_SECRET"):
        raise RuntimeError("local tenant identity or stable JWT configuration is required")
    app.state.execution_authority = ExecutionAuthority(
        path,
        custody_key=Path(os.environ["CHRONUS_EXECUTION_KEY_FILE"]).read_bytes(),
        max_concurrent=int(os.getenv("CHRONUS_EXECUTION_CONCURRENCY", "2")),
        max_wall_seconds=float(os.getenv("CHRONUS_EXECUTION_WALL_SECONDS", "30")),
        memory_bytes=int(os.getenv("CHRONUS_EXECUTION_MEMORY_BYTES", str(2 * 1024**3))),
    )
    app.state.al_haras_authorizer = LocalALHarasAuthorizer()
    yield


def create_execution_app():
    application = FastAPI(title="Chronus execution authority", lifespan=lifespan)
    application.add_middleware(ExecutionBodyLimit)
    application.include_router(router)
    return application


app = create_execution_app()
