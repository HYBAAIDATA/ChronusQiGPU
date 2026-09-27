from __future__ import annotations
from dataclasses import dataclass
import os
from typing import Callable, Iterable, TypeVar
from .host import HostGPUPlan, execute_reference

T = TypeVar("T")


@dataclass(frozen=True)
class BackendCapabilities:
    requested_mode: str
    selected_mode: str
    execution_backend: str
    available: bool
    degraded: bool
    connected: bool
    host_assist_connected: bool
    scaling_applied: bool
    scaling_mode: str
    capacity_mode: str
    reason: str


class BackendConnector:
    """MLA1517-first connector; host GPU is an optional scale-assist, not the product."""

    VALID_MODES = {"auto", "mla1517_gpu", "integrated_iGPU", "host_gpu_overlay", "cpu_reference"}

    def __init__(
        self,
        requested_mode: str | None = None,
        allow_cpu_fallback: bool = True,
        require_host_gpu: bool = False,
        allow_host_gpu: bool = True,
    ):
        env_mode = os.getenv("MLA1517_MODE", "mla1517_gpu")
        self.requested_mode = requested_mode or env_mode
        if self.requested_mode not in self.VALID_MODES:
            raise ValueError("unsupported backend mode")
        self.allow_cpu_fallback = allow_cpu_fallback
        self.require_host_gpu = require_host_gpu
        self.allow_host_gpu = allow_host_gpu
        self.host_gpu_connected = os.getenv("MLA1517_HOST_GPU_CONNECTED", "0") == "1"
        self.host_assist_enabled = os.getenv("MLA1517_HOST_GPU_ASSIST", "0") == "1"
        self.mla_gpu_connected = os.getenv("MLA1517_GPU_CONNECTED", "0") == "1"
        self.host_gpu_backend = os.getenv("MLA1517_HOST_GPU_BACKEND", "host_gpu")

    def selected_mode(self) -> str:
        if self.requested_mode == "auto":
            return (
                "mla1517_gpu"
                if self.mla_gpu_connected
                else (
                    "host_gpu_overlay"
                    if self.allow_host_gpu and self.host_gpu_connected
                    else "cpu_reference"
                )
            )
        return self.requested_mode

    def capabilities(self) -> BackendCapabilities:
        selected = self.selected_mode()
        host_assist = bool(
            self.host_gpu_connected and self.host_assist_enabled and self.allow_host_gpu
        )
        if selected == "cpu_reference":
            return BackendCapabilities(
                self.requested_mode,
                selected,
                "cpu_reference",
                True,
                self.requested_mode != "cpu_reference",
                False,
                False,
                False,
                "reference",
                "bounded_reference",
                "deterministic CPU reference backend",
            )
        if selected in {"mla1517_gpu", "integrated_iGPU"} and self.mla_gpu_connected:
            return BackendCapabilities(
                self.requested_mode,
                selected,
                "mla1517_gpu",
                True,
                False,
                True,
                host_assist,
                True,
                "mla1517_native_plus_host_assist" if host_assist else "mla1517_native",
                "candidate_exponential_measured_only",
                (
                    "MLA1517 GPU/iGPU connected; host assist enabled"
                    if host_assist
                    else "MLA1517 GPU/iGPU connected"
                ),
            )
        if selected == "host_gpu_overlay" and self.host_gpu_connected:
            return BackendCapabilities(
                self.requested_mode,
                selected,
                self.host_gpu_backend,
                True,
                False,
                True,
                False,
                True,
                "host_overlay_only",
                "bounded_measured",
                "host GPU overlay selected without MLA1517 GPU",
            )
        if self.require_host_gpu and selected == "host_gpu_overlay":
            return BackendCapabilities(
                self.requested_mode,
                selected,
                selected,
                False,
                False,
                False,
                False,
                False,
                "unavailable",
                "unavailable",
                "required host GPU is not connected",
            )
        if self.allow_cpu_fallback:
            return BackendCapabilities(
                self.requested_mode,
                selected,
                "cpu_reference",
                True,
                True,
                False,
                False,
                False,
                "reference_fallback",
                "bounded_reference",
                "MLA1517 GPU unavailable; CPU conformance fallback",
            )
        return BackendCapabilities(
            self.requested_mode,
            selected,
            selected,
            False,
            False,
            False,
            False,
            False,
            "unavailable",
            "unavailable",
            "MLA1517 GPU unavailable and fallback disabled",
        )

    def execute(
        self, values: Iterable[T], lanes: int, kernel: Callable[[T], T]
    ) -> tuple[list[T], BackendCapabilities, dict]:
        caps = self.capabilities()
        if not caps.available:
            raise RuntimeError(caps.reason)
        items = list(values)
        plan = HostGPUPlan(len(items), lanes, caps.selected_mode, caps.execution_backend)
        result = execute_reference(items, plan, kernel)
        return result, caps, plan.manifest()
