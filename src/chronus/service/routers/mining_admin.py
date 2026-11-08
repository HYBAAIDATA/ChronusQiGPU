"""REST API routes for Hashrate Intelligence & Mining Administration."""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from chronus.execution.mining_admin import MiningAdminEngine
from chronus.service.dependencies import get_current_tenant

router = APIRouter(prefix="/v1/mining/admin", tags=["mining_admin"])
_engine = MiningAdminEngine.get_instance()


class StartMiningRequest(BaseModel):
    base_hashrate_eh_s: Optional[float] = Field(None, description="Target base hashrate in EH/s")
    active_warps: Optional[int] = Field(None, description="Number of active execution warps/blades")


class ConfigureCapacityRequest(BaseModel):
    base_hashrate_eh_s: Optional[float] = Field(None, description="Base hashrate in EH/s")
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


@router.get("/status", summary="Get real-time mining administration status")
async def get_mining_status(
    tenant_id: str = Depends(get_current_tenant),
) -> Dict[str, Any]:
    return _engine.get_status()


@router.post("/start", summary="Start mining engine with specified capacity")
async def start_mining(
    req: StartMiningRequest,
    tenant_id: str = Depends(get_current_tenant),
) -> Dict[str, Any]:
    return _engine.start_mining(
        base_hashrate_eh_s=req.base_hashrate_eh_s,
        active_warps=req.active_warps,
    )


@router.post("/stop", summary="Stop active mining engine")
async def stop_mining(
    tenant_id: str = Depends(get_current_tenant),
) -> Dict[str, Any]:
    return _engine.stop_mining()


@router.post("/configure", summary="Dynamically configure hashrate and hardware parameters")
async def configure_capacity(
    req: ConfigureCapacityRequest,
    tenant_id: str = Depends(get_current_tenant),
) -> Dict[str, Any]:
    return _engine.configure_hashrate_and_capacity(
        base_hashrate_eh_s=req.base_hashrate_eh_s,
        active_warps=req.active_warps,
        core_voltage_v=req.core_voltage_v,
        fan_speed_pct=req.fan_speed_pct,
    )


@router.post("/intelligence", summary="Rebalance 5-mode meta-intelligence distribution")
async def configure_intelligence(
    req: ConfigureIntelligenceRequest,
    tenant_id: str = Depends(get_current_tenant),
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
    tenant_id: str = Depends(get_current_tenant),
) -> Dict[str, Any]:
    try:
        return _engine.apply_causal_intervention(req.intervention)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/anomaly/inject", summary="Inject reorg or stratum poisoning perturbation")
async def inject_anomaly(
    tenant_id: str = Depends(get_current_tenant),
) -> Dict[str, Any]:
    return _engine.inject_anomaly()


@router.post("/anomaly/heal", summary="Execute 1-cycle DSW instanton monopole cobordism heal")
async def execute_dsw_heal(
    tenant_id: str = Depends(get_current_tenant),
) -> Dict[str, Any]:
    return _engine.execute_dsw_heal()
