"""Torch reversible φ-layer — fold/unfold as nn.Module.

If torch is absent, factory returns None (honest).
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from ..ai_layers import PhiFoldLayer


def available() -> bool:
    try:
        import torch  # noqa: F401

        return True
    except Exception:
        return False


def make_module(kind: str = "unitary", depth: int = 3, threshold: float = 0.0):
    if not available():
        return None
    import torch
    import torch.nn as nn

    class PhiFoldTorch(nn.Module):
        def __init__(self, kind: str = "unitary", depth: int = 3, threshold: float = 0.0):
            super().__init__()
            self.kind = kind
            self.depth = depth
            self.threshold = threshold
            self._state = None
            self._layer = PhiFoldLayer(kind=kind, depth=depth, threshold=threshold)

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            arr = x.detach().cpu().numpy()
            z, st = self._layer.forward(arr)
            self._state = st
            return torch.as_tensor(z, dtype=x.dtype, device=x.device)

        def inverse(self, z: "torch.Tensor") -> "torch.Tensor":
            assert self._state is not None, "call forward first"
            y = self._layer.inverse(z.detach().cpu().numpy(), self._state)
            return torch.as_tensor(y, dtype=z.dtype, device=z.device)

        def roundtrip_error(self, x: "torch.Tensor") -> float:
            z = self.forward(x)
            y = self.inverse(z)
            return float(torch.max(torch.abs(x - y)).item())

    return PhiFoldTorch(kind=kind, depth=depth, threshold=threshold)


def numpy_roundtrip(x: np.ndarray, kind: str = "unitary") -> float:
    """Always-available path when torch missing."""
    layer = PhiFoldLayer(kind=kind)
    z, st = layer.forward(x)
    y = layer.inverse(z, st)
    return float(np.max(np.abs(np.asarray(x, dtype=np.float64) - np.asarray(y, dtype=np.float64).reshape(x.shape))))
