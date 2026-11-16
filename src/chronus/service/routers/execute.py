"""Synchronous compatibility API for bounded CHRONUS CPU epochs."""
import os
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from chronus.core.workload_alias import normalize_workload_type
from chronus.execution.authority import ExecutionAuthority, ExecutionBusyError
from chronus.service.dependencies import get_current_tenant
from chronus.service.models import WorkloadRequest

router = APIRouter(prefix="/api/v1/execute", tags=["execution"])
_lock = threading.Lock()


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workload: WorkloadRequest
    wall_seconds: float | None = Field(default=None, gt=0, le=3600, allow_inf_nan=False)


def get_authority(request: Request) -> ExecutionAuthority:
    with _lock:
        authority = getattr(request.app.state, "execution_authority", None)
        if authority is None:
            path = os.getenv("CHRONUS_EXECUTION_STATE_PATH")
            key_path = os.getenv("CHRONUS_EXECUTION_KEY_FILE")
            if not path or not key_path:
                raise HTTPException(503, "Durable execution custody is not configured")
            try:
                authority = ExecutionAuthority(
                    path,
                    custody_key=Path(key_path).read_bytes(),
                    max_concurrent=int(os.getenv("CHRONUS_EXECUTION_CONCURRENCY", "2")),
                    max_wall_seconds=float(os.getenv("CHRONUS_EXECUTION_WALL_SECONDS", "30")),
                    memory_bytes=int(os.getenv("CHRONUS_EXECUTION_MEMORY_BYTES", str(2 * 1024**3))),
                )
            except Exception as exc:
                raise HTTPException(503, "Execution custody or policy is unavailable") from exc
            request.app.state.execution_authority = authority
        return authority


def authenticated_tenant(tenant_id=Depends(get_current_tenant)) -> str:
    # GET status must require identity too; the legacy dependency allows public GET.
    if not tenant_id:
        raise HTTPException(401, "Valid authentication token required")
    return tenant_id


@router.post("")
async def execute_epoch(body: ExecutionRequest,
                        tenant_id: str = Depends(authenticated_tenant),
                        authority: ExecutionAuthority = Depends(get_authority)) -> dict:
    workload = body.workload
    if workload.tenant_id != tenant_id:
        raise HTTPException(403, "Request tenant does not match authenticated tenant")
    if workload.backend_preference not in (None, "python-math-reference"):
        raise HTTPException(400, "Only explicit CPU reference execution is supported")
    try:
        return await run_in_threadpool(
            authority.execute, tenant_id, workload.payload_bytes,
            normalize_workload_type(workload.workload_type), body.wall_seconds,
        )
    except ExecutionBusyError as exc:
        raise HTTPException(429, "Concurrent execution limit reached", headers={"Retry-After": "1"}) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "Execution custody or supervision failed") from exc


@router.get("/status")
async def execution_status(receipt_object_id: str = Query(pattern=r"^[0-9a-f]{64}$"),
                           tenant_id: str = Depends(authenticated_tenant),
                           authority: ExecutionAuthority = Depends(get_authority)) -> dict:
    try:
        return await run_in_threadpool(authority.status, tenant_id, receipt_object_id)
    except KeyError as exc:
        raise HTTPException(404, "Execution receipt not found") from exc
    except Exception as exc:
        raise HTTPException(503, "Execution custody verification failed") from exc


@router.get("/replay")
async def replay_execution(receipt_object_id: str = Query(pattern=r"^[0-9a-f]{64}$"),
                           tenant_id: str = Depends(authenticated_tenant),
                           authority: ExecutionAuthority = Depends(get_authority)) -> dict:
    try:
        return await run_in_threadpool(authority.replay, tenant_id, receipt_object_id)
    except KeyError as exc:
        raise HTTPException(404, "Execution receipt not found") from exc
    except Exception as exc:
        raise HTTPException(503, "Execution custody verification failed") from exc
