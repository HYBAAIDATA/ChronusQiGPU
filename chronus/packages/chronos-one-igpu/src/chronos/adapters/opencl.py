"""Fail-closed OpenCL capability adapter.

This module probes a real pyopencl installation when present. Kernel emission
and dispatch are deliberately not faked: a 256-bit six-stage kernel must be
implemented and verified before this adapter reports a compiled execution.
"""
from __future__ import annotations
import hashlib
from .base import *

class OpenCLAdapter:
    name = "opencl"
    kind = "opencl"
    fail_closed = True
    def __init__(self): self._capability = None; self._last = None
    def probe(self) -> Capability:
        try:
            import pyopencl as cl
            platforms = cl.get_platforms()
            for platform in platforms:
                for device in platform.get_devices(device_type=cl.device_type.GPU):
                    fingerprint = hashlib.sha256(f"{device.vendor}|{device.name}|{device.driver_version}".encode()).hexdigest()
                    self._capability = Capability(device.name, self.kind, device.driver_version, fingerprint, True, True)
                    return self._capability
        except Exception as exc:
            raise BackendAbsent(f"OpenCL GPU unavailable: {exc}") from exc
        raise BackendAbsent("no OpenCL GPU device")
    def compile(self, spec: PipelineSpec) -> CompiledKernel:
        if self._capability is None: self.probe()
        raise CompileError("OpenCL probe succeeded, but the exact 256-bit kernel is not implemented; refusing fallback")
    def dispatch(self, kernel, batch):
        raise DispatchError("OpenCL dispatch unavailable until exact kernel compilation is implemented")
    def receipt(self):
        raise RuntimeError("no OpenCL execution receipt")
