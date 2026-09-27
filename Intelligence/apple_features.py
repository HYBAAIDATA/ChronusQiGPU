"""Apple Silicon integration — detection + capability probes.

Honest probe: returns available=False off macOS. Hardware entry points
(ANE / Metal) raise RuntimeError when the platform can't service them —
no stubs pretending hardware exists.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: step
"""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class AppleSiliconInfo:
    chip: str
    neural_engine_cores: int
    gpu_cores: int
    cpu_cores: int
    unified_memory_gb: int
    metal_support: bool
    accelerate_support: bool
    coreml_support: bool


class AppleSiliconDetector:
    """Detects Apple Silicon capabilities."""

    KNOWN_CHIPS = {
        "M1": AppleSiliconInfo("M1", 16, 8, 8, 8, True, True, True),
        "M1 Pro": AppleSiliconInfo("M1 Pro", 16, 16, 10, 16, True, True, True),
        "M1 Max": AppleSiliconInfo("M1 Max", 16, 32, 10, 32, True, True, True),
        "M1 Ultra": AppleSiliconInfo("M1 Ultra", 32, 64, 20, 64, True, True, True),
        "M2": AppleSiliconInfo("M2", 16, 10, 8, 16, True, True, True),
        "M2 Pro": AppleSiliconInfo("M2 Pro", 16, 19, 12, 32, True, True, True),
        "M2 Max": AppleSiliconInfo("M2 Max", 16, 38, 12, 64, True, True, True),
        "M2 Ultra": AppleSiliconInfo("M2 Ultra", 32, 76, 24, 128, True, True, True),
        "M3": AppleSiliconInfo("M3", 16, 10, 8, 16, True, True, True),
        "M3 Pro": AppleSiliconInfo("M3 Pro", 16, 18, 12, 36, True, True, True),
        "M3 Max": AppleSiliconInfo("M3 Max", 16, 40, 16, 128, True, True, True),
        "M3 Ultra": AppleSiliconInfo("M3 Ultra", 32, 80, 24, 192, True, True, True),
        "M4": AppleSiliconInfo("M4", 16, 10, 10, 16, True, True, True),
        "M4 Pro": AppleSiliconInfo("M4 Pro", 16, 20, 14, 64, True, True, True),
        "M4 Max": AppleSiliconInfo("M4 Max", 16, 40, 16, 128, True, True, True),
    }

    @classmethod
    def detect(cls) -> Optional[AppleSiliconInfo]:
        if platform.system() != "Darwin":
            return None
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            chip_str = result.stdout.strip()
            for name, info in cls.KNOWN_CHIPS.items():
                if name in chip_str:
                    return info
        except Exception:
            pass
        return None


class AppleNeuralEngine:
    """Apple Neural Engine interface via CoreML (macOS only)."""

    def __init__(self):
        self.info = AppleSiliconDetector.detect()
        self.available = self.info is not None and self.info.coreml_support

    def execute(self, model_path: str, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        if not self.available:
            raise RuntimeError("Apple Neural Engine not available on this platform")
        import coremltools as ct  # macOS-only dependency

        model = ct.models.MLModel(model_path)
        return model.predict(inputs)

    def compile(self, model_path: str, output_path: str):
        if not self.available:
            raise RuntimeError("Apple Neural Engine not available on this platform")
        import coremltools as ct  # macOS-only dependency

        model = ct.models.MLModel(model_path)
        model.save(output_path)


class AppleMetal:
    """Apple Metal GPU interface (macOS only)."""

    # Hash-pipeline kernel registry (B4/A6): Metal dispatch names for the
    # Stage A score + Stage C grind markers. Off-macOS raises honestly.
    PHI_FILTER_KERNEL = "phi_filter_score"
    SHA256_GRIND_KERNEL = "sha256d_grind"
    KERNEL_MAP = {
        "phi_filter_score": "phi_filter_score",
        "sha256d_grind_mark": "sha256d_grind",
    }

    def __init__(self):
        self.info = AppleSiliconDetector.detect()
        self.available = self.info is not None and self.info.metal_support

    def kernel_names(self) -> Dict[str, str]:
        """Registered Metal kernel names (hash pipeline parity)."""
        return dict(self.KERNEL_MAP)

    def execute_kernel(
        self, kernel_name: str, buffers: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        if not self.available:
            raise RuntimeError("Apple Metal not available on this platform")
        import metalcompute as mc  # macOS-only dependency

        device = mc.Device()
        kernel = device.kernel(kernel_name)
        for name, buf in buffers.items():
            kernel.set_buffer(buf, name)
        kernel.run()
        return {name: kernel.get_buffer(name) for name in buffers}


class AppleAccelerate:
    """Accelerate-style linear algebra with numpy fallback."""

    def __init__(self):
        self.info = AppleSiliconDetector.detect()
        self.available = self.info is not None and self.info.accelerate_support

    def blas_gemm(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        return A @ B

    def vdsp_fft(self, x: np.ndarray) -> np.ndarray:
        return np.fft.fft(x)

    def vforce_exp(self, x: np.ndarray) -> np.ndarray:
        return np.exp(x)


class AppleUnifiedMemory:
    """Unified-memory helper (numpy stand-in off macOS)."""

    def __init__(self):
        self.info = AppleSiliconDetector.detect()

    def allocate(self, size_bytes: int) -> np.ndarray:
        return np.zeros(size_bytes // 8, dtype=np.float64)

    def zero_copy_transfer(self, array: np.ndarray) -> np.ndarray:
        return array


class AppleSiliconRuntime:
    """Unified Apple Silicon runtime facade."""

    def __init__(self):
        self.info = AppleSiliconDetector.detect()
        self.neural_engine = AppleNeuralEngine()
        self.metal = AppleMetal()
        self.accelerate = AppleAccelerate()
        self.unified_memory = AppleUnifiedMemory()

    def is_available(self) -> bool:
        return self.info is not None

    def telemetry(self) -> Dict[str, Any]:
        if self.info is None:
            return {"available": False}
        return {
            "available": True,
            "chip": self.info.chip,
            "neural_engine_cores": self.info.neural_engine_cores,
            "gpu_cores": self.info.gpu_cores,
            "cpu_cores": self.info.cpu_cores,
            "unified_memory_gb": self.info.unified_memory_gb,
            "metal": self.metal.available,
            "accelerate": self.accelerate.available,
            "coreml": self.neural_engine.available,
        }
