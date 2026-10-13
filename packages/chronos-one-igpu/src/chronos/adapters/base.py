"""Backend adapter contracts and execution receipts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol, Sequence
import hashlib, json, time

@dataclass(frozen=True)
class StageSpec:
    name: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    latency: int
    width: int

@dataclass(frozen=True)
class PipelineSpec:
    stages: tuple[StageSpec, ...]
    working_width: int = 256
    field: str = "Z/(2^width)Z"
    fail_closed: bool = True
    def digest(self) -> str:
        payload = {"stages":[s.__dict__ for s in self.stages], "working_width":self.working_width, "field":self.field, "fail_closed":self.fail_closed}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

@dataclass(frozen=True)
class Capability:
    name: str
    kind: str
    driver: str
    device_id: str
    exact_integer_arithmetic: bool
    hardware_accelerated: bool

@dataclass(frozen=True)
class CompiledKernel:
    backend: str
    kernel_digest: str
    pipeline_spec: PipelineSpec

@dataclass(frozen=True)
class BatchResult:
    records: tuple[Any, ...]
    backend: str
    kernel_digest: str
    latency_seconds: float
    measured: bool

@dataclass(frozen=True)
class ExecutionReceipt:
    backend: str
    backend_kind: str
    device_id: str
    kernel_digest: str
    pipeline_spec: str
    latency_cycles: int | None
    throughput_rps: float
    power_watts: float | None
    measured: bool
    timestamp: str
    signature: str | None

class BackendAbsent(RuntimeError): pass
class CompileError(RuntimeError): pass
class DispatchError(RuntimeError): pass

class Adapter(Protocol):
    name: str
    kind: str
    fail_closed: bool
    def probe(self) -> Capability: ...
    def compile(self, spec: PipelineSpec) -> CompiledKernel: ...
    def dispatch(self, kernel: CompiledKernel, batch: Sequence[int]) -> BatchResult: ...
    def receipt(self) -> ExecutionReceipt: ...

def default_pipeline_spec(width: int = 256) -> PipelineSpec:
    names = ("lucas", "cassini", "zeckendorf", "prime", "binet", "pisot")
    stages = tuple(StageSpec(n, ("rung",), ("record",), 1, width) for n in names)
    return PipelineSpec(stages=stages, working_width=width)
