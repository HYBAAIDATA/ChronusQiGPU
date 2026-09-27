"""Acceleration substrate for the iGPU-first mining path.

Submodules:

- :mod:`accel.unified_gpu_detector` — one CUDA/Metal/OpenCL census with
  evidence-based iGPU classification and cross-backend deduplication.
- :mod:`accel.igpu_sha256d_opencl` — pooled-buffer SHA-256d nonce scanner
  whose found-flag is published after the nonce it refers to.
- :mod:`accel.substrate` — tiered hardware initialization that records why
  each tier failed instead of degrading to CPU silently.

The iGPU is the default GPU for this substrate. A discrete GPU is used only
when no integrated device is present, and every device record states the
evidence behind that choice.
"""

from __future__ import annotations

__all__ = ["igpu_sha256d_opencl", "substrate", "unified_gpu_detector"]
