"""Validated configuration for the native exact public API."""

from dataclasses import dataclass
from math import isfinite
from .exceptions import ConfigurationError, CapabilityError


@dataclass(frozen=True)
class PipelineConfig:
    backend: str = "auto"
    execution_mode: str = "exact_vqc"
    error_management: str = "none"
    max_amplitudes: int = 1 << 20
    max_qubits: int = 10_000
    shots: int | None = None
    seed: int = 1234
    job_timeout_seconds: float = 300.0
    differential: bool = True
    custody: bool = False
    replay: bool = False
    custody_dir: str | None = None

    def __post_init__(self):
        if self.execution_mode not in {"exact_vqc", "simulation", "nisq", "fault_tolerant"}:
            raise ConfigurationError("unknown execution_mode")
        if self.execution_mode != "exact_vqc":
            raise CapabilityError(
                "This adapter supports exact_vqc only; no simulator, QPU or logical-QEC substitution"
            )
        if self.error_management != "none":
            raise CapabilityError("No mitigation or logical-QEC execution plan is configured")
        if self.backend not in {"auto", "exact_algebraic", "stabilizer"}:
            raise CapabilityError(
                "Public native adapter supports auto, exact_algebraic and stabilizer only"
            )
        for name in ("max_amplitudes", "max_qubits"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ConfigurationError(f"{name} must be a positive integer")
        if self.shots is not None and (type(self.shots) is not int or self.shots <= 0):
            raise ConfigurationError("shots must be a positive integer or None")
        if type(self.seed) is not int or not 0 <= self.seed < 2**32:
            raise ConfigurationError("seed must be an integer in [0, 2**32)")
        if (
            type(self.job_timeout_seconds) not in (int, float)
            or not isfinite(self.job_timeout_seconds)
            or self.job_timeout_seconds <= 0
        ):
            raise ConfigurationError("job timeout must be positive and finite")
        for name in ("differential", "custody", "replay"):
            if type(getattr(self, name)) is not bool:
                raise ConfigurationError(f"{name} must be a bool")
        if self.replay and not self.custody:
            raise ConfigurationError("replay requires custody")
