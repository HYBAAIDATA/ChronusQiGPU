"""Internal extension APIs, separate from the small public facade."""

from typing import Callable, Protocol
from dataclasses import dataclass
from .contracts import (
    BackendCapabilities,
    CircuitIR,
    CompiledArtifact,
    Estimate,
    ExecutionRequest,
    JobResult,
    JobStatus,
    OptimizationResult,
    ParameterBindings,
)


class Compiler(Protocol):
    def compile(self, circuit: CircuitIR) -> CompiledArtifact: ...


class ExecutionJob(Protocol):
    @property
    def job_id(self) -> str: ...
    def status(self) -> JobStatus: ...
    def result(self, timeout: float | None = None) -> JobResult: ...
    def cancel(self) -> bool: ...


class Backend(Protocol):
    def capabilities(self) -> BackendCapabilities: ...
    def submit(
        self, request: ExecutionRequest, *, idempotency_key: str | None = None
    ) -> ExecutionJob: ...
    def get_job(self, job_id: str) -> ExecutionJob: ...
    def close(self) -> None: ...


class Estimator(Protocol):
    def estimate(self, request: ExecutionRequest) -> Estimate: ...


class Optimizer(Protocol):
    def minimize(
        self,
        evaluate: Callable[[ParameterBindings], Estimate],
        candidates: tuple[ParameterBindings, ...],
        *,
        max_iterations: int
    ) -> OptimizationResult: ...


@dataclass(frozen=True)
class ExecutionPlan:
    requests: tuple[ExecutionRequest, ...]
    method: str


class ErrorManager(Protocol):
    def prepare(self, request: ExecutionRequest) -> ExecutionPlan: ...


class NoErrorManagement:
    def prepare(self, request: ExecutionRequest) -> ExecutionPlan:
        return ExecutionPlan((request,), "none")
