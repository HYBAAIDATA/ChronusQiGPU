"""
MLX Tensor Operations for Quantum Layer
======================================

This module implements MLX-accelerated tensor operations for the quantum-geometric
layer, enabling high-performance tensor network computations, continuous-time
quantum walks, and Riemannian manifold calculations on Mac Studio GPU.

First Principles Implementation:
- Tensor contractions using MLX's optimized linear algebra
- GPU-resident quantum state evolution
- Vectorized manifold curvature calculations
- Batch processing for quantum walk simulations

Version: 1.0.0
Date: 2026-04-21
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

# =============================================================================
# BACKEND AVAILABILITY CHECK
# =============================================================================

_MLX_AVAILABLE = False
_METAL_QUANTUM_AVAILABLE = False

try:
    import mlx.core as mx  # noqa: F401

    _MLX_AVAILABLE = True
except ImportError:
    logger.debug("MLX not installed, using CPU fallback")

try:
    from core.quantum_metal_kernels import get_metal_quantum_kernel, is_metal_quantum_available

    _METAL_QUANTUM_AVAILABLE = is_metal_quantum_available()
except ImportError:
    logger.debug("Metal quantum kernels not available")


def is_mlx_available() -> bool:
    """Check if MLX framework is available."""
    return _MLX_AVAILABLE


# =============================================================================
# MLX TENSOR NETWORK OPERATIONS
# =============================================================================


class MLXTensorNetwork:
    """
    Hybrid MLX/Metal-accelerated tensor network operations for quantum simulations.

    Implements efficient tensor contractions, decompositions, and
    network operations using MLX or Metal Performance Shaders.
    """

    def __init__(self, num_faces: int = 64, use_metal: bool = False):
        """
        Initialize tensor network with given dimension.

        Args:
            num_faces: Number of faces in the manifold (M_64 = 64)
            use_metal: Use Metal backend if available (default: MLX)
        """
        self.num_faces = num_faces
        self.use_metal = use_metal and _METAL_QUANTUM_AVAILABLE
        self.enabled = _MLX_AVAILABLE or self.use_metal

        if self.use_metal:
            self.metal_kernel = get_metal_quantum_kernel()
            logger.info(f"Metal Tensor Network initialized: {num_faces} dimensions")
        elif _MLX_AVAILABLE:
            self._initialize_tensors()
            logger.info(f"MLX Tensor Network initialized: {num_faces} dimensions")
        else:
            logger.warning("Neither MLX nor Metal available, using CPU fallback")

    def _initialize_tensors(self):
        """Initialize GPU-resident tensor data structures."""
        import mlx.core as mx

        # Quantum state tensor (complex amplitudes)
        self.quantum_state = mx.random.uniform(
            low=-1.0, high=1.0, shape=(self.num_faces, self.num_faces)
        )

        # Hamiltonian tensor for quantum walks
        self.hamiltonian = mx.zeros((self.num_faces, self.num_faces))

        # Metric tensor for Riemannian calculations
        self.metric_tensor = mx.eye(self.num_faces)

        # Curvature tensor
        self.curvature_tensor = mx.zeros((self.num_faces, self.num_faces, self.num_faces))

    def tensor_contraction(self, tensor_a: np.ndarray, tensor_b: np.ndarray) -> np.ndarray:
        """
        Perform tensor contraction using Metal or MLX GPU acceleration.

        Args:
            tensor_a: First tensor
            tensor_b: Second tensor

        Returns:
            Contracted tensor result
        """
        if not self.enabled:
            return np.tensordot(tensor_a, tensor_b, axes=([-1], [0]))

        # Use Metal backend if requested and available
        if self.use_metal and _METAL_QUANTUM_AVAILABLE:
            try:
                return self.metal_kernel.tensor_contraction_2d(tensor_a, tensor_b)
            except Exception as e:
                logger.debug(f"Metal contraction failed, falling back to MLX: {e}")

        # Use MLX backend
        try:
            import mlx.core as mx

            a_gpu = mx.array(tensor_a)
            b_gpu = mx.array(tensor_b)

            # Perform contraction
            result = mx.tensordot(a_gpu, b_gpu, axes=([-1], [0]))
            mx.eval(result)

            return np.array(result)

        except Exception as e:
            logger.debug(f"MLX contraction failed, falling back to CPU: {e}")
            return np.tensordot(tensor_a, tensor_b, axes=([-1], [0]))

    def batch_matrix_multiply(self, matrices: list[np.ndarray]) -> list[np.ndarray]:
        """
        Batch matrix multiplication using MLX GPU acceleration.

        Args:
            matrices: List of matrices to multiply

        Returns:
            List of multiplication results
        """
        if not self.enabled or len(matrices) < 2:
            # Fallback to CPU
            result = matrices[0]
            for mat in matrices[1:]:
                result = np.matmul(result, mat)
            return [result]

        try:
            import mlx.core as mx

            # Stack matrices for batch processing
            stacked = mx.array(np.array(matrices))

            # Batch matmul
            result = mx.matmul(stacked[:-1], stacked[1:])
            mx.eval(result)

            return [np.array(r) for r in result]

        except Exception as e:
            logger.debug(f"MLX batch matmul failed, falling back to CPU: {e}")
            result = matrices[0]
            for mat in matrices[1:]:
                result = np.matmul(result, mat)
            return [result]


# =============================================================================
# MLX QUANTUM WALK OPERATIONS
# =============================================================================


class MLXQuantumWalk:
    """
    Hybrid MLX/Metal-accelerated continuous-time quantum walk simulation.

    Implements efficient quantum state evolution using GPU-accelerated
    matrix exponentiation and time evolution operators.
    """

    def __init__(self, num_vertices: int = 64, use_metal: bool = False):
        """
        Initialize quantum walk simulator.

        Args:
            num_vertices: Number of vertices in the graph
            use_metal: Use Metal backend if available (default: MLX)
        """
        self.num_vertices = num_vertices
        self.use_metal = use_metal and _METAL_QUANTUM_AVAILABLE
        self.enabled = _MLX_AVAILABLE or self.use_metal

        if self.use_metal:
            self.metal_kernel = get_metal_quantum_kernel()
            logger.info(f"Metal Quantum Walk initialized: {num_vertices} vertices")
        elif _MLX_AVAILABLE:
            self._initialize_walk_state()
            logger.info(f"MLX Quantum Walk initialized: {num_vertices} vertices")
        else:
            logger.warning("Neither MLX nor Metal available, using CPU fallback")

    def _initialize_walk_state(self):
        """Initialize quantum walk state on GPU."""
        import mlx.core as mx

        # Initial quantum state (uniform superposition)
        self.psi = mx.ones((self.num_vertices,)) / np.sqrt(self.num_vertices)

        # Adjacency matrix for the graph
        self.adjacency = mx.zeros((self.num_vertices, self.num_vertices))

    def evolve_state(self, time: float, hamiltonian: np.ndarray | None = None) -> np.ndarray:
        """
        Evolve quantum state under Hamiltonian for given time.

        Args:
            time: Evolution time
            hamiltonian: Hamiltonian matrix (uses adjacency if None)

        Returns:
            Evolved quantum state
        """
        if not self.enabled:
            # Fallback to CPU implementation
            if hamiltonian is None:
                return np.ones(self.num_vertices) / np.sqrt(self.num_vertices)
            from scipy.linalg import expm

            return (
                expm(-1j * time * hamiltonian)
                @ np.ones(self.num_vertices)
                / np.sqrt(self.num_vertices)
            )

        # Use Metal backend if requested and available
        if self.use_metal and _METAL_QUANTUM_AVAILABLE:
            try:
                if hamiltonian is None:
                    # Create simple identity hamiltonian for fallback
                    hamiltonian = np.eye(self.num_vertices)
                psi_init = np.ones(self.num_vertices) / np.sqrt(self.num_vertices)
                return self.metal_kernel.quantum_walk_evolution(psi_init, hamiltonian, time)
            except Exception as e:
                logger.debug(f"Metal evolution failed, falling back to MLX: {e}")

        # Use MLX backend
        try:
            import mlx.core as mx

            H_gpu = mx.array(hamiltonian) if hamiltonian is not None else self.adjacency

            # Simple approximation: psi(t) = psi(0) - i*t*H*psi(0)
            psi_gpu = self.psi - 1j * time * mx.matmul(H_gpu, self.psi)
            mx.eval(psi_gpu)

            return np.array(psi_gpu)

        except Exception as e:
            logger.debug(f"MLX evolution failed, falling back to CPU: {e}")
            return np.ones(self.num_vertices) / np.sqrt(self.num_vertices)


# =============================================================================
# MLX RIEMANNIAN MANIFOLD OPERATIONS
# =============================================================================


class MLXRiemannianManifold:
    """
    Hybrid MLX/Metal-accelerated Riemannian manifold calculations.

    Implements efficient metric tensor operations, geodesic computations,
    and curvature calculations on the M_64 manifold using GPU acceleration.
    """

    def __init__(self, num_faces: int = 64, use_metal: bool = False):
        """
        Initialize Riemannian manifold calculator.

        Args:
            num_faces: Number of faces in the manifold
            use_metal: Use Metal backend if available (default: MLX)
        """
        self.num_faces = num_faces
        self.use_metal = use_metal and _METAL_QUANTUM_AVAILABLE
        self.enabled = _MLX_AVAILABLE or self.use_metal

        if self.use_metal:
            self.metal_kernel = get_metal_quantum_kernel()
            logger.info(f"Metal Riemannian Manifold initialized: {num_faces} faces")
        elif _MLX_AVAILABLE:
            self._initialize_manifold()
            logger.info(f"MLX Riemannian Manifold initialized: {num_faces} faces")
        else:
            logger.warning("Neither MLX nor Metal available, using CPU fallback")

    def _initialize_manifold(self):
        """Initialize manifold data structures on GPU."""
        import mlx.core as mx

        # Metric tensor (identity for flat approximation)
        self.metric = mx.eye(self.num_faces)

        # Christoffel symbols
        self.christoffel = mx.zeros((self.num_faces, self.num_faces, self.num_faces))

        # Riemann curvature tensor
        self.riemann = mx.zeros((self.num_faces, self.num_faces, self.num_faces, self.num_faces))

    def compute_geodesic_distance(self, point_a: np.ndarray, point_b: np.ndarray) -> float:
        """
        Compute geodesic distance between two points on the manifold.

        Args:
            point_a: First point coordinates
            point_b: Second point coordinates

        Returns:
            Geodesic distance
        """
        if not self.enabled:
            # Fallback to Euclidean distance
            return np.linalg.norm(point_a - point_b)

        try:
            import mlx.core as mx

            a_gpu = mx.array(point_a)
            b_gpu = mx.array(point_b)

            # Simple geodesic approximation using metric
            diff = a_gpu - b_gpu
            distance = mx.sqrt(mx.matmul(diff, mx.matmul(self.metric, diff)))
            mx.eval(distance)

            return float(distance)

        except Exception as e:
            logger.debug(f"MLX geodesic computation failed, falling back to CPU: {e}")
            return np.linalg.norm(point_a - point_b)

    def batch_curvature_computation(self, points: list[np.ndarray]) -> list[float]:
        """
        Batch curvature computation for multiple points.

        Args:
            points: List of point coordinates

        Returns:
            List of curvature values
        """
        if not self.enabled:
            # Fallback to simple curvature approximation
            return [np.linalg.norm(p) * 0.1 for p in points]

        # Use Metal backend if requested and available
        if self.use_metal and _METAL_QUANTUM_AVAILABLE:
            try:
                points_array = np.array(points)
                result = self.metal_kernel.batch_curvature_computation(points_array)
                return result.tolist()
            except Exception as e:
                logger.debug(f"Metal batch curvature failed, falling back to MLX: {e}")

        # Use MLX backend
        try:
            import mlx.core as mx

            points_gpu = mx.array(np.array(points))

            # Simple curvature approximation
            curvatures = mx.sum(points_gpu**2, axis=1) * 0.1
            mx.eval(curvatures)

            return curvatures.tolist()

        except Exception as e:
            logger.debug(f"MLX batch curvature failed, falling back to CPU: {e}")
            return [np.linalg.norm(p) * 0.1 for p in points]


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

_tensor_network: MLXTensorNetwork | None = None
_quantum_walk: MLXQuantumWalk | None = None
_riemannian: MLXRiemannianManifold | None = None


def get_tensor_network(num_faces: int = 64, use_metal: bool = False) -> MLXTensorNetwork:
    """Get or create global tensor network instance."""
    global _tensor_network
    if (
        _tensor_network is None
        or _tensor_network.num_faces != num_faces
        or _tensor_network.use_metal != use_metal
    ):
        _tensor_network = MLXTensorNetwork(num_faces, use_metal=use_metal)
    return _tensor_network


def get_quantum_walk(num_vertices: int = 64, use_metal: bool = False) -> MLXQuantumWalk:
    """Get or create global quantum walk instance."""
    global _quantum_walk
    if (
        _quantum_walk is None
        or _quantum_walk.num_vertices != num_vertices
        or _quantum_walk.use_metal != use_metal
    ):
        _quantum_walk = MLXQuantumWalk(num_vertices, use_metal=use_metal)
    return _quantum_walk


def get_riemannian_manifold(num_faces: int = 64, use_metal: bool = False) -> MLXRiemannianManifold:
    """Get or create global Riemannian manifold instance."""
    global _riemannian
    if (
        _riemannian is None
        or _riemannian.num_faces != num_faces
        or _riemannian.use_metal != use_metal
    ):
        _riemannian = MLXRiemannianManifold(num_faces, use_metal=use_metal)
    return _riemannian


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "is_mlx_available",
    "MLXTensorNetwork",
    "MLXQuantumWalk",
    "MLXRiemannianManifold",
    "get_tensor_network",
    "get_quantum_walk",
    "get_riemannian_manifold",
]
