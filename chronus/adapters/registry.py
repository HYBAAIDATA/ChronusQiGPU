from __future__ import annotations
from .base import Adapter, BackendAbsent

class AdapterRegistry:
    def __init__(self): self.adapters = {}; self.order = []
    def register(self, adapter: Adapter):
        self.adapters[adapter.name] = adapter
        if adapter.name not in self.order: self.order.append(adapter.name)
    def select(self, policy: str = "prefer_gpu") -> Adapter:
        if policy == "cpu_only":
            for adapter in self.adapters.values():
                if adapter.kind == "cpu": adapter.probe(); return adapter
            raise BackendAbsent("no CPU adapter registered")
        if policy in ("prefer_gpu", "prefer_asic"):
            kinds = {"opencl", "cuda", "rocm", "metal"} if policy == "prefer_gpu" else {"asic"}
            for name in self.order:
                adapter = self.adapters[name]
                if adapter.kind in kinds:
                    try: adapter.probe(); return adapter
                    except Exception: continue
            raise BackendAbsent(f"no adapter available for policy {policy}")
        raise ValueError(f"unknown adapter policy: {policy}")
