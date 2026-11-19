"""Tensor Engine Router: Endpoints for the Falsifiable Tensor Engine.

Exposes charter verification, hardware cap inspection, network building,
and execution of the three year-one consortium acceptance experiments (E1, E2, E3).
"""

from __future__ import annotations

from typing import Any
import os

import numpy as np
from starlette.concurrency import run_in_threadpool

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from chronus.service.auth_middleware import (
    AuthenticatedIdentity, Role, require_roles,
)
from chronus.tensor.folded_compute import FoldedTensorExecutor

from chronus.tensor.charter import (
    CharterViolation,
    charter,
    program_entry_check,
)
from chronus.tensor.experiments import (
    E1_exactness_oracle,
    E2_symmetry_stress_test,
    E3_honest_1000_node_claim,
    ExperimentResult,
)
from chronus.tensor.network import (
    HARD_CAP_THEOREM,
    build_network,
)
from chronus.tensor.types import (
    RefusedMethod,
    UntrustedApproximation,
    UntrustedResult,
    theory_saving,
)

router = APIRouter(prefix="/v1/tensor", tags=["falsifiable-tensor-engine"])


class TextAuditRequest(BaseModel):
    text: str = Field(..., description="Text or claim to audit against charter hype tokens")


class NetworkBuildRequest(BaseModel):
    n_nodes: int = Field(default=10, ge=1, le=10000, description="Number of nodes/sites")
    topology: str = Field(default="MPS", description="Network topology: MPS, PEPS, or MERA")
    chi_max: int = Field(default=64, ge=1, description="Maximum bond dimension")
    group: str = Field(default="none", description="Symmetry gauge group: none, Z2, U(1), SU(2)")


@router.get("/charter", response_model=dict[str, Any])
def get_charter_status() -> dict[str, Any]:
    """Inspect Consortium Charter v1.0, banned tokens, required audit subsystems, and status."""
    passed = program_entry_check()
    return {
        "version": charter.version,
        "metric": charter.metric,
        "veto_holder": charter.veto_holder.name,
        "required_subsystems": sorted(charter.REQUIRED_SUBSYSTEMS),
        "banned_hype_tokens_count": len(charter.BANNED_HYPE_TOKENS),
        "banned_hype_tokens": sorted(charter.BANNED_HYPE_TOKENS),
        "program_entry_check": passed,
    }


@router.post("/charter/audit", response_model=dict[str, Any])
def audit_claim_text(request: TextAuditRequest) -> dict[str, Any]:
    """Audits text for banned hype language according to the Consortium Charter."""
    is_clean = charter.refuses(request.text)
    if not is_clean:
        return {
            "compliant": False,
            "status": "VIOLATION",
            "message": "Text contains banned hype language violating scientific integrity.",
        }
    return {
        "compliant": True,
        "status": "CLEAN",
        "message": "Text is free of banned hype tokens.",
    }


@router.get("/hardware-caps", response_model=dict[str, Any])
def get_hardware_caps() -> dict[str, Any]:
    """Returns theorem-derived physical hardware bond dimension caps."""
    max_chi = HARD_CAP_THEOREM()
    return {
        "theorem": "HARD_CAP_THEOREM (40 GB HBM3e / RAM, complex128, rank-4 tensor)",
        "chi_max_limit": max_chi,
        "elements_per_tensor": max_chi ** 4,
        "bytes_per_element": 16,
        "bytes_per_tensor_at_cap": (max_chi ** 4) * 16,
        "max_usable_ram_bytes": 40 * 1024 * 1024 * 1024,
        "verdict": "Contractions requesting chi > 26,214 will be honestly refused with UntrustedResult.",
    }


@router.post("/network/build", response_model=dict[str, Any])
def build_tensor_network(request: NetworkBuildRequest) -> dict[str, Any]:
    """Builds an honest block-sparse tensor network and returns memory telemetry."""
    try:
        net, ledger = build_network(
            n_nodes=request.n_nodes,
            topology=request.topology,
            chi_max=request.chi_max,
            group=request.group,
        )
    except UntrustedResult as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Honest Refusal (Hardware Cap Exceeded): {e!s}",
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    mem_sym = net.memory()
    mem_dense = net.dense_equivalent_memory()
    pred_saving = theory_saving(request.group, request.chi_max)
    actual_saving = mem_dense / mem_sym if mem_sym > 0 else 1.0

    return {
        "n_nodes": len(net.nodes),
        "topology": net.topology,
        "chi_max": net.chi_max,
        "group": net.gauge_group,
        "memory_bytes": mem_sym,
        "dense_equivalent_bytes": mem_dense,
        "theoretical_saving_factor": round(pred_saving, 3),
        "actual_saving_factor": round(actual_saving, 3),
        "error_ledger_bound": ledger.global_bound,
    }


@router.get("/experiments/{exp_id}", response_model=dict[str, Any])
def run_or_inspect_experiment(exp_id: str) -> dict[str, Any]:
    """Executes or retrieves one of the three consortium acceptance experiments:

    - E1: Exactness Oracle (reproduces reference statevector at n <= 32)
    - E2: Symmetry Stress Test (Z2, U(1), SU(2) block-sparse memory savings match theory within 5%)
    - E3: Honest 1,000-Node Claim (1D TFIM DMRG, global_bound < 1e-6, n=32 cross-check)
    """
    exp_key = exp_id.upper()
    try:
        if exp_key == "E1":
            result: ExperimentResult = E1_exactness_oracle()
        elif exp_key == "E2":
            result = E2_symmetry_stress_test()
        elif exp_key == "E3":
            result = E3_honest_1000_node_claim()
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown experiment '{exp_id}'. Valid experiments are E1, E2, E3.",
            )
    except (UntrustedApproximation, UntrustedResult, RefusedMethod, CharterViolation) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Experiment honest refusal: {e!s}",
        )
    except NotImplementedError as e:
        # A capability the experiment needs is not implemented: refuse honestly
        # instead of reporting an internal error (or a claim).
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Experiment not runnable: {e!s}",
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Experiment execution failure: {e!s}",
        )

    return {
        "experiment_id": result.experiment_id,
        "status": result.status,
        "passed": result.passed,
        "summary": result.summary,
        "telemetry": result.telemetry,
        "certificate": {
            "tree": str(result.certificate.tree) if result.certificate else None,
            "peak_memory_bytes": result.certificate.peak_memory_bytes if result.certificate else 0,
            "flop_count": result.certificate.flop_count if result.certificate else 0,
            "planner_bound": result.certificate.planner_bound if result.certificate else 0.0,
            "planner_theorem": result.certificate.planner_theorem if result.certificate else None,
        } if result.certificate else None,
    }


class PulviniLinearRequest(BaseModel):
    """Bounded authenticated experimental tensor operation; no source storage."""

    left: list[float] = Field(..., min_length=1, max_length=4096)
    right: list[float] = Field(..., min_length=1, max_length=4096)
    alpha: float = Field(default=1.0, allow_inf_nan=False)
    beta: float = Field(default=1.0, allow_inf_nan=False)
    depth: int = Field(default=4, ge=0, le=16)


@router.post(
    "/pulvini/linear", response_model=dict[str, Any],
    summary="Authenticated, opt-in complete-fold PULVINI linear arithmetic",
)
async def run_pulvini_linear(
    request: PulviniLinearRequest,
    identity: AuthenticatedIdentity = Depends(
        require_roles(Role.DEVELOPER, Role.TENANT_ADMIN,
                      Role.ADMIN, Role.SYSTEM_ADMIN)),
) -> dict[str, Any]:
    """Execute verified numerical folded-channel arithmetic on in-memory inputs.

    Entire input and output fold states (including kernels) are validated.
    The default is OFF: enabling this *does not* qualify hardware or production.
    Never persist raw customer data in this experimental route.
    """
    if os.getenv("CHRONUS_PULVINI_API_ENABLED", "").strip() != "1":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="PULVINI experimental compute endpoint not enabled")
    if not isinstance(identity.tenant_id, str) or not identity.tenant_id.strip():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="authenticated tenant context is required")
    x = np.asarray(request.left, dtype=np.float64)
    y = np.asarray(request.right, dtype=np.float64)
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="non-finite tensor input refused")
    if x.shape != y.shape:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="folded input shapes must match")

    def compute():
        executor = FoldedTensorExecutor(depth=request.depth, max_elements=4096)
        result = executor.execute_folded_linear(
            executor.fold(x), executor.fold(y),
            alpha=request.alpha, beta=request.beta,
        )
        output = executor.materialise(result.operand)
        return {"status": "PASS", "operation": result.operation,
                "output": output.tolist(), "elements": int(output.size),
                "tenant_id": identity.tenant_id,
                "fold_power_d": request.depth,
                "metrics": result.public_metrics(),
                "source_attestation": "UNVERIFIED_UNSIGNED",
                "production_qualification": "UNVERIFIED",
                "hardware_execution": "UNVERIFIED",
                "raw_input_persisted": False}

    try:
        return await run_in_threadpool(compute)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(exc)) from exc
