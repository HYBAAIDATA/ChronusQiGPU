"""Compute abstraction exposes concrete, qualified backends without importing MLX at startup."""
from chronus.compute.igpu_dispatcher import ComputeTask, ComputeUnavailable, iGPUDispatcher

__all__ = ["ComputeTask", "ComputeUnavailable", "iGPUDispatcher"]
