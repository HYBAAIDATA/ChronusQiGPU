"""QiGPU orchestration: hardware-agnostic execution surface inventory.

The QiGPU model treats the mathematical substrate as primary and hardware as
an interchangeable surface. The CPU reference surface is always present. A
client-provisioned accelerator surface (OpenCL GPU) is available only when it
was explicitly enabled and its startup known-answer tests passed; otherwise
execution stays on the CPU substrate and telemetry says so.
"""

from dataclasses import dataclass
from typing import Any

from chronus.core.workload_alias import externalize_workload_type
from chronus.execution.reference import ExecutionRouter


@dataclass(frozen=True)
class ExecutionSurface:
    surface_id: str
    kind: str
    execution_mode: str
    workloads: list[str]
    available: bool
    telemetry: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        # Customer-visible inventory uses sealed class names only.
        return {
            "surface_id": self.surface_id,
            "kind": self.kind,
            "execution_mode": self.execution_mode,
            "workloads": sorted(
                {externalize_workload_type(name) for name in self.workloads}
            ),
            "available": self.available,
            "telemetry": self.telemetry,
        }


class QiGPUOrchestrator:
    """Inventory execution surfaces and resolve client routing preference."""

    def __init__(self, router: ExecutionRouter) -> None:
        self.router = router

    def surfaces(self) -> list[ExecutionSurface]:
        result = []
        for name in self.router.list_backends():
            backend = self.router._backends[name]
            telemetry: dict[str, Any] = {}
            if hasattr(backend, "probe_silicon"):
                telemetry = backend.probe_silicon()
            result.append(
                ExecutionSurface(
                    surface_id=name,
                    kind=(
                        "client_accelerator"
                        if hasattr(backend, "probe_silicon")
                        else "cpu_substrate"
                    ),
                    execution_mode=getattr(
                        backend, "execution_mode", "SOFTWARE_EXECUTION"
                    ),
                    workloads=sorted(backend.supported_workloads),
                    available=True,
                    telemetry=telemetry,
                )
            )
        return result

    def resolve(self, workload_type: str, preference: str | None) -> str:
        """Return the surface that would execute a workload, or fail closed."""
        if preference is not None:
            backend = self.router._backends.get(preference)
            if backend is None:
                raise ValueError(f"execution surface '{preference}' is not provisioned")
            if not backend.supports(workload_type):
                raise ValueError(
                    f"surface '{preference}' does not support {workload_type}"
                )
            return preference
        for name, backend in self.router._backends.items():
            if backend.supports(workload_type):
                return name
        raise ValueError(f"no execution surface supports {workload_type}")

    def auto_select(self, workload_type: str) -> tuple[str, str]:
        """Climb into a provisioned accelerator surface when one supports the
        workload; otherwise operate on the CPU substrate. Fails closed when no
        surface supports the workload."""
        for name, backend in self.router._backends.items():
            if hasattr(backend, "probe_silicon") and backend.supports(workload_type):
                return name, "client-accelerator"
        for name, backend in self.router._backends.items():
            if backend.supports(workload_type):
                return name, "cpu-substrate"
        raise ValueError(f"no execution surface supports {workload_type}")

    def inventory(self) -> dict[str, Any]:
        surfaces = self.surfaces()
        return {
            "substrate": "mathematical",
            "hardware_agnostic": True,
            "surfaces": [surface.to_dict() for surface in surfaces],
            "default_surface": next(
                (s.surface_id for s in surfaces if s.kind == "cpu_substrate"), None
            ),
            "accelerator_surfaces": [
                s.surface_id for s in surfaces if s.kind == "client_accelerator"
            ],
        }
