"""iGPU: the Chronus execution-lane runtime.

Groups the execution lanes that exist in this repository: the CPU reference
path (chronus.execution.reference), the opt-in OpenCL adapters and their
packaged kernels (chronus.backends.opencl_pv, chronus.execution.opencl_backend,
chronus.kernels), the native C++ fold library (cpp/, built separately) and the
Zeckendorf hardware model (chronus.hw). The tensor representation used by the
Chronus service is exported as chronus.igpu.tensor. It ships inside the
Chronus distribution and is not published as a separate package.
"""

import importlib
from importlib import resources

__all__ = ["kernel_source", "tensor"]


def kernel_source(name: str) -> str:
    """Return the source text of a packaged OpenCL kernel, for example "pv_lattice.cl"."""
    if not name.endswith(".cl") or "/" in name or "\\" in name:
        raise ValueError("kernel name must be a bare *.cl file name")
    return resources.files("chronus.kernels").joinpath(name).read_text(encoding="utf-8")


def __getattr__(name):
    if name == "tensor":
        return importlib.import_module("chronus.igpu.tensor")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
