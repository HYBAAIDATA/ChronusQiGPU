"""Opt-in Chronus execution of EUCLID-selected ARC geometry primitives.

EUCLID still selects programmes and owns learning/reward. This adapter only
executes a chosen integer symmetry through an injected Chronus runtime. It
inspects no task identifier, training answer or withheld output.
"""

from __future__ import annotations

from itertools import count
from typing import Any

from .grid_primitives import Grid

D4_PRIMITIVES = frozenset(("rot90", "rot180", "rot270", "flip_h", "flip_v", "transpose"))


class ChronusARCGeometry:
    def __init__(
        self,
        runtime: Any,
        *,
        tenant: str,
        workload_prefix: str,
        execution_policy: str = "standalone_software",
        required_adapter_id: str | None = None,
    ) -> None:
        if not tenant or not workload_prefix:
            raise ValueError("tenant and workload prefix required")
        self.runtime = runtime
        self.tenant = tenant
        self.prefix = workload_prefix
        self.policy = execution_policy
        self.required_adapter_id = required_adapter_id
        self._sequence = count()
        self.last_receipt: dict[str, Any] | None = None

    def __call__(self, operation: str, grid: Grid) -> Grid:
        from chronus.virtual_igpu.abi import Workload

        if operation not in D4_PRIMITIVES:
            raise ValueError("Chronus ARC adapter accepts only declared D4 primitives")
        result = self.runtime.submit(
            Workload(
                id=f"{self.prefix}-{next(self._sequence)}",
                tenant=self.tenant,
                kind="grid_geometry",
                input={"op": "d4", "grid": grid},
                execution_policy=self.policy,
                required_adapter_id=self.required_adapter_id,
            )
        )
        if (
            result.status != "ok"
            or result.receipt.get("verification", {}).get("verdict") != "match"
        ):
            raise RuntimeError("Chronus ARC geometry execution failed verification")
        self.last_receipt = result.receipt
        return result.output["transforms"][operation]
