from __future__ import annotations
import hashlib, platform, time
from datetime import datetime, timezone
from typing import Sequence
from .base import *
from ..lucas_datapath import DatapathConfig, SpatialLucasPipeline

class CpuAdapter:
    name = "cpu-exact-reference"
    kind = "cpu"
    fail_closed = True
    def __init__(self, config: DatapathConfig | None = None):
        self.config = config or DatapathConfig()
        self._last: ExecutionReceipt | None = None
        self._cap = Capability(self.name, self.kind, platform.python_version(), hashlib.sha256(platform.platform().encode()).hexdigest(), True, False)
    def probe(self) -> Capability: return self._cap
    def compile(self, spec: PipelineSpec) -> CompiledKernel:
        if spec.working_width != self.config.working_width: raise CompileError("CPU config/spec width mismatch")
        return CompiledKernel(self.name, spec.digest(), spec)
    def dispatch(self, kernel: CompiledKernel, batch: Sequence[int]) -> BatchResult:
        start = time.perf_counter()
        pipeline = SpatialLucasPipeline(self.config)
        records = tuple(pipeline.process_batch(batch))
        elapsed = time.perf_counter() - start
        result = BatchResult(records, self.name, kernel.kernel_digest, elapsed, True)
        self._last = ExecutionReceipt(self.name, self.kind, self._cap.device_id, kernel.kernel_digest, kernel.pipeline_spec.digest(), None, len(batch)/elapsed if elapsed else 0.0, None, True, datetime.now(timezone.utc).isoformat(), None)
        return result
    def receipt(self) -> ExecutionReceipt:
        if self._last is None: raise RuntimeError("no dispatch has been measured")
        return self._last
