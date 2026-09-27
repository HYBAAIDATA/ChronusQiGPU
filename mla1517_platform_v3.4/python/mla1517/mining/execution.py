"""Truth-labelled execution receipts for the canonical mining path."""
from __future__ import annotations

from dataclasses import dataclass

TRUTH_CLASSES = frozenset({"measured_hardware", "measured_cpu_reference", "unavailable", "rejected"})


@dataclass(frozen=True)
class MiningExecutionResult:
    requested_backend: str
    selected_backend: str | None
    actual_backend: str | None
    device_name: str | None
    device_available: bool
    hardware_execution: bool
    degraded: bool
    fallback_used: bool
    hashes_computed: int
    elapsed_seconds: float
    measured_hashrate: float
    truth_class: str

    def __post_init__(self) -> None:
        if self.truth_class not in TRUTH_CLASSES:
            raise ValueError(f"unsupported truth_class: {self.truth_class}")
        if self.hashes_computed < 0 or self.elapsed_seconds < 0:
            raise ValueError("execution counters cannot be negative")
        if self.measured_hashrate < 0:
            raise ValueError("measured_hashrate cannot be negative")
        if self.hardware_execution and not self.device_available:
            raise ValueError("hardware_execution requires an available device")
        if self.truth_class == "measured_hardware" and not self.hardware_execution:
            raise ValueError("measured_hardware requires hardware_execution")
        if self.truth_class == "measured_cpu_reference" and self.hardware_execution:
            raise ValueError("CPU reference cannot be labelled hardware execution")

    @classmethod
    def observed(
        cls,
        *,
        requested_backend: str,
        actual_backend: str | None,
        device_name: str | None,
        device_available: bool,
        hardware_execution: bool,
        hashes_computed: int,
        elapsed_seconds: float,
        degraded: bool = False,
        fallback_used: bool = False,
    ) -> "MiningExecutionResult":
        """Build a receipt from observed counters, never from an estimate."""
        if elapsed_seconds <= 0 or hashes_computed < 0:
            raise ValueError("observed execution requires positive elapsed time")
        if hardware_execution:
            truth_class = "measured_hardware"
        elif actual_backend == "cpu_reference":
            truth_class = "measured_cpu_reference"
        elif actual_backend is None:
            truth_class = "unavailable"
        else:
            truth_class = "rejected"
        return cls(
            requested_backend=requested_backend,
            selected_backend=actual_backend,
            actual_backend=actual_backend,
            device_name=device_name,
            device_available=device_available,
            hardware_execution=hardware_execution,
            degraded=degraded,
            fallback_used=fallback_used,
            hashes_computed=hashes_computed,
            elapsed_seconds=elapsed_seconds,
            measured_hashrate=hashes_computed / elapsed_seconds,
            truth_class=truth_class,
        )
