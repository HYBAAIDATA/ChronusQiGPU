"""REST API routes for Hashrate Intelligence & Mining Administration."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from chronus.execution.mining_admin import MiningAdminEngine
from chronus.service.mining_operator import get_mining_admin_operator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/mining/admin", tags=["mining_admin"])
_engine = MiningAdminEngine.get_instance()


class StartMiningRequest(BaseModel):
    base_hashrate_eh_s: Optional[float] = Field(
        None, gt=0, le=1.0, description="Target base hashrate in EH/s. The hard cap is 1."
    )
    active_warps: Optional[int] = Field(None, description="Number of active execution warps/blades")


class ConfigureCapacityRequest(BaseModel):
    base_hashrate_eh_s: Optional[float] = Field(
        None, gt=0, le=1.0, description="Base hashrate in EH/s. The hard cap is 1."
    )
    active_warps: Optional[int] = Field(None, description="Active compute warps")
    core_voltage_v: Optional[float] = Field(None, description="ASIC core voltage in volts")
    fan_speed_pct: Optional[float] = Field(None, description="Cooling fan speed in percent")


class ConfigureIntelligenceRequest(BaseModel):
    predictive: float = Field(..., description="Predictive mode weight")
    causal: float = Field(..., description="Causal mode weight")
    counterfactual: float = Field(..., description="Counterfactual mode weight")
    topological: float = Field(..., description="Topological mode weight")
    geometric: float = Field(..., description="Geometric mode weight")


class CausalInterventionRequest(BaseModel):
    intervention: str = Field(..., description="Intervention type: OBSERVATIONAL, FAN_100_PCT, UNDERVOLT_1_10V, GRID_CURTAILMENT")


class ConfigureStealthRequest(BaseModel):
    max_configured_eh_s: Optional[float] = Field(
        None, gt=0, le=1.0, description="Configured hashrate cap in EH/s. Cannot exceed 1."
    )
    stealth_target_eh_s: Optional[float] = Field(
        None, gt=0, le=1.0, description="Active throttle in EH/s. Cannot exceed the cap."
    )
    never_consecutive_blocks: Optional[bool] = Field(None, description="Enforce 'Never Two Consecutive Blocks' rule")
    persistent_presence: Optional[bool] = Field(None, description="Maintain persistent socket presence with steady heartbeat shares")


class SimulatePatroclusRequest(BaseModel):
    pools: Optional[list] = Field(default=None, description="Deprecated and unsupported: local loopback fixture names are fixed; omit pools")


@router.get("/status", summary="Get real-time mining administration status")
async def get_mining_status(
    tenant_id: str = Depends(get_mining_admin_operator),
) -> Dict[str, Any]:
    return _engine.get_status()


@router.post("/start", summary="Start mining engine with specified capacity")
async def start_mining(
    req: StartMiningRequest,
    tenant_id: str = Depends(get_mining_admin_operator),
) -> Dict[str, Any]:
    try:
        return _engine.start_mining(
            base_hashrate_eh_s=req.base_hashrate_eh_s,
            active_warps=req.active_warps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/stop", summary="Stop active mining engine")
async def stop_mining(
    tenant_id: str = Depends(get_mining_admin_operator),
) -> Dict[str, Any]:
    return _engine.stop_mining()


@router.post("/configure", summary="Dynamically configure hashrate and hardware parameters")
async def configure_capacity(
    req: ConfigureCapacityRequest,
    tenant_id: str = Depends(get_mining_admin_operator),
) -> Dict[str, Any]:
    try:
        return _engine.configure_hashrate_and_capacity(
            base_hashrate_eh_s=req.base_hashrate_eh_s,
            active_warps=req.active_warps,
            core_voltage_v=req.core_voltage_v,
            fan_speed_pct=req.fan_speed_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/intelligence", summary="Rebalance 5-mode meta-intelligence distribution")
async def configure_intelligence(
    req: ConfigureIntelligenceRequest,
    tenant_id: str = Depends(get_mining_admin_operator),
) -> Dict[str, Any]:
    return _engine.configure_intelligence_modes(
        predictive=req.predictive,
        causal=req.causal,
        counterfactual=req.counterfactual,
        topological=req.topological,
        geometric=req.geometric,
    )


@router.post("/intervene", summary="Execute Pearl Level 2 causal do(X) intervention")
async def apply_intervention(
    req: CausalInterventionRequest,
    tenant_id: str = Depends(get_mining_admin_operator),
) -> Dict[str, Any]:
    try:
        return _engine.apply_causal_intervention(req.intervention)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/anomaly/inject", summary="Inject reorg or stratum poisoning perturbation")
async def inject_anomaly(
    tenant_id: str = Depends(get_mining_admin_operator),
) -> Dict[str, Any]:
    return _engine.inject_anomaly()


@router.post("/anomaly/heal", summary="Reset the anomaly flags set by /anomaly/inject (no repair is performed; repair_performed=false)")
async def execute_dsw_heal(
    tenant_id: str = Depends(get_mining_admin_operator),
) -> Dict[str, Any]:
    return _engine.execute_dsw_heal()


@router.get("/patroclus", summary="Get Patroclus Gateway & 600 Myrmidon Searchers telemetry")
async def get_patroclus_telemetry(
    tenant_id: str = Depends(get_mining_admin_operator),
) -> Dict[str, Any]:
    return _engine.get_patroclus_status()


@router.post("/stealth", summary="Configure stealth hashrate shaping and block policies")
async def configure_stealth(
    req: ConfigureStealthRequest,
    tenant_id: str = Depends(get_mining_admin_operator),
) -> Dict[str, Any]:
    try:
        return _engine.configure_stealth(
            max_configured_eh_s=req.max_configured_eh_s,
            stealth_target_eh_s=req.stealth_target_eh_s,
            never_consecutive_blocks=req.never_consecutive_blocks,
            persistent_presence=req.persistent_presence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/patroclus/simulate",
    summary="Run a local-loopback Stratum rehearsal (NOT live pool acceptance)",
)
async def simulate_patroclus_session(
    req: SimulatePatroclusRequest,
    tenant_id: str = Depends(get_mining_admin_operator),
) -> Dict[str, Any]:
    """Rehearse the fixed local fixtures; never report external pool acceptance.

    The underlying runner binds 127.0.0.1 fixture servers. Its responses do
    not qualify a deployment, certify a device or prove live mining shares.
    """
    if req.pools is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only the fixed local-loopback fixtures are supported; omit pools.",
        )

    from chronus.execution.master_e2e_engine import execute_master_end_to_end

    try:
        await execute_master_end_to_end()
    except Exception as exc:
        logger.exception("Local loopback Stratum rehearsal failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Local-loopback Stratum rehearsal failed; no production evidence.",
        ) from exc

    return {
        "status": "REHEARSAL_COMPLETED",
        "evidence_class": "LOCAL_LOOPBACK_FIXTURE",
        "transport": "127.0.0.1",
        "live_pool_acceptance": "UNAVAILABLE",
        "pool_acknowledgements": [],
        "production_qualified": False,
        "decision_points": [],
        "message": (
            "Fixed local-loopback Stratum fixtures completed. "
            "No external pool sessions or accepted shares were verified."
        ),
    }
