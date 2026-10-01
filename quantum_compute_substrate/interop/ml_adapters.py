"""AI/ML adapters (PyTorch, TensorFlow)."""
import importlib
from typing import Any, Optional, Dict
import numpy as np


def _try_import(name: str) -> Optional[Any]:
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


class TorchAdapter:
    """Convert between numpy state vectors and PyTorch tensors."""

    def __init__(self):
        self.torch = _try_import("torch")
        self.available = self.torch is not None

    def to_torch(self, array: np.ndarray):
        if not self.available:
            raise RuntimeError("PyTorch not installed.")
        return self.torch.from_numpy(array)

    def from_torch(self, tensor) -> np.ndarray:
        if not self.available:
            raise RuntimeError("PyTorch not installed.")
        return tensor.detach().cpu().numpy()

    def status(self) -> Dict:
        return {"framework": "pytorch", "available": self.available}


class TensorFlowAdapter:
    """Convert between numpy state vectors and TensorFlow tensors."""

    def __init__(self):
        self.tf = _try_import("tensorflow")
        self.available = self.tf is not None

    def to_tf(self, array: np.ndarray):
        if not self.available:
            raise RuntimeError("TensorFlow not installed.")
        return self.tf.convert_to_tensor(array)

    def from_tf(self, tensor) -> np.ndarray:
        if not self.available:
            raise RuntimeError("TensorFlow not installed.")
        return tensor.numpy()

    def status(self) -> Dict:
        return {"framework": "tensorflow", "available": self.available}
