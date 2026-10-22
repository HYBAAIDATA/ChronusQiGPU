"""
Substrate Abstraction Layer for Quantum Operations
=================================================

This module provides a hardware-agnostic backend interface for executing
quantum mathematical operations. The mathematical operations are defined
in math_core.py and can be executed on different backends:
- CPU backend: Pure NumPy implementation
- GPU backend: MLX/Metal acceleration
- Future: Quantum hardware backend (QPU)

Philosophical Foundation:
- Quantum computation is mathematical, not physical
- Substrate is an implementation detail, not fundamental
- Same mathematical operation can execute on any substrate
- Backend selection is orthogonal to mathematical correctness

Architecture:
- Mathematical Layer: Pure math (math_core.py)
- Backend Layer: Execution strategies (this module)
- Hardware Layer: Physical implementation (CPU, GPU, QPU)

Version: 1.0.0
Date: 2026-04-21
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# BACKEND TYPE ENUMERATION
# =============================================================================


class BackendType(Enum):
    """Available backend types for quantum operations."""

    CPU = "cpu"
    GPU = "gpu"
    AUTO = "auto"


# =============================================================================
# BACKEND INTERFACE
# =============================================================================


class QuantumBackend(ABC):
    """
    Abstract interface for quantum operation backends.

    All backends must implement these methods to ensure consistent
    mathematical behavior regardless of substrate.
    """

    @property
    @abstractmethod
    def backend_type(self) -> BackendType:
        """Return the backend type."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is available."""
        ...

    @abstractmethod
    def matrix_multiply(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        """Matrix multiplication C = A @ B."""

    @abstractmethod
    def matrix_exponential(self, H: np.ndarray, t: float = 1.0) -> np.ndarray:
        """Matrix exponential exp(-iHt)."""

    @abstractmethod
    def eigen_decomposition(self, H: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Eigenvalue decomposition: H = VΛV†."""

    @abstractmethod
    def svd(self, A: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Singular value decomposition: A = UΣV†."""

    @abstractmethod
    def elementwise_ops(self, A: np.ndarray, B: np.ndarray, op: str) -> np.ndarray:
        """Element-wise operations."""

    @abstractmethod
    def reduction(self, A: np.ndarray, op: str) -> np.ndarray:
        """Reduction operations (sum, mean, norm, etc.)."""


# =============================================================================
# CPU BACKEND (PURE NUMPY)
# =============================================================================


class CPUBackend(QuantumBackend):
    """
    CPU backend using pure NumPy.

    This is the baseline implementation that works on any system
    with NumPy installed. No hardware acceleration.
    """

    def __init__(self):
        """Initialize CPU backend."""
        self._type = BackendType.CPU
        logger.info("CPU backend initialized (pure NumPy)")

    @property
    def backend_type(self) -> BackendType:
        return self._type

    @property
    def is_available(self) -> bool:
        return True  # CPU backend always available

    def matrix_multiply(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        """Matrix multiplication using NumPy."""
        return A @ B

    def matrix_exponential(self, H: np.ndarray, t: float = 1.0) -> np.ndarray:
        """Matrix exponential using SciPy."""
        from scipy.linalg import expm

        return expm(-1j * H * t)

    def eigen_decomposition(self, H: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Eigenvalue decomposition using NumPy."""
        return np.linalg.eigh(H)

    def svd(self, A: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """SVD using NumPy."""
        return np.linalg.svd(A, full_matrices=False)

    def elementwise_ops(self, A: np.ndarray, B: np.ndarray, op: str) -> np.ndarray:
        """Element-wise operations using NumPy."""
        if op == "add":
            return A + B
        elif op == "multiply":
            return A * B
        elif op == "divide":
            return A / B
        elif op == "power":
            return A**B
        else:
            msg = f"Unknown operation: {op}"
            raise ValueError(msg)

    def reduction(self, A: np.ndarray, op: str) -> np.ndarray:
        """Reduction operations using NumPy."""
        if op == "sum":
            return np.sum(A)
        elif op == "mean":
            return np.mean(A)
        elif op == "norm":
            return np.linalg.norm(A)
        elif op == "max":
            return np.max(A)
        elif op == "min":
            return np.min(A)
        else:
            msg = f"Unknown operation: {op}"
            raise ValueError(msg)


# =============================================================================
# GPU BACKEND (MLX/METAL)
# =============================================================================


class GPUBackend(QuantumBackend):
    """
    GPU backend using MLX/Metal.

    Provides hardware acceleration on Apple Silicon Macs.
    Falls back to CPU if MLX not available.
    """

    def __init__(self):
        """Initialize GPU backend."""
        self._type = BackendType.GPU
        self._available = False
        self._mlx = None

        try:
            import mlx.core as mx

            self._mlx = mx
            self._available = True
            logger.info("GPU backend initialized (MLX/Metal)")
        except ImportError:
            logger.warning("MLX not available, GPU backend unavailable")

    @property
    def backend_type(self) -> BackendType:
        return self._type

    @property
    def is_available(self) -> bool:
        return self._available

    def matrix_multiply(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        """Matrix multiplication using MLX."""
        if not self._available:
            return CPUBackend().matrix_multiply(A, B)

        A_gpu = self._mlx.array(A)
        B_gpu = self._mlx.array(B)
        C_gpu = self._mlx.matmul(A_gpu, B_gpu)
        return np.array(C_gpu)

    def matrix_exponential(self, H: np.ndarray, t: float = 1.0) -> np.ndarray:
        """Matrix exponential - falls back to CPU for now."""
        # MLX doesn't have matrix exponential yet
        return CPUBackend().matrix_exponential(H, t)

    def eigen_decomposition(self, H: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Eigenvalue decomposition using MLX."""
        if not self._available:
            return CPUBackend().eigen_decomposition(H)

        H_gpu = self._mlx.array(H)
        eigvals_gpu, eigvecs_gpu = self._mlx.linalg.eigh(H_gpu, stream=self._mlx.cpu)
        self._mlx.eval(eigvals_gpu, eigvecs_gpu)
        return np.array(eigvals_gpu), np.array(eigvecs_gpu)

    def svd(self, A: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """SVD using MLX."""
        if not self._available:
            return CPUBackend().svd(A)

        A_gpu = self._mlx.array(A)
        U_gpu, S_gpu, V_gpu = self._mlx.linalg.svd(A_gpu, full_matrices=False)
        self._mlx.eval(U_gpu, S_gpu, V_gpu)
        return np.array(U_gpu), np.array(S_gpu), np.array(V_gpu)

    def elementwise_ops(self, A: np.ndarray, B: np.ndarray, op: str) -> np.ndarray:
        """Element-wise operations using MLX."""
        if not self._available:
            return CPUBackend().elementwise_ops(A, B, op)

        A_gpu = self._mlx.array(A)
        B_gpu = self._mlx.array(B)

        if op == "add":
            result_gpu = A_gpu + B_gpu
        elif op == "multiply":
            result_gpu = A_gpu * B_gpu
        elif op == "divide":
            result_gpu = A_gpu / B_gpu
        elif op == "power":
            result_gpu = A_gpu**B_gpu
        else:
            msg = f"Unknown operation: {op}"
            raise ValueError(msg)

        return np.array(result_gpu)

    def reduction(self, A: np.ndarray, op: str) -> np.ndarray:
        """Reduction operations using MLX."""
        if not self._available:
            return CPUBackend().reduction(A, op)

        A_gpu = self._mlx.array(A)

        if op == "sum":
            result_gpu = self._mlx.sum(A_gpu)
        elif op == "mean":
            result_gpu = self._mlx.mean(A_gpu)
        elif op == "norm":
            result_gpu = self._mlx.linalg.norm(A_gpu)
        elif op == "max":
            result_gpu = self._mlx.max(A_gpu)
        elif op == "min":
            result_gpu = self._mlx.min(A_gpu)
        else:
            msg = f"Unknown operation: {op}"
            raise ValueError(msg)

        self._mlx.eval(result_gpu)
        return np.array(result_gpu)


# =============================================================================
# AUTO BACKEND (AUTOMATIC SELECTION)
# =============================================================================


class AutoBackend(QuantumBackend):
    """
    Auto backend that selects best available backend.

    Priority: GPU > CPU
    """

    def __init__(self):
        """Initialize auto backend."""
        self._type = BackendType.AUTO
        self._gpu = GPUBackend()
        self._cpu = CPUBackend()
        self._preferred = self._gpu if self._gpu.is_available else self._cpu

        if self._preferred.backend_type == BackendType.GPU:
            logger.info("Auto backend selected: GPU (MLX/Metal)")
        else:
            logger.info("Auto backend selected: CPU (NumPy)")

    @property
    def backend_type(self) -> BackendType:
        return self._type

    @property
    def is_available(self) -> bool:
        return True  # Auto backend always has a fallback

    @property
    def active_backend(self) -> QuantumBackend:
        """Return the currently active backend."""
        return self._preferred

    def matrix_multiply(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        """Matrix multiplication using active backend."""
        return self._preferred.matrix_multiply(A, B)

    def matrix_exponential(self, H: np.ndarray, t: float = 1.0) -> np.ndarray:
        """Matrix exponential using active backend."""
        return self._preferred.matrix_exponential(H, t)

    def eigen_decomposition(self, H: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Eigenvalue decomposition using active backend."""
        return self._preferred.eigen_decomposition(H)

    def svd(self, A: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """SVD using active backend."""
        return self._preferred.svd(A)

    def elementwise_ops(self, A: np.ndarray, B: np.ndarray, op: str) -> np.ndarray:
        """Element-wise operations using active backend."""
        return self._preferred.elementwise_ops(A, B, op)

    def reduction(self, A: np.ndarray, op: str) -> np.ndarray:
        """Reduction operations using active backend."""
        return self._preferred.reduction(A, op)


# =============================================================================
# BACKEND FACTORY
# =============================================================================


@dataclass
class BackendConfig:
    """Configuration for backend selection."""

    backend_type: BackendType = BackendType.AUTO
    fallback_to_cpu: bool = True
    verbose: bool = False


def get_backend(config: BackendConfig | None = None) -> QuantumBackend:
    """
    Get quantum backend based on configuration.

    Args:
        config: Backend configuration (uses defaults if None)

    Returns:
        Quantum backend instance
    """
    if config is None:
        config = BackendConfig()

    if config.backend_type == BackendType.CPU:
        return CPUBackend()
    elif config.backend_type == BackendType.GPU:
        gpu = GPUBackend()
        if gpu.is_available:
            return gpu
        elif config.fallback_to_cpu:
            logger.warning("GPU backend unavailable, falling back to CPU")
            return CPUBackend()
        else:
            msg = "GPU backend requested but unavailable"
            raise RuntimeError(msg)
    elif config.backend_type == BackendType.AUTO:
        return AutoBackend()
    else:
        msg = f"Unknown backend type: {config.backend_type}"
        raise ValueError(msg)


# =============================================================================
# BACKEND-AGNOSTIC OPERATIONS
# =============================================================================


class BackendOperations:
    """
    Backend-agnostic quantum operations.

    Uses the configured backend to execute mathematical operations.
    Ensures consistent results regardless of substrate.
    """

    def __init__(self, backend: QuantumBackend | None = None):
        """
        Initialize with specified backend.

        Args:
            backend: Quantum backend (uses auto if None)
        """
        self.backend = backend if backend is not None else get_backend()

    def evolve_state(
        self, state: np.ndarray, hamiltonian: np.ndarray, time: float = 1.0
    ) -> np.ndarray:
        """
        Evolve quantum state using backend.

        |ψ(t)⟩ = exp(-iHt) |ψ(0)⟩

        Args:
            state: Initial state vector
            hamiltonian: Hamiltonian matrix
            time: Evolution time

        Returns:
            Evolved state vector
        """
        # Compute evolution operator
        U = self.backend.matrix_exponential(hamiltonian, time)

        # Apply to state
        evolved = self.backend.matrix_multiply(U, state)

        # Normalize
        norm = self.backend.reduction(evolved, "norm")
        if norm > 0:
            evolved = evolved / norm

        return evolved

    def spectral_walk(
        self, initial_state: np.ndarray, hamiltonian: np.ndarray, time: float
    ) -> np.ndarray:
        """
        Spectral quantum walk using eigen decomposition.

        Uses precomputed eigen decomposition for efficiency.

        Args:
            initial_state: Initial state vector
            hamiltonian: Walk Hamiltonian
            time: Walk time

        Returns:
            Evolved state vector
        """
        # Compute eigen decomposition
        eigvals, eigvecs = self.backend.eigen_decomposition(hamiltonian)

        # Express initial state in eigenbasis
        coeffs = self.backend.matrix_multiply(eigvecs.conj().T, initial_state)

        # Evolve each eigencomponent
        evolved_coeffs = coeffs * np.exp(-1j * eigvals * time)

        # Transform back to computational basis
        return self.backend.matrix_multiply(eigvecs, evolved_coeffs)


# =============================================================================
# GLOBAL BACKEND INSTANCE
# =============================================================================


_global_backend: QuantumBackend | None = None
_global_ops: BackendOperations | None = None


def set_global_backend(backend: QuantumBackend) -> None:
    """Set global backend for all quantum operations."""
    global _global_backend, _global_ops
    _global_backend = backend
    _global_ops = BackendOperations(backend)
    logger.info(f"Global backend set to {backend.backend_type.value}")


def get_global_backend() -> QuantumBackend:
    """Get global backend (creates default if none)."""
    global _global_backend
    if _global_backend is None:
        _global_backend = get_backend()
    return _global_backend


def get_global_ops() -> BackendOperations:
    """Get global backend operations (creates default if none)."""
    global _global_ops
    if _global_ops is None:
        _global_ops = BackendOperations(get_global_backend())
    return _global_ops


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Backend types
    "BackendType",
    # Backend interface
    "QuantumBackend",
    # Concrete backends
    "CPUBackend",
    "GPUBackend",
    "AutoBackend",
    # Configuration
    "BackendConfig",
    "get_backend",
    # Operations
    "BackendOperations",
    # Global management
    "set_global_backend",
    "get_global_backend",
    "get_global_ops",
]
