"""Quantum-side iGPU execution for the shared OpenCL context.

:mod:`hyba.quantum.igpu_opencl` owns the process-wide OpenCL context that the
whole iGPU substrate binds to, and the resident buffer sets that hold quantum
state on the device across calls.
"""

from __future__ import annotations

__all__ = ["igpu_opencl"]
