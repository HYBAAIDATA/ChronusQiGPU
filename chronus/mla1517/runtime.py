from __future__ import annotations
from typing import Callable, Iterable, Any
from .connectors import BackendConnector
from .objects import MLAObject
from .store import PrimeDB
from .scale import ScaleBudget, ScaleController, ScalePoint


class MLA1517Runtime:
    """PRIME-DB -> controlled scale -> MLA1517 GPU/iGPU -> proof."""

    def __init__(
        self,
        db: PrimeDB,
        mode: str | None = None,
        lanes: int = 17,
        allow_cpu_fallback: bool = True,
        require_host_gpu: bool = False,
        allow_host_gpu: bool = True,
        scale_budget: ScaleBudget | None = None,
    ):
        self.db = db
        self.mode = mode
        self.lanes = lanes
        self.connector = BackendConnector(
            mode, allow_cpu_fallback, require_host_gpu, allow_host_gpu
        )
        self.scale_controller = ScaleController(scale_budget)

    def execute(
        self, obj: MLAObject, values: Iterable[Any], kernel: Callable[[Any], Any]
    ) -> dict[str, Any]:
        obj.validate()
        scale_decision = self.scale_controller.authorize(ScalePoint(obj.scale))
        if not scale_decision.accepted:
            raise RuntimeError(f"scale rejected: {scale_decision.reason}")
        items = list(values)
        result, caps, plan = self.connector.execute(items, self.lanes, kernel)
        return {
            "object_id": obj.object_id,
            "requested_mode": caps.requested_mode,
            "selected_mode": caps.selected_mode,
            "execution_backend": caps.execution_backend,
            "connected": caps.connected,
            "host_assist_connected": caps.host_assist_connected,
            "scaling_applied": caps.scaling_applied,
            "scaling_mode": caps.scaling_mode,
            "degraded": caps.degraded,
            "capacity_mode": caps.capacity_mode,
            "backend_reason": caps.reason,
            "scale_control": {
                "accepted": scale_decision.accepted,
                "reason": scale_decision.reason,
                "estimate": scale_decision.estimate.__dict__,
            },
            "input_count": len(items),
            "output_count": len(result),
            "plan": plan,
            "proof": {
                "object_valid": True,
                "cassini_seal": obj.cassini_seal,
                "zeckendorf_valid": True,
            },
            "result": result,
            "performance_claim": "measured_only",
            "unlimited_speed_or_capacity": False,
        }
