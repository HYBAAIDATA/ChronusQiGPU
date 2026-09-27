"""Tests for Apple Silicon detection and capability probes."""

import numpy as np

from Intelligence.apple_features import (
    AppleSiliconDetector,
    AppleAccelerate,
    AppleUnifiedMemory,
    AppleSiliconRuntime,
)


def test_detector():
    info = AppleSiliconDetector.detect()
    if info is not None:
        assert info.chip in AppleSiliconDetector.KNOWN_CHIPS


def test_runtime_init():
    rt = AppleSiliconRuntime()
    assert rt.is_available() == (AppleSiliconDetector.detect() is not None)


def test_runtime_telemetry():
    rt = AppleSiliconRuntime()
    tel = rt.telemetry()
    assert "available" in tel


def test_accelerate_fallback():
    acc = AppleAccelerate()
    A = np.random.randn(10, 10)
    B = np.random.randn(10, 10)
    C = acc.blas_gemm(A, B)
    assert np.allclose(C, A @ B)


def test_unified_memory_allocate():
    um = AppleUnifiedMemory()
    arr = um.allocate(1024)
    assert arr.size == 128
