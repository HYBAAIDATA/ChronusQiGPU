"""Native kernel runtime for the iGPU substrate.

:mod:`hyba.native_kernels.igpu_runtime` holds the allocation and timing
helpers used by the OpenCL paths. It reports where memory actually lives and
how long a callable actually took, so neither is inferable only from a name.
"""

from __future__ import annotations

__all__ = ["igpu_runtime"]
