"""Canonical Chronus production runtime: one system, two modes.

Mode 1 - independent: Chronus is the GPU. The software fabric executes the
canonical workload ABI and mathematical pipeline on ordinary host silicon. No
physical GPU or vendor runtime is required.

Mode 2 - scale_stack: the same governed execution contract binds an available
physical accelerator stack. If this mode is selected, absence of a usable
physical adapter fails closed. That requirement never leaks into independent
mode.

Production readiness is established by an executable voyage, not module
presence: verified Virtual iGPU work, the QSDL/Hamiltonian/evolution/EMP/
reconstruction pipeline, and QSDL-to-QX sealed execution.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import math
from pathlib import Path
from typing import Any, Iterable

from .virtual_igpu.abi import ABI_VERSION, ExecutionPolicy, Workload, WorkloadKind
from .virtual_igpu.adapters import Adapter, ChronusSoftwareFabricAdapter, default_adapters
from .virtual_igpu.runtime import RuntimeDaemon

PRODUCTION_CONTRACT_VERSION = "chronus.production/1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChronusMode(str, Enum):
    INDEPENDENT = "independent"
    SCALE_STACK = "scale_stack"


STARTUP_QSDL = (
    "scene chronus_startup { "
    "manifold M32 "
    "object probe { geometry sphere(radius=1.0, center=(0,0,0)) "
    "material glass { dielectric=1.5 absorption=0.001 quantum { resonance=[0.5] } } } "
    "light sun { type=directional position=(1,1,1) intensity=1.0 driving=zero() } "
    "camera { resolution=(160,90) fov=60.0 position=(0,0,5) } "
    "quality { layers=2 evolution_steps=12 seed=0 } "
    "}"
)


@dataclass(frozen=True)
class ChronusProductionReport:
    passed: bool
    mode: str
    physical_gpu_required: bool
    physical_gpu_bound: bool
    two_mode_contract: dict[str, Any]
    execution: dict[str, Any]
    math_pipeline: dict[str, Any]
    qx_pipeline: dict[str, Any]
    hardware_claimed: bool = False
    physical_qpu_claimed: bool = False
    schema: str = "chronus.production-voyage/1"
    abi_version: str = ABI_VERSION
    recorded_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if not data["recorded_at"]:
            data["recorded_at"] = _utc_now()
        return data


class ChronusProductionRuntime:
    """One canonical runtime for independent and accelerator-scaling Chronus."""

    def __init__(
        self,
        root: str | Path,
        *,
        mode: ChronusMode | str = ChronusMode.INDEPENDENT,
        adapters: Iterable[Adapter] | None = None,
        tenant: str = "chronus-production",
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.mode = mode if isinstance(mode, ChronusMode) else ChronusMode(str(mode))
        self.tenant = str(tenant)
        if adapters is None:
            if self.mode is ChronusMode.INDEPENDENT:
                resolved = [ChronusSoftwareFabricAdapter()]
            else:
                resolved = default_adapters(include_cpu_emulator=False)
        else:
            resolved = list(adapters)
        self.daemon = RuntimeDaemon(
            adapters=resolved,
            store_dir=self.root / "virtual-igpu",
            runtime_identity=f"chronus.production:{self.mode.value}:{ABI_VERSION}",
        )
        self._last_report: dict[str, Any] | None = None

    @staticmethod
    def two_mode_contract() -> dict[str, Any]:
        return {
            "system": "Chronus",
            "modes": {
                ChronusMode.INDEPENDENT.value: {
                    "meaning": "chronus_is_the_gpu",
                    "physical_gpu_required": False,
                    "vendor_runtime_required": False,
                },
                ChronusMode.SCALE_STACK.value: {
                    "meaning": "scale_available_gpu_stack",
                    "physical_gpu_required_when_selected": True,
                    "silent_software_fallback": False,
                },
            },
            "single_execution_abi": ABI_VERSION,
        }

    def _execution_probe(self) -> dict[str, Any]:
        if self.mode is ChronusMode.INDEPENDENT:
            policy = ExecutionPolicy.STANDALONE_SOFTWARE.value
            fallback = True
        else:
            policy = ExecutionPolicy.PREFERRED_ACCELERATOR.value
            fallback = False

        workload = Workload(
            id=f"chronus-production-{self.mode.value}-matmul",
            kind=WorkloadKind.TENSOR_OP,
            tenant=self.tenant,
            input={
                "op": "matmul",
                "a": [[1.0, 2.0], [3.0, 5.0]],
                "b": [[8.0, 13.0], [21.0, 34.0]],
                "output_shape": [2, 2],
            },
            execution_policy=policy,
            allow_software_fallback=fallback,
            metadata={"purpose": "chronus_production_startup_gate"},
        )
        result = self.daemon.submit(workload)
        verification = dict(result.receipt.get("verification", {}))
        if result.status != "ok":
            raise RuntimeError(f"Chronus execution probe status={result.status!r}")
        if verification.get("verdict") != "match":
            raise RuntimeError(
                "Chronus execution probe was not independently verified: "
                f"{verification.get('verdict')!r}"
            )
        if self.mode is ChronusMode.INDEPENDENT and result.actual_adapter_id != "chronus-software-fabric":
            raise RuntimeError("independent mode did not execute on the Chronus software fabric")
        if self.mode is ChronusMode.SCALE_STACK:
            adapter_id = result.actual_adapter_id.lower()
            if any(token in adapter_id for token in ("software", "cpu", "emulator")):
                raise RuntimeError("scale_stack selected a software/reference adapter")

        return {
            "status": result.status,
            "requested_policy": result.requested_policy,
            "actual_adapter_id": result.actual_adapter_id,
            "actual_device_id": result.actual_device_id,
            "route_reason": result.route_reason,
            "trust_class": result.trust_class,
            "hardware_rooted": result.hardware_rooted,
            "verification": verification.get("verdict"),
            "verifier": verification.get("verifier"),
            "evidence_digest": result.evidence_digest,
            "receipt_id": result.receipt.get("receipt_id"),
        }

    @staticmethod
    def _math_pipeline_probe() -> dict[str, Any]:
        from .v33 import ChronosEngine

        result = ChronosEngine(
            n_faces=32,
            layers=2,
            enable_emp=True,
            emp_readout_fraction=0.25,
        ).render(STARTUP_QSDL)
        distribution_sum = float(result.distribution.sum())
        passed = bool(
            math.isfinite(float(result.energy))
            and result.frame_shape == (90, 160, 3)
            and result.total_pixels == 160 * 90
            and result.rendered_pixels_hit > 0
            and abs(distribution_sum - 1.0) <= 1e-8
            and result.emp_enabled
        )
        if not passed:
            raise RuntimeError("Chronos QSDL mathematical pipeline startup probe failed")
        return {
            "passed": True,
            "pipeline": "QSDL -> Hamiltonian -> evolution/EMP -> expectation readout -> reconstruction",
            "energy": float(result.energy),
            "frame_shape": list(result.frame_shape),
            "rendered_pixels_hit": int(result.rendered_pixels_hit),
            "total_pixels": int(result.total_pixels),
            "distribution_sum": distribution_sum,
            "emp_enabled": bool(result.emp_enabled),
            "fidelity_to_ground": (
                None if result.fidelity_to_ground is None else float(result.fidelity_to_ground)
            ),
            "render_backend": result.render_backend,
        }

    @staticmethod
    def _qx_pipeline_probe() -> dict[str, Any]:
        from .v33.qx_bridge import execute_qsdl_qx_reference

        report = execute_qsdl_qx_reference(STARTUP_QSDL, n_faces=32)
        if not report.get("passed"):
            raise RuntimeError("Chronos QSDL-to-QX execution contract probe failed")
        return report

    def startup_voyage(self) -> dict[str, Any]:
        """Execute the canonical Chronus software production voyage."""
        self.daemon.attach()

        execution = self._execution_probe()
        math_pipeline = self._math_pipeline_probe()
        qx_pipeline = self._qx_pipeline_probe()

        report = ChronusProductionReport(
            passed=True,
            mode=self.mode.value,
            physical_gpu_required=self.mode is ChronusMode.SCALE_STACK,
            physical_gpu_bound=self.mode is ChronusMode.SCALE_STACK,
            two_mode_contract=self.two_mode_contract(),
            execution=execution,
            math_pipeline=math_pipeline,
            qx_pipeline=qx_pipeline,
            hardware_claimed=bool(execution["hardware_rooted"]),
            physical_qpu_claimed=False,
            recorded_at=_utc_now(),
        ).as_dict()

        verified = verify_startup_report(report)
        if not verified["passed"]:
            raise RuntimeError(
                "Chronus production voyage failed semantic verification: "
                f"{verified['checks']}"
            )
        self._last_report = report
        return report

    def health(self) -> dict[str, Any]:
        return {
            "schema": "chronus.production-health/1",
            "mode": self.mode.value,
            "runtime": self.daemon.health(),
            "two_mode_contract": self.two_mode_contract(),
            "startup_voyage": self._last_report,
        }

    def stop(self) -> None:
        self.daemon.stop()


def verify_startup_report(report: dict[str, Any]) -> dict[str, Any]:
    """Semantic verifier for a recovered Chronus production-voyage record."""
    modes = ((report.get("two_mode_contract") or {}).get("modes") or {})
    execution = report.get("execution") or {}
    math_pipeline = report.get("math_pipeline") or {}
    qx_pipeline = report.get("qx_pipeline") or {}
    mode = str(report.get("mode", ""))

    checks = {
        "schema": report.get("schema") == "chronus.production-voyage/1",
        "reported_pass": report.get("passed") is True,
        "two_modes_present": {"independent", "scale_stack"} <= set(modes),
        "math_pipeline": math_pipeline.get("passed") is True,
        "qx_pipeline": qx_pipeline.get("passed") is True,
        "execution_ok": execution.get("status") == "ok",
        "execution_recomputed": execution.get("verification") == "match",
        "no_physical_qpu_claim": report.get("physical_qpu_claimed") is False,
    }
    if mode == ChronusMode.INDEPENDENT.value:
        checks.update(
            {
                "independent_no_gpu_dependency": report.get("physical_gpu_required") is False,
                "independent_software_fabric": execution.get("actual_adapter_id") == "chronus-software-fabric",
                "independent_no_hardware_claim": report.get("hardware_claimed") is False,
            }
        )
    elif mode == ChronusMode.SCALE_STACK.value:
        adapter_id = str(execution.get("actual_adapter_id", "")).lower()
        checks.update(
            {
                "scale_requires_selected_device": report.get("physical_gpu_required") is True,
                "scale_physical_bound": report.get("physical_gpu_bound") is True,
                "scale_not_software_adapter": not any(
                    token in adapter_id for token in ("software", "cpu", "emulator")
                ),
            }
        )
    else:
        checks["known_mode"] = False

    return {
        "schema": "chronus.production-voyage.verify/1",
        "passed": all(bool(value) for value in checks.values()),
        "checks": checks,
        "mode": mode,
        "adapter_id": execution.get("actual_adapter_id"),
    }


__all__ = [
    "PRODUCTION_CONTRACT_VERSION",
    "STARTUP_QSDL",
    "ChronusMode",
    "ChronusProductionReport",
    "ChronusProductionRuntime",
    "verify_startup_report",
]
