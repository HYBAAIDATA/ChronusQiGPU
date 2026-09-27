"""Portable math IR — one spec, per-backend emitters, oracle-checked execution.

Every op in the substrate is described by a :class:`KernelSpec`: its math,
its signature, the capabilities a device must *measure* to run it, and its
precision bound. Emitters lower a spec to OpenCL, Metal, or a CPU callable;
``IRExecutor`` binds a spec to a concrete device only when that device's
measured capability set covers ``required_capabilities``, then verifies the
result against the spec's oracle (sha256d ≤ target rechecked via hashlib —
the sole accept authority).

This package lives in ``hyba/`` because it is composition machinery, not an
algorithm: LUCAS WIRING purity forbids the sibling algorithm modules from
importing it.
"""

from hyba.math_ir.specs import KernelSpec, KERNEL_SPECS, get_spec
from hyba.math_ir.executor import CapabilityMismatch, IRExecutor, OpResult

__all__ = [
    "CapabilityMismatch",
    "IRExecutor",
    "KernelSpec",
    "KERNEL_SPECS",
    "OpResult",
    "get_spec",
]
