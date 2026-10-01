"""GPU backend compatibility entry points.

Imports are deliberately lazy so importing :mod:`gpu.backends` never probes
hardware or requires an optional OpenCL runtime.
"""

__all__ = ["asic", "chronus"]
