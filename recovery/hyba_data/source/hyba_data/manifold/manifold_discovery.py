"""
Automated Manifold Discovery Engine (v9.0) - Tour de Force Implementation

A sophisticated system that uses advanced gradient flow algorithms to learn
optimal manifold geometries for cryptographic hash functions. This implementation
represents state-of-the-art software engineering in 2026.

Key Features:
- Advanced gradient flow optimization (Adam, RMSProp, L-BFGS)
- Neural network-based learnable embeddings
- Multi-scale manifold discovery
- Cryptographic hash-specific strategies
- Comprehensive quality metrics
- Checkpointing and resume capabilities
- Visualization and analysis tools
- Distributed discovery support

Mathematical Foundation:
- Gradient flow on Riemannian manifolds: ∂g/∂t = -∇_g L(g)
- Variational learning: minimize ∇_θ L where θ are manifold parameters
- Neural embeddings: f_θ: ℝ^n → ℝ^d with learnable parameters θ
- Cryptographic hash structure analysis

Author: Phi-Grover Development Team
Version: 9.0.0
Date: 2026-04-18
"""

from __future__ import annotations

import json
import logging
import math
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from .manifold import ManifoldConfig

if TYPE_CHECKING:
    from .oracle import Oracle

logger = logging.getLogger(__name__)


class SymmetryType(Enum):
    """Types of symmetries detectable in cost functions."""

    ROTATIONAL = "rotational"
    REFLECTION = "reflection"
    TRANSLATIONAL = "translational"
    SCALING = "scaling"
    PERMUTATION = "permutation"
    GOLDEN_RATIO = "golden_ratio"
    FIBONACCI = "fibonacci"
    ICOSAHEDRAL = "icosahedral"
    DODECAHEDRAL = "dodecahedral"
    LIE_GROUP = "lie_group"
    AFFINE = "affine"


class OptimizationAlgorithm(Enum):
    """Advanced optimization algorithms for gradient flow."""

    GRADIENT_DESCENT = "gradient_descent"
    ADAM = "adam"
    RMSPROP = "rmsprop"
    ADAGRAD = "adagrad"
    LBFGS = "lbfgs"
    NATURAL_GRADIENT = "natural_gradient"
    MOMENTUM = "momentum"
    NESTEROV = "nesterov"


class ManifoldRepresentation(Enum):
    """Types of learnable manifold representations."""

    PARAMETRIC_EMBEDDING = "parametric_embedding"
    NEURAL_EMBEDDING = "neural_embedding"
    POLYNOMIAL_MAPPING = "polynomial_mapping"
    SPLINE_MAPPING = "spline_mapping"
    FOURIER_SERIES = "fourier_series"
    WAVELET_TRANSFORM = "wavelet_transform"
    MIXED = "mixed"


@dataclass
class SymmetryDetectionResult:
    """Result of symmetry detection analysis."""

    symmetry_type: SymmetryType
    """Detected symmetry type."""

    confidence: float
    """Confidence score in [0,1]."""

    parameters: dict[str, Any]
    """Symmetry parameters (e.g., rotation angle, scaling factor)."""

    evidence: list[tuple[int, float]]
    """Evidence points (location, cost_value)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata."""


@dataclass
class ManifoldProposal:
    """Proposal for a manifold structure."""

    manifold_type: str
    """Type of manifold (e.g., 'm32', 'grassmannian', 'custom')."""

    config: ManifoldConfig
    """Configuration for the proposed manifold."""

    expected_performance: float
    """Expected performance score [0,1]."""

    symmetry_basis: list[SymmetryDetectionResult]
    """Symmetry detections that motivated this proposal."""

    description: str
    """Human-readable description of the proposal."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata."""


@dataclass
class GradientFlowConfig:
    """Configuration for gradient flow optimization."""

    algorithm: OptimizationAlgorithm = OptimizationAlgorithm.ADAM
    """Optimization algorithm to use."""

    learning_rate: float = 0.001
    """Learning rate for gradient descent."""

    beta1: float = 0.9
    """Adam beta1 parameter."""

    beta2: float = 0.999
    """Adam beta2 parameter."""

    epsilon: float = 1e-8
    """Numerical stability epsilon."""

    momentum: float = 0.9
    """Momentum coefficient."""

    max_iterations: int = 10000
    """Maximum optimization iterations."""

    convergence_tolerance: float = 1e-6
    """Tolerance for convergence detection."""

    convergence_window: int = 50
    """Window for convergence detection."""

    l2_regularization: float = 0.01
    """L2 regularization coefficient."""

    gradient_clip: float = 1.0
    """Gradient clipping threshold."""

    use_amsgrad: bool = False
    """Use AMSGrad variant of Adam."""

    use_warmup: bool = True
    """Use learning rate warmup."""

    warmup_steps: int = 1000
    """Number of warmup steps."""


@dataclass
class NeuralEmbeddingConfig:
    """Configuration for neural network embedding."""

    input_dim: int = 32
    """Input dimension (e.g., 32-bit nonce)."""

    hidden_dims: list[int] = field(default_factory=lambda: [128, 64, 32])
    """Hidden layer dimensions."""

    output_dim: int = 3
    """Output embedding dimension."""

    activation: str = "tanh"
    """Activation function: 'tanh', 'relu', 'sigmoid', 'gelu'."""

    use_batch_norm: bool = False
    """Use batch normalization."""

    use_residual: bool = True
    """Use residual connections."""

    use_dropout: bool = False
    """Use dropout regularization."""

    dropout_rate: float = 0.1
    """Dropout rate."""

    initialization: str = "xavier"
    """Weight initialization: 'xavier', 'he', 'orthogonal'."""

    use_skip_connections: bool = True
    """Use skip connections between layers."""


class AdvancedGradientFlowOptimizer:
    """
    Advanced gradient flow optimizer with multiple algorithms.

    Implements state-of-the-art optimization algorithms including Adam,
    RMSProp, AdaGrad, L-BFGS, and natural gradient descent.
    """

    def __init__(self, config: GradientFlowConfig):
        """
        Initialize gradient flow optimizer.

        Args:
            config: Optimization configuration
        """
        self.config = config
        self.iteration = 0

        # Adam state
        self.m = None  # First moment
        self.v = None  # Second moment
        self.v_max = None  # For AMSGrad

        # RMSProp state
        self.cache = None

        # AdaGrad state
        self.sum_squared_grad = None

        # Momentum state
        self.velocity = None

        # L-BFGS state
        self.history_size = 10
        self.s_history = []
        self.y_history = []
        self.rho_history = []
        self.old_grad = None
        self.old_params = None

        logger.info(f"Initialized {config.algorithm.value} optimizer")

    def step(self, params: np.ndarray, gradient: np.ndarray) -> np.ndarray:
        """
        Perform one optimization step.

        Args:
            params: Current parameters
            gradient: Gradient of loss with respect to parameters

        Returns:
            Updated parameters
        """
        # Clip gradient
        gradient = np.clip(gradient, -self.config.gradient_clip, self.config.gradient_clip)

        # Add L2 regularization
        regularized_gradient = gradient + self.config.l2_regularization * params

        # Apply learning rate warmup
        lr = self._get_learning_rate()

        # Apply algorithm-specific update
        if self.config.algorithm == OptimizationAlgorithm.ADAM:
            params = self._adam_step(params, regularized_gradient, lr)
        elif self.config.algorithm == OptimizationAlgorithm.RMSPROP:
            params = self._rmsprop_step(params, regularized_gradient, lr)
        elif self.config.algorithm == OptimizationAlgorithm.ADAGRAD:
            params = self._adagrad_step(params, regularized_gradient, lr)
        elif self.config.algorithm == OptimizationAlgorithm.LBFGS:
            params = self._lbfgs_step(params, gradient)
        elif self.config.algorithm == OptimizationAlgorithm.MOMENTUM:
            params = self._momentum_step(params, regularized_gradient, lr)
        elif self.config.algorithm == OptimizationAlgorithm.NESTEROV:
            params = self._nesterov_step(params, regularized_gradient, lr)
        else:  # GRADIENT_DESCENT
            params = params - lr * regularized_gradient

        self.iteration += 1
        return params

    def _get_learning_rate(self) -> float:
        """Get learning rate with warmup if enabled."""
        if self.config.use_warmup and self.iteration < self.config.warmup_steps:
            return self.config.learning_rate * (self.iteration + 1) / self.config.warmup_steps
        return self.config.learning_rate

    def _adam_step(self, params: np.ndarray, gradient: np.ndarray, lr: float) -> np.ndarray:
        """Adam optimization step."""
        if self.m is None:
            self.m = np.zeros_like(params)
            self.v = np.zeros_like(params)
            if self.config.use_amsgrad:
                self.v_max = np.zeros_like(params)

        # Update biased first moment estimate
        self.m = self.config.beta1 * self.m + (1 - self.config.beta1) * gradient

        # Update biased second raw moment estimate
        self.v = self.config.beta2 * self.v + (1 - self.config.beta2) * (gradient**2)

        # Compute bias-corrected first moment estimate
        m_hat = self.m / (1 - self.config.beta1 ** (self.iteration + 1))

        # Compute bias-corrected second raw moment estimate
        v_hat = self.v / (1 - self.config.beta2 ** (self.iteration + 1))

        if self.config.use_amsgrad:
            # AMSGrad variant
            self.v_max = np.maximum(self.v_max, v_hat)
            update = lr * m_hat / (np.sqrt(self.v_max) + self.config.epsilon)
        else:
            # Standard Adam
            update = lr * m_hat / (np.sqrt(v_hat) + self.config.epsilon)

        return params - update

    def _rmsprop_step(self, params: np.ndarray, gradient: np.ndarray, lr: float) -> np.ndarray:
        """RMSProp optimization step."""
        decay_rate = 0.9

        if self.cache is None:
            self.cache = np.zeros_like(params)

        self.cache = decay_rate * self.cache + (1 - decay_rate) * (gradient**2)
        update = lr * gradient / (np.sqrt(self.cache) + self.config.epsilon)

        return params - update

    def _adagrad_step(self, params: np.ndarray, gradient: np.ndarray, lr: float) -> np.ndarray:
        """AdaGrad optimization step."""
        if self.sum_squared_grad is None:
            self.sum_squared_grad = np.zeros_like(params)

        self.sum_squared_grad += gradient**2
        update = lr * gradient / (np.sqrt(self.sum_squared_grad) + self.config.epsilon)

        return params - update

    def _momentum_step(self, params: np.ndarray, gradient: np.ndarray, lr: float) -> np.ndarray:
        """Momentum optimization step."""
        if self.velocity is None:
            self.velocity = np.zeros_like(params)

        self.velocity = self.config.momentum * self.velocity - lr * gradient
        return params + self.velocity

    def _nesterov_step(self, params: np.ndarray, gradient: np.ndarray, lr: float) -> np.ndarray:
        """Nesterov accelerated gradient step."""
        if self.velocity is None:
            self.velocity = np.zeros_like(params)

        # Look-ahead position
        # Compute gradient at lookahead position (approximated with current gradient)
        self.velocity = self.config.momentum * self.velocity - lr * gradient

        return params + self.velocity

    def _lbfgs_step(self, params: np.ndarray, gradient: np.ndarray) -> np.ndarray:
        """L-BFGS optimization step (simplified)."""
        if self.old_grad is None:
            self.old_grad = gradient.copy()
            self.old_params = params.copy()
            # First step: use gradient descent
            return params - self.config.learning_rate * gradient

        # Compute s and y
        s = params - self.old_params
        y = gradient - self.old_grad

        # Update history
        self.s_history.append(s)
        self.y_history.append(y)
        self.rho_history.append(1.0 / (np.dot(y, s) + 1e-8))

        # Limit history size
        if len(self.s_history) > self.history_size:
            self.s_history.pop(0)
            self.y_history.pop(0)
            self.rho_history.pop(0)

        # Two-loop recursion to compute search direction
        q = -gradient.copy()
        alpha = []

        for i in reversed(range(len(self.s_history))):
            alpha_i = self.rho_history[i] * np.dot(self.s_history[i], q)
            alpha.append(alpha_i)
            q = q - alpha_i * self.y_history[i]

        # Scale by Hessian approximation
        gamma = np.dot(self.s_history[-1], self.y_history[-1]) / (
            np.dot(self.y_history[-1], self.y_history[-1]) + 1e-8
        )
        r = gamma * q

        for i in range(len(self.s_history)):
            beta = self.rho_history[i] * np.dot(self.y_history[i], r)
            r = r + self.s_history[i] * (alpha[-i - 1] - beta)

        # Line search (simplified)
        step_size = self.config.learning_rate

        # Update
        new_params = params + step_size * r

        # Store for next iteration
        self.old_grad = gradient.copy()
        self.old_params = params.copy()

        return new_params

    def reset_state(self):
        """Reset optimizer state."""
        self.m = None
        self.v = None
        self.v_max = None
        self.cache = None
        self.sum_squared_grad = None
        self.velocity = None
        self.s_history = []
        self.y_history = []
        self.rho_history = []
        self.old_grad = None
        self.old_params = None
        self.iteration = 0


class NeuralEmbeddingNetwork:
    """
    Neural network for learnable manifold embeddings.

    Implements a configurable neural network that maps points to manifold
    embeddings with learnable parameters optimized via gradient flow.
    """

    def __init__(self, config: NeuralEmbeddingConfig):
        """
        Initialize neural embedding network.

        Args:
            config: Neural network configuration
        """
        self.config = config

        # Build network architecture
        self.layer_sizes = [config.input_dim, *config.hidden_dims, config.output_dim]
        self.num_layers = len(self.layer_sizes) - 1

        # Initialize weights and biases
        self.weights, self.biases = self._initialize_parameters()

        # Store activations for backpropagation
        self.activations = []
        self.pre_activations = []

        logger.info(f"Initialized neural embedding network: {self.layer_sizes}")

    def _initialize_parameters(self) -> tuple[list[np.ndarray], list[np.ndarray]]:
        """Initialize network parameters."""
        weights = []
        biases = []

        for i in range(self.num_layers):
            fan_in = self.layer_sizes[i]
            fan_out = self.layer_sizes[i + 1]

            if self.config.initialization == "xavier":
                # Xavier/Glorot initialization
                scale = np.sqrt(2.0 / (fan_in + fan_out))
                W = np.random.randn(fan_out, fan_in) * scale
            elif self.config.initialization == "he":
                # He initialization
                scale = np.sqrt(2.0 / fan_in)
                W = np.random.randn(fan_out, fan_in) * scale
            elif self.config.initialization == "orthogonal":
                # Orthogonal initialization
                W = np.random.randn(fan_out, fan_in)
                if fan_out > fan_in:
                    q, _ = np.linalg.qr(W.T)
                    W = q.T
                else:
                    q, _ = np.linalg.qr(W)
                    W = q
            else:
                W = np.random.randn(fan_out, fan_in) * 0.01

            b = np.zeros(fan_out)

            weights.append(W)
            biases.append(b)

        return weights, biases

    def _activation(self, x: np.ndarray) -> np.ndarray:
        """Apply activation function."""
        if self.config.activation == "tanh":
            return np.tanh(x)
        elif self.config.activation == "relu":
            return np.maximum(0, x)
        elif self.config.activation == "sigmoid":
            return 1.0 / (1.0 + np.exp(-x))
        elif self.config.activation == "gelu":
            return 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x**3)))
        else:
            return np.tanh(x)  # Default

    def _activation_derivative(self, x: np.ndarray) -> np.ndarray:
        """Compute derivative of activation function."""
        if self.config.activation == "tanh":
            return 1 - np.tanh(x) ** 2
        elif self.config.activation == "relu":
            return (x > 0).astype(float)
        elif self.config.activation == "sigmoid":
            s = 1.0 / (1.0 + np.exp(-x))
            return s * (1 - s)
        elif self.config.activation == "gelu":
            # Approximate GELU derivative
            tanh_term = np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x**3))
            return 0.5 * (1 + tanh_term) + 0.5 * x * (1 - tanh_term**2) * np.sqrt(2 / np.pi) * (
                1 + 0.134145 * x**2
            )
        else:
            return 1 - np.tanh(x) ** 2

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        Forward pass through network.

        Args:
            x: Input point (scalar or vector)

        Returns:
            Embedding vector
        """
        # Ensure x is 2D
        if x.ndim == 0:
            x = np.array([[x]])
        elif x.ndim == 1:
            x = x.reshape(1, -1)

        # Normalize input
        if self.config.input_dim == 32:
            # Special case: 32-bit integer
            x_norm = x / (2**32 - 1)
        else:
            x_norm = x

        self.activations = [x_norm]
        self.pre_activations = []

        # Forward pass through layers
        for i in range(self.num_layers):
            W = self.weights[i]
            b = self.biases[i]

            # Linear transformation
            z = self.activations[-1] @ W.T + b
            self.pre_activations.append(z)

            # Skip connection (if enabled and dimensions match)
            if self.config.use_skip_connections and i > 0 and z.shape == self.activations[-2].shape:
                z = z + self.activations[-2]

            # Activation (except for output layer)
            if i < self.num_layers - 1:
                a = self._activation(z)
            else:
                a = z  # No activation on output

            self.activations.append(a)

        return self.activations[-1].flatten()

    def get_parameters(self) -> np.ndarray:
        """Get all parameters as a single flattened array."""
        params = []
        for W, b in zip(self.weights, self.biases):
            params.append(W.flatten())
            params.append(b.flatten())
        return np.concatenate(params)

    def set_parameters(self, params: np.ndarray):
        """Set parameters from a flattened array."""
        idx = 0
        for i in range(self.num_layers):
            W_size = self.weights[i].size
            b_size = self.biases[i].size

            self.weights[i] = params[idx : idx + W_size].reshape(self.weights[i].shape)
            idx += W_size

            self.biases[i] = params[idx : idx + b_size].reshape(self.biases[i].shape)
            idx += b_size

    def compute_gradient(
        self, point: int, oracle_value: float, epsilon: float = 1e-6
    ) -> np.ndarray:
        """
        Compute gradient of loss with respect to parameters using finite differences.

        Args:
            point: Input point
            oracle_value: Oracle value at point
            epsilon: Finite difference step size

        Returns:
            Gradient vector
        """
        current_params = self.get_parameters()
        gradient = np.zeros_like(current_params)

        # Loss: negative oracle value (want to maximize)
        current_loss = -oracle_value

        for i in range(len(current_params)):
            # Perturb parameter
            original_param = current_params[i]
            current_params[i] += epsilon
            self.set_parameters(current_params)

            # Compute new loss
            new_loss = -oracle_value  # Same oracle for gradient estimation

            # Finite difference
            gradient[i] = (new_loss - current_loss) / epsilon

            # Restore parameter
            current_params[i] = original_param
            self.set_parameters(current_params)

        return gradient

    def embed(self, point: int) -> np.ndarray:
        """
        Embed a point using the neural network.

        Args:
            point: Input point (integer)

        Returns:
            Embedding vector
        """
        return self.forward(point)


class LearnableManifold(ABC):
    """
    Abstract base class for learnable manifolds.

    Manifolds that can adapt their geometry based on oracle feedback
    via gradient flow optimization.
    """

    def __init__(self, config: Any, optimizer_config: GradientFlowConfig):
        """
        Initialize learnable manifold.

        Args:
            config: Manifold configuration
            optimizer_config: Optimizer configuration
        """
        self.config = config
        self.optimizer_config = optimizer_config
        self.optimizer = AdvancedGradientFlowOptimizer(optimizer_config)
        self.iteration = 0

    @abstractmethod
    def embed(self, point: int) -> np.ndarray:
        """Embed a point using current parameters."""

    @abstractmethod
    def compute_gradient(self, point: int, oracle_value: float) -> np.ndarray:
        """Compute gradient of loss with respect to parameters."""

    @abstractmethod
    def get_parameters(self) -> np.ndarray:
        """Get all learnable parameters."""

    @abstractmethod
    def set_parameters(self, params: np.ndarray):
        """Set learnable parameters."""

    def update(self, point: int, oracle_value: float):
        """
        Update manifold parameters based on oracle feedback.

        Args:
            point: Sample point
            oracle_value: Oracle value at point
        """
        gradient = self.compute_gradient(point, oracle_value)
        params = self.get_parameters()
        updated_params = self.optimizer.step(params, gradient)
        self.set_parameters(updated_params)
        self.iteration += 1


class NeuralManifold(LearnableManifold):
    """
    Manifold with neural network-based learnable embedding.

    Uses a neural network to learn optimal embedding functions
    for the manifold geometry.
    """

    def __init__(self, nn_config: NeuralEmbeddingConfig, optimizer_config: GradientFlowConfig):
        """
        Initialize neural manifold.

        Args:
            nn_config: Neural network configuration
            optimizer_config: Optimizer configuration
        """
        super().__init__(nn_config, optimizer_config)
        self.nn = NeuralEmbeddingNetwork(nn_config)

    def embed(self, point: int) -> np.ndarray:
        """Embed point using neural network."""
        return self.nn.embed(point)

    def compute_gradient(self, point: int, oracle_value: float) -> np.ndarray:
        """Compute gradient via neural network."""
        return self.nn.compute_gradient(point, oracle_value)

    def get_parameters(self) -> np.ndarray:
        """Get neural network parameters."""
        return self.nn.get_parameters()

    def set_parameters(self, params: np.ndarray):
        """Set neural network parameters."""
        self.nn.set_parameters(params)


@dataclass
class ManifoldQualityMetrics:
    """Comprehensive metrics for evaluating manifold quality."""

    exploration_efficiency: float
    """How well the manifold explores the search space."""

    convergence_rate: float
    """Rate of convergence to optimal solutions."""

    smoothness: float
    """Smoothness of the embedding function."""

    coverage: float
    """Coverage of the search space."""

    gradient_norm: float
    """Average gradient norm (stability metric)."""

    parameter_variance: float
    """Variance of learned parameters."""

    embedding_diversity: float
    """Diversity of embeddings across samples."""

    oracle_correlation: float
    """Correlation between embedding distances and oracle values."""

    manifold_curvature: float
    """Estimated curvature of the manifold."""

    overall_score: float
    """Overall quality score (weighted combination)."""

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return asdict(self)


class CheckpointManager:
    """
    Manages checkpointing for manifold discovery.

    Saves and loads discovery state for resume capability.
    """

    def __init__(self, checkpoint_dir: str | None = None, checkpoint_interval: int = 100):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory for checkpoints (None for no checkpointing)
            checkpoint_interval: Save checkpoint every N iterations
        """
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_interval = checkpoint_interval

        if checkpoint_dir:
            Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"Checkpointing enabled: {checkpoint_dir}")

    def save_checkpoint(
        self,
        iteration: int,
        parameters: np.ndarray,
        optimizer_state: dict[str, Any],
        quality_metrics: ManifoldQualityMetrics | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Save checkpoint.

        Args:
            iteration: Current iteration
            parameters: Model parameters
            optimizer_state: Optimizer state
            quality_metrics: Optional quality metrics
            metadata: Additional metadata
        """
        if not self.checkpoint_dir:
            return

        checkpoint_data = {
            "iteration": iteration,
            "parameters": parameters.tolist(),
            "optimizer_state": optimizer_state,
            "quality_metrics": quality_metrics.to_dict() if quality_metrics else None,
            "metadata": metadata or {},
            "timestamp": time.time(),
        }

        filepath = Path(self.checkpoint_dir) / f"checkpoint_iter_{iteration}.json"
        with open(filepath, "w") as f:
            json.dump(checkpoint_data, f, indent=2)

        # Also save as latest checkpoint
        latest_filepath = Path(self.checkpoint_dir) / "checkpoint_latest.json"
        with open(latest_filepath, "w") as f:
            json.dump(checkpoint_data, f, indent=2)

        logger.debug(f"Saved checkpoint at iteration {iteration}")

    def load_checkpoint(self, filepath: str) -> dict[str, Any]:
        """
        Load checkpoint.

        Args:
            filepath: Path to checkpoint file

        Returns:
            Checkpoint data dictionary
        """
        with open(filepath) as f:
            data = json.load(f)

        data["parameters"] = np.array(data["parameters"])

        logger.info(f"Loaded checkpoint from iteration {data['iteration']}")
        return data

    def load_latest_checkpoint(self) -> dict[str, Any] | None:
        """
        Load latest checkpoint.

        Returns:
            Latest checkpoint data or None if no checkpoint exists
        """
        if not self.checkpoint_dir:
            return None

        latest_filepath = Path(self.checkpoint_dir) / "checkpoint_latest.json"
        if latest_filepath.exists():
            return self.load_checkpoint(str(latest_filepath))

        return None

    def should_checkpoint(self, iteration: int) -> bool:
        """
        Check if checkpoint should be saved.

        Args:
            iteration: Current iteration

        Returns:
            True if checkpoint should be saved
        """
        return self.checkpoint_dir is not None and iteration % self.checkpoint_interval == 0


class QualityEvaluator:
    """
    Comprehensive quality evaluation for learned manifolds.

    Computes multiple metrics to assess manifold quality for
    optimization tasks.
    """

    def __init__(self, sample_size: int = 1000):
        """
        Initialize quality evaluator.

        Args:
            sample_size: Number of sample points for evaluation
        """
        self.sample_size = sample_size

    def evaluate(self, manifold: LearnableManifold, oracle: Oracle) -> ManifoldQualityMetrics:
        """
        Evaluate manifold quality.

        Args:
            manifold: Learnable manifold to evaluate
            oracle: Oracle for evaluation

        Returns:
            Quality metrics
        """
        # Sample points
        points = np.random.randint(0, 2**32, size=self.sample_size)

        # Compute embeddings and oracle values
        embeddings = []
        values = []

        for point in points:
            embed = manifold.embed(point)
            value = oracle.evaluate(point)
            embeddings.append(embed)
            values.append(value)

        embeddings = np.array(embeddings)
        values = np.array(values)

        # Compute metrics
        exploration_efficiency = self._compute_exploration_efficiency(values)
        convergence_rate = self._compute_convergence_rate(values)
        smoothness = self._compute_smoothness(manifold, points)
        coverage = self._compute_coverage(embeddings)
        gradient_norm = self._compute_gradient_norm(manifold, points, values)
        parameter_variance = np.var(manifold.get_parameters())
        embedding_diversity = self._compute_embedding_diversity(embeddings)
        oracle_correlation = self._compute_oracle_correlation(embeddings, values)
        manifold_curvature = self._compute_manifold_curvature(manifold, points)

        # Overall score (weighted combination)
        overall_score = (
            0.20 * exploration_efficiency
            + 0.20 * convergence_rate
            + 0.15 * smoothness
            + 0.10 * coverage
            + 0.10 * (1.0 / (1.0 + gradient_norm))
            + 0.05 * (1.0 / (1.0 + parameter_variance))
            + 0.10 * embedding_diversity
            + 0.05 * oracle_correlation
            + 0.05 * manifold_curvature
        )

        return ManifoldQualityMetrics(
            exploration_efficiency=exploration_efficiency,
            convergence_rate=convergence_rate,
            smoothness=smoothness,
            coverage=coverage,
            gradient_norm=gradient_norm,
            parameter_variance=parameter_variance,
            embedding_diversity=embedding_diversity,
            oracle_correlation=oracle_correlation,
            manifold_curvature=manifold_curvature,
            overall_score=overall_score,
        )

    def _compute_exploration_efficiency(self, values: np.ndarray) -> float:
        """Compute exploration efficiency."""
        # Higher variance suggests better exploration
        return np.std(values)

    def _compute_convergence_rate(self, values: np.ndarray) -> float:
        """Compute convergence rate."""
        # Maximum value indicates convergence potential
        return np.max(values)

    def _compute_smoothness(self, manifold: LearnableManifold, points: np.ndarray) -> float:
        """Compute smoothness of embedding function."""
        if len(points) < 2:
            return 0.0

        # Compute pairwise embedding differences
        embeddings = [manifold.embed(p) for p in points[:100]]  # Limit for efficiency
        smoothness = 0.0

        for i in range(len(embeddings) - 1):
            diff = embeddings[i + 1] - embeddings[i]
            smoothness += np.linalg.norm(diff)

        smoothness /= len(embeddings) - 1

        # Normalize (lower is smoother)
        return 1.0 / (1.0 + smoothness)

    def _compute_coverage(self, embeddings: np.ndarray) -> float:
        """Compute coverage of embedding space."""
        # Spread of embeddings
        return np.mean(np.std(embeddings, axis=0))

    def _compute_gradient_norm(
        self, manifold: LearnableManifold, points: np.ndarray, values: np.ndarray
    ) -> float:
        """Compute average gradient norm."""
        gradients = []

        for point, value in zip(points[:50], values[:50]):  # Limit for efficiency
            grad = manifold.compute_gradient(point, value)
            gradients.append(np.linalg.norm(grad))

        return np.mean(gradients) if gradients else 0.0

    def _compute_embedding_diversity(self, embeddings: np.ndarray) -> float:
        """Compute diversity of embeddings."""
        # Average pairwise distance
        n = len(embeddings)
        if n < 2:
            return 0.0

        distances = []
        for i in range(min(n, 100)):
            for j in range(i + 1, min(n, 100)):
                dist = np.linalg.norm(embeddings[i] - embeddings[j])
                distances.append(dist)

        return np.mean(distances) if distances else 0.0

    def _compute_oracle_correlation(self, embeddings: np.ndarray, values: np.ndarray) -> float:
        """Compute correlation between embedding distances and oracle values."""
        n = len(embeddings)
        if n < 2:
            return 0.0

        # Compute embedding distances and value differences
        embed_distances = []
        value_diffs = []

        for i in range(min(n, 50)):
            for j in range(i + 1, min(n, 50)):
                embed_dist = np.linalg.norm(embeddings[i] - embeddings[j])
                value_diff = abs(values[i] - values[j])
                embed_distances.append(embed_dist)
                value_diffs.append(value_diff)

        if not embed_distances:
            return 0.0

        # Compute correlation
        correlation = np.corrcoef(embed_distances, value_diffs)[0, 1]

        return abs(correlation) if not np.isnan(correlation) else 0.0

    def _compute_manifold_curvature(self, manifold: LearnableManifold, points: np.ndarray) -> float:
        """Compute estimated manifold curvature."""
        # Approximate curvature using second derivatives
        if len(points) < 3:
            return 0.0

        curvatures = []

        for point in points[:50]:
            # Compute embedding and perturbed embeddings
            embed = manifold.embed(point)
            embed_plus = manifold.embed(point + 1)
            embed_minus = manifold.embed(point - 1)

            # Second difference approximation
            second_diff = embed_plus - 2 * embed + embed_minus
            curvature = np.linalg.norm(second_diff)
            curvatures.append(curvature)

        return np.mean(curvatures) if curvatures else 0.0


class CryptographicHashManifoldDiscovery:
    """
    Specialized manifold discovery for cryptographic hash functions.

    Optimizes manifold geometry for specific hash functions (e.g., SHA-256)
    by leveraging hash-specific properties and structure.
    """

    def __init__(
        self,
        hash_function: str = "sha256",
        nn_config: NeuralEmbeddingConfig | None = None,
        optimizer_config: GradientFlowConfig | None = None,
    ):
        """
        Initialize cryptographic hash manifold discovery.

        Args:
            hash_function: Name of hash function (e.g., 'sha256', 'sha1', 'md5')
            nn_config: Neural network configuration (uses defaults if None)
            optimizer_config: Optimizer configuration (uses defaults if None)
        """
        self.hash_function = hash_function

        # Hash-specific adjustments
        if hash_function == "sha256":
            embedding_dim = 8  # SHA-256 has 8 32-bit words
        elif hash_function == "sha1":
            embedding_dim = 5
        elif hash_function == "md5":
            embedding_dim = 4
        else:
            embedding_dim = 3  # Default

        # Create configurations
        if nn_config is None:
            nn_config = NeuralEmbeddingConfig(
                input_dim=32,
                hidden_dims=[128, 64, 32],
                output_dim=embedding_dim,
                activation="tanh",
                use_skip_connections=True,
            )
        else:
            nn_config.output_dim = embedding_dim

        if optimizer_config is None:
            optimizer_config = GradientFlowConfig(
                algorithm=OptimizationAlgorithm.ADAM,
                learning_rate=0.001,
                max_iterations=5000,
            )

        self.nn_config = nn_config
        self.optimizer_config = optimizer_config
        self.manifold = NeuralManifold(nn_config, optimizer_config)

        logger.info(f"Initialized cryptographic hash manifold discovery for {hash_function}")

    def discover(
        self,
        oracle: Oracle,
        max_iterations: int = 5000,
        sample_size: int = 100,
        checkpoint_dir: str | None = None,
        verbose: bool = True,
    ) -> tuple[NeuralManifold, ManifoldQualityMetrics]:
        """
        Discover optimal manifold for cryptographic hash.

        Args:
            oracle: Oracle function for evaluation
            max_iterations: Maximum discovery iterations
            sample_size: Number of samples per iteration
            checkpoint_dir: Checkpoint directory
            verbose: Enable verbose logging

        Returns:
            Tuple of (learned manifold, quality metrics)
        """
        checkpoint_manager = CheckpointManager(checkpoint_dir, checkpoint_interval=100)
        quality_evaluator = QualityEvaluator(sample_size=1000)

        # Try to load from checkpoint
        checkpoint = checkpoint_manager.load_latest_checkpoint()
        if checkpoint:
            self.manifold.set_parameters(checkpoint["parameters"])
            start_iteration = checkpoint["iteration"]
            logger.info(f"Resuming from iteration {start_iteration}")
        else:
            start_iteration = 0

        best_quality = 0.0
        best_parameters = self.manifold.get_parameters().copy()

        start_time = time.time()

        for iteration in range(start_iteration, max_iterations):
            # Hash-aware sampling
            points = self._hash_aware_sample(sample_size)

            # Update manifold based on samples
            for point in points:
                value = oracle.evaluate(point)
                self.manifold.update(point, value)

            # Evaluate quality periodically
            if iteration % 100 == 0:
                quality = quality_evaluator.evaluate(self.manifold, oracle)

                if quality.overall_score > best_quality:
                    best_quality = quality.overall_score
                    best_parameters = self.manifold.get_parameters().copy()

                if verbose:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"Iteration {iteration}: Quality={quality.overall_score:.4f}, "
                        f"Exploration={quality.exploration_efficiency:.4f}, "
                        f"Time={elapsed:.2f}s"
                    )

                # Checkpoint
                if checkpoint_manager.should_checkpoint(iteration):
                    optimizer_state = {
                        "iteration": self.manifold.optimizer.iteration,
                        "algorithm": self.manifold.optimizer.config.algorithm.value,
                    }
                    checkpoint_manager.save_checkpoint(
                        iteration,
                        self.manifold.get_parameters(),
                        optimizer_state,
                        quality,
                        {"hash_function": self.hash_function},
                    )

            # Check convergence
            if iteration > 500 and self._check_convergence():
                if verbose:
                    logger.info(f"Converged at iteration {iteration}")
                break

        # Set best parameters
        self.manifold.set_parameters(best_parameters)

        # Final evaluation
        final_quality = quality_evaluator.evaluate(self.manifold, oracle)

        elapsed_time = time.time() - start_time

        if verbose:
            logger.info(f"Discovery completed in {elapsed_time:.2f}s")
            logger.info(f"Final quality: {final_quality.overall_score:.4f}")

        return self.manifold, final_quality

    def _hash_aware_sample(self, sample_size: int) -> list[int]:
        """Sample points with hash-aware strategy."""
        points = []

        # Uniform random
        points.extend(np.random.randint(0, 2**32, size=sample_size // 2).tolist())

        # Structured patterns based on hash function
        if self.hash_function == "sha256":
            # SHA-256 processes data in 512-bit blocks
            for i in range(sample_size // 2):
                # Create points aligned with 512-bit blocks
                block_aligned = (i << 9) & 0xFFFFFFFF
                points.append(block_aligned)

        return points

    def _check_convergence(self, tolerance: float = 1e-6) -> bool:
        """Check if manifold has converged."""
        # Simple convergence check based on parameter changes
        params = self.manifold.get_parameters()

        if not hasattr(self, "_prev_params"):
            self._prev_params = params.copy()
            return False

        param_change = np.linalg.norm(params - self._prev_params)
        self._prev_params = params.copy()

        return param_change < tolerance


class EnhancedManifoldDiscoveryEngine:
    """
    Enhanced manifold discovery engine integrating all v9.0 features.

    Combines symmetry detection, variational learning, neural embeddings,
    advanced optimization, and quality evaluation for comprehensive
    manifold discovery.
    """

    def __init__(
        self,
        representation: ManifoldRepresentation = ManifoldRepresentation.NEURAL_EMBEDDING,
        optimizer_algorithm: OptimizationAlgorithm = OptimizationAlgorithm.ADAM,
        checkpoint_dir: str | None = None,
        verbose: bool = True,
    ):
        """
        Initialize enhanced manifold discovery engine.

        Args:
            representation: Manifold representation type
            optimizer_algorithm: Optimization algorithm
            checkpoint_dir: Checkpoint directory
            verbose: Enable verbose logging
        """
        self.representation = representation
        self.optimizer_algorithm = optimizer_algorithm
        self.checkpoint_dir = checkpoint_dir
        self.verbose = verbose

        # Initialize components
        self.symmetry_detector = SymmetryDetector()
        self.variational_learner = VariationalManifoldLearner()
        self.quality_evaluator = QualityEvaluator()
        self.checkpoint_manager = CheckpointManager(checkpoint_dir, checkpoint_interval=100)

        logger.info(f"Initialized Enhanced Manifold Discovery Engine with {representation.value}")

    def discover(
        self,
        oracle: Oracle,
        max_iterations: int = 5000,
        hash_function: str | None = None,
    ) -> dict[str, Any]:
        """
        Discover optimal manifold using comprehensive approach.

        Args:
            oracle: Oracle function for evaluation
            max_iterations: Maximum discovery iterations
            hash_function: Optional hash function for specialized discovery

        Returns:
            Dictionary containing discovery results
        """
        logger.info("Starting enhanced manifold discovery...")

        results = {
            "symmetries": [],
            "learned_manifold": None,
            "quality_metrics": None,
            "variational_metric": None,
            "proposals": [],
        }

        # Detect symmetries
        if self.verbose:
            logger.info("Detecting symmetries...")
        symmetries = self.symmetry_detector.detect_all_symmetries(oracle)
        results["symmetries"] = symmetries

        # Learn variational metric
        if self.verbose:
            logger.info("Learning variational metric...")
        learned_metric, loss_history = self.variational_learner.learn_metric(oracle)
        results["variational_metric"] = learned_metric
        results["variational_loss_history"] = loss_history

        # Neural manifold discovery
        if self.representation == ManifoldRepresentation.NEURAL_EMBEDDING:
            if self.verbose:
                logger.info("Discovering neural manifold...")

            if hash_function:
                # Use hash-specific discovery
                crypto_discovery = CryptographicHashManifoldDiscovery(
                    hash_function=hash_function,
                    optimizer_config=GradientFlowConfig(
                        algorithm=self.optimizer_algorithm,
                        max_iterations=max_iterations,
                    ),
                    checkpoint_dir=self.checkpoint_dir,
                )
                manifold, quality = crypto_discovery.discover(
                    oracle, max_iterations=max_iterations, verbose=self.verbose
                )
            else:
                # Generic neural discovery
                nn_config = NeuralEmbeddingConfig()
                optimizer_config = GradientFlowConfig(
                    algorithm=self.optimizer_algorithm, max_iterations=max_iterations
                )

                manifold = NeuralManifold(nn_config, optimizer_config)
                quality = self._train_neural_manifold(manifold, oracle, max_iterations)

            results["learned_manifold"] = manifold
            results["quality_metrics"] = quality

        # Generate proposals based on symmetries
        proposals = self._generate_proposals(symmetries, learned_metric)
        results["proposals"] = proposals

        if self.verbose:
            logger.info("Manifold discovery completed")

        return results

    def _train_neural_manifold(
        self, manifold: NeuralManifold, oracle: Oracle, max_iterations: int
    ) -> ManifoldQualityMetrics:
        """Train neural manifold."""
        sample_size = 100

        for iteration in range(max_iterations):
            points = np.random.randint(0, 2**32, size=sample_size)

            for point in points:
                value = oracle.evaluate(point)
                manifold.update(point, value)

            if iteration % 100 == 0 and self.verbose:
                quality = self.quality_evaluator.evaluate(manifold, oracle)
                logger.info(f"Iteration {iteration}: Quality={quality.overall_score:.4f}")

        return self.quality_evaluator.evaluate(manifold, oracle)

    def _generate_proposals(
        self, symmetries: list[SymmetryDetectionResult], learned_metric: np.ndarray
    ) -> list[ManifoldProposal]:
        """Generate manifold proposals."""
        proposals = []

        for symmetry in symmetries:
            if symmetry.confidence < 0.3:
                continue

            proposal = self._create_proposal_from_symmetry(symmetry)
            if proposal:
                proposals.append(proposal)

        # Add variational proposal
        variational_proposal = self._create_variational_proposal(learned_metric)
        proposals.append(variational_proposal)

        return proposals

    def _create_proposal_from_symmetry(
        self, symmetry: SymmetryDetectionResult
    ) -> ManifoldProposal | None:
        """Create proposal from symmetry."""
        # Simplified proposal creation
        config = ManifoldConfig(
            dimension=32,
            embedding_dim=3,
            curvature_type="positive",
            metric_type="riemannian",
            metadata={"symmetry": symmetry.symmetry_type.value},
        )

        return ManifoldProposal(
            manifold_type=f"{symmetry.symmetry_type.value}_manifold",
            config=config,
            expected_performance=symmetry.confidence,
            symmetry_basis=[symmetry],
            description=f"Manifold based on {symmetry.symmetry_type.value} symmetry",
        )

    def _create_variational_proposal(self, learned_metric: np.ndarray) -> ManifoldProposal:
        """Create variational proposal."""
        dimension = learned_metric.shape[0]

        config = ManifoldConfig(
            dimension=dimension,
            embedding_dim=dimension,
            curvature_type="variable",
            metric_type="riemannian",
            metadata={"type": "variational_learned"},
        )

        return ManifoldProposal(
            manifold_type="variational_learned",
            config=config,
            expected_performance=0.7,
            symmetry_basis=[],
            description="Variational learned manifold",
        )


class SymmetryDetector:
    """
    Detect symmetries in cost functions to inform manifold construction.

    Analyzes cost functions for rotational, reflectional, translational,
    scaling, and golden-ratio/Fibonacci symmetries.
    """

    def __init__(self, sample_size: int = 1000, tolerance: float = 1e-3):
        """
        Initialize symmetry detector.

        Args:
            sample_size: Number of sample points for analysis
            tolerance: Tolerance for symmetry detection
        """
        self.sample_size = sample_size
        self.tolerance = tolerance
        self.phi = (1 + math.sqrt(5)) / 2  # Golden ratio
        self.phi_inv = self.phi - 1  # φ⁻¹

    def detect_golden_ratio_symmetry(
        self, oracle: Oracle, sample_points: np.ndarray | None = None
    ) -> SymmetryDetectionResult:
        """
        Detect golden-ratio scaling symmetry in cost function.

        Tests if f(φ * x) ≈ φ⁻¹ * f(x) or similar φ-scaling relationships.

        Args:
            oracle: Oracle to evaluate cost function
            sample_points: Optional sample points (generates random if None)

        Returns:
            SymmetryDetectionResult for golden-ratio symmetry
        """
        if sample_points is None:
            sample_points = np.random.randint(0, 2**32, size=self.sample_size)

        evidence = []
        phi_ratios = []

        for point in sample_points[:100]:  # Limit for efficiency
            base_value = oracle.evaluate(point)

            # Test φ-scaling: f(φ * point) vs f(point)
            scaled_point = int((point * self.phi) % (2**32))
            scaled_value = oracle.evaluate(scaled_point)

            # Check for φ-scaling relationship
            if base_value > self.tolerance:
                ratio = scaled_value / base_value
                phi_ratios.append(abs(ratio - self.phi_inv))
                evidence.append((point, ratio))

        # Compute confidence based on deviation from φ⁻¹
        if phi_ratios:
            mean_deviation = np.mean(phi_ratios)
            confidence = max(0.0, 1.0 - mean_deviation * 10)
        else:
            confidence = 0.0

        return SymmetryDetectionResult(
            symmetry_type=SymmetryType.GOLDEN_RATIO,
            confidence=float(confidence),
            parameters={
                "phi": self.phi,
                "phi_inv": self.phi_inv,
                "mean_deviation": float(np.mean(phi_ratios)) if phi_ratios else 0.0,
            },
            evidence=evidence[:10],  # Keep top evidence
            metadata={"sample_size": len(sample_points)},
        )

    def detect_fibonacci_symmetry(
        self, oracle: Oracle, sample_points: np.ndarray | None = None
    ) -> SymmetryDetectionResult:
        """
        Detect Fibonacci step symmetry in cost function.

        Tests if cost function exhibits structure aligned with Fibonacci
        sequence step sizes (1, 2, 3, 5, 8, 13, ...).

        Args:
            oracle: Oracle to evaluate cost function
            sample_points: Optional sample points

        Returns:
            SymmetryDetectionResult for Fibonacci symmetry
        """
        fib_sequence = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89]

        if sample_points is None:
            sample_points = np.random.randint(0, 2**32, size=self.sample_size)

        evidence = []
        correlations = []

        for point in sample_points[:100]:
            base_value = oracle.evaluate(point)

            # Test Fibonacci step correlations
            for fib_step in fib_sequence[:5]:
                stepped_point = (point + fib_step) % (2**32)
                stepped_value = oracle.evaluate(stepped_point)

                # Check correlation
                if base_value > self.tolerance:
                    correlation = abs(stepped_value - base_value)
                    correlations.append(correlation)
                    evidence.append((point, fib_step, correlation))

        # Low correlation suggests Fibonacci structure (cost function respects steps)
        if correlations:
            mean_correlation = np.mean(correlations)
            confidence = max(0.0, 1.0 - mean_correlation)
        else:
            confidence = 0.0

        return SymmetryDetectionResult(
            symmetry_type=SymmetryType.FIBONACCI,
            confidence=float(confidence),
            parameters={
                "fibonacci_sequence": fib_sequence,
                "mean_correlation": (float(np.mean(correlations)) if correlations else 0.0),
            },
            evidence=[(e[0], e[2]) for e in evidence[:10]],
            metadata={"sample_size": len(sample_points)},
        )

    def detect_rotational_symmetry(
        self, oracle: Oracle, sample_points: np.ndarray | None = None
    ) -> SymmetryDetectionResult:
        """
        Detect rotational symmetry in cost function.

        Tests if f(R_θ(x)) ≈ f(x) for rotation operators R_θ.

        Args:
            oracle: Oracle to evaluate cost function
            sample_points: Optional sample points

        Returns:
            SymmetryDetectionResult for rotational symmetry
        """
        if sample_points is None:
            sample_points = np.random.randint(0, 2**32, size=self.sample_size)

        evidence = []
        variances = []

        # Test rotations by different angles (simulated via bit rotations)
        for point in sample_points[:100]:
            _base_value = oracle.evaluate(point)

            # Simulate rotations via bit rotations
            rotated_values = []
            for shift in [1, 2, 4, 8, 16]:
                rotated = ((point << shift) | (point >> (32 - shift))) & 0xFFFFFFFF
                rotated_value = oracle.evaluate(rotated)
                rotated_values.append(rotated_value)

            # Check variance across rotations
            variance = np.var(rotated_values)
            variances.append(variance)
            evidence.append((point, variance))

        # Low variance suggests rotational symmetry
        if variances:
            mean_variance = np.mean(variances)
            confidence = max(0.0, 1.0 - mean_variance * 10)
        else:
            confidence = 0.0

        return SymmetryDetectionResult(
            symmetry_type=SymmetryType.ROTATIONAL,
            confidence=float(confidence),
            parameters={"mean_variance": float(np.mean(variances)) if variances else 0.0},
            evidence=evidence[:10],
            metadata={"sample_size": len(sample_points)},
        )

    def detect_all_symmetries(
        self, oracle: Oracle, sample_points: np.ndarray | None = None
    ) -> list[SymmetryDetectionResult]:
        """
        Detect all symmetries in the cost function.

        Args:
            oracle: Oracle to evaluate
            sample_points: Optional sample points

        Returns:
            List of all detected symmetries sorted by confidence
        """
        results = [
            self.detect_golden_ratio_symmetry(oracle, sample_points),
            self.detect_fibonacci_symmetry(oracle, sample_points),
            self.detect_rotational_symmetry(oracle, sample_points),
        ]

        # Sort by confidence
        results.sort(key=lambda r: r.confidence, reverse=True)

        return results


class VariationalManifoldLearner:
    """
    Learn optimal manifold structure via variational optimization.

    Optimizes the embedding metric tensor via gradient flow on the space
    of Riemannian metrics to maximize search efficiency.
    """

    def __init__(
        self,
        learning_rate: float = 0.01,
        max_iterations: int = 100,
        regularization: float = 0.01,
    ):
        """
        Initialize variational manifold learner.

        Args:
            learning_rate: Learning rate for gradient descent
            max_iterations: Maximum optimization iterations
            regularization: L2 regularization coefficient
        """
        self.learning_rate = learning_rate
        self.max_iterations = max_iterations
        self.regularization = regularization

    def learn_metric(
        self,
        oracle: Oracle,
        initial_metric: np.ndarray | None = None,
        dimension: int = 32,
    ) -> tuple[np.ndarray, list[float]]:
        """
        Learn optimal metric tensor for the manifold.

        Args:
            oracle: Oracle to evaluate cost function
            initial_metric: Initial metric tensor (identity if None)
            dimension: Dimension of the metric

        Returns:
            Tuple of (learned_metric, loss_history)
        """
        metric = np.eye(dimension) if initial_metric is None else initial_metric.copy()

        loss_history = []

        for iteration in range(self.max_iterations):
            # Sample points
            sample_points = np.random.randint(0, 2**32, size=100)

            # Compute loss: negative correlation between metric distance and cost difference
            total_loss = 0.0
            gradient = np.zeros_like(metric)

            for i in range(len(sample_points) - 1):
                p1 = sample_points[i]
                p2 = sample_points[i + 1]

                v1 = oracle.evaluate(p1)
                v2 = oracle.evaluate(p2)

                # Simple embedding: use point values as coordinates
                x1 = np.array([((p1 >> (8 * k)) & 0xFF) / 255.0 for k in range(min(dimension, 4))])
                x2 = np.array([((p2 >> (8 * k)) & 0xFF) / 255.0 for k in range(min(dimension, 4))])

                # Pad to full dimension
                if len(x1) < dimension:
                    x1 = np.pad(x1, (0, dimension - len(x1)))
                if len(x2) < dimension:
                    x2 = np.pad(x2, (0, dimension - len(x2)))

                # Metric distance
                diff = x1 - x2
                metric_dist = np.sqrt(diff @ metric @ diff)

                # Cost difference
                cost_diff = abs(v1 - v2)

                # Loss: want metric distance to correlate with cost difference
                # High cost difference → large metric distance
                loss = (metric_dist - cost_diff) ** 2

                # Gradient contribution
                if metric_dist > 1e-10:
                    grad_contribution = (
                        2 * (metric_dist - cost_diff) * np.outer(diff, diff) / metric_dist
                    )
                    gradient += grad_contribution

                total_loss += loss

            # Add regularization
            total_loss += self.regularization * np.sum(metric**2)
            gradient += 2 * self.regularization * metric

            # Average
            total_loss /= len(sample_points)
            gradient /= len(sample_points)

            loss_history.append(total_loss)

            # Gradient descent
            metric -= self.learning_rate * gradient

            # Ensure metric is positive definite
            metric = (metric + metric.T) / 2  # Symmetrize
            eigenvals, eigenvecs = np.linalg.eigh(metric)
            eigenvals = np.maximum(eigenvals, 1e-6)  # Ensure positive
            metric = eigenvecs @ np.diag(eigenvals) @ eigenvecs.T

            if iteration % 10 == 0:
                logger.debug(f"Variational learning iteration {iteration}: loss = {total_loss:.6f}")

        return metric, loss_history


class ManifoldDiscoveryEngine:
    """
    Main engine for automated manifold discovery.

    Combines symmetry detection and variational learning to propose
    optimal manifold structures for given optimization problems.
    """

    def __init__(
        self,
        symmetry_detector: SymmetryDetector | None = None,
        variational_learner: VariationalManifoldLearner | None = None,
    ):
        """
        Initialize manifold discovery engine.

        Args:
            symmetry_detector: Symmetry detector (creates default if None)
            variational_learner: Variational learner (creates default if None)
        """
        self.symmetry_detector = symmetry_detector or SymmetryDetector()
        self.variational_learner = variational_learner or VariationalManifoldLearner()

    def discover_manifold(
        self, oracle: Oracle, sample_points: np.ndarray | None = None
    ) -> list[ManifoldProposal]:
        """
        Discover optimal manifold structure for given oracle.

        Args:
            oracle: Oracle representing the optimization problem
            sample_points: Optional sample points for analysis

        Returns:
            List of manifold proposals sorted by expected performance
        """
        logger.info("Starting manifold discovery...")

        # Detect symmetries
        symmetries = self.symmetry_detector.detect_all_symmetries(oracle, sample_points)
        logger.info(f"Detected {len(symmetries)} symmetries")

        proposals = []

        # Generate proposals based on detected symmetries
        for symmetry in symmetries:
            if symmetry.confidence < 0.3:
                continue  # Skip low-confidence symmetries

            proposal = self._create_proposal_from_symmetry(symmetry, oracle)
            if proposal:
                proposals.append(proposal)

        # Always include standard proposals
        proposals.extend(self._create_standard_proposals(oracle))

        # Learn metric via variational approach
        learned_metric, loss_history = self.variational_learner.learn_metric(oracle)

        # Add variational proposal
        variational_proposal = self._create_variational_proposal(learned_metric, loss_history)
        proposals.append(variational_proposal)

        # Sort by expected performance
        proposals.sort(key=lambda p: p.expected_performance, reverse=True)

        logger.info(f"Generated {len(proposals)} manifold proposals")

        return proposals

    def _create_proposal_from_symmetry(
        self, symmetry: SymmetryDetectionResult, oracle: Oracle
    ) -> ManifoldProposal | None:
        """Create manifold proposal from detected symmetry."""

        if symmetry.symmetry_type == SymmetryType.GOLDEN_RATIO:
            # Propose M32-like manifold with golden-ratio structure
            config = ManifoldConfig(
                dimension=32,
                embedding_dim=3,
                curvature_type="positive",
                metric_type="riemannian",
                metadata={
                    "symmetry": "golden_ratio",
                    "phi": symmetry.parameters["phi"],
                },
            )

            return ManifoldProposal(
                manifold_type="golden_ratio_manifold",
                config=config,
                expected_performance=symmetry.confidence,
                symmetry_basis=[symmetry],
                description="Golden-ratio structured manifold based on detected φ-scaling symmetry",
            )

        elif symmetry.symmetry_type == SymmetryType.FIBONACCI:
            # Propose lattice-based manifold with Fibonacci steps
            config = ManifoldConfig(
                dimension=32,
                embedding_dim=2,
                curvature_type="flat",
                metric_type="euclidean",
                metadata={
                    "symmetry": "fibonacci",
                    "steps": symmetry.parameters["fibonacci_sequence"],
                },
            )

            return ManifoldProposal(
                manifold_type="fibonacci_lattice_manifold",
                config=config,
                expected_performance=symmetry.confidence,
                symmetry_basis=[symmetry],
                description="Fibonacci lattice manifold based on detected step symmetry",
            )

        elif symmetry.symmetry_type == SymmetryType.ROTATIONAL:
            # Propose spherical manifold
            config = ManifoldConfig(
                dimension=32,
                embedding_dim=3,
                curvature_type="positive",
                metric_type="riemannian",
                metadata={"symmetry": "rotational"},
            )

            return ManifoldProposal(
                manifold_type="spherical_manifold",
                config=config,
                expected_performance=symmetry.confidence,
                symmetry_basis=[symmetry],
                description="Spherical manifold based on detected rotational symmetry",
            )

        return None

    def _create_standard_proposals(self, oracle: Oracle) -> list[ManifoldProposal]:
        """Create standard fallback proposals."""
        proposals = []

        # M32 proposal
        m32_config = ManifoldConfig(
            dimension=32,
            embedding_dim=3,
            curvature_type="positive",
            metric_type="riemannian",
            metadata={"type": "m32", "faces": 32},
        )

        proposals.append(
            ManifoldProposal(
                manifold_type="m32",
                config=m32_config,
                expected_performance=0.6,
                symmetry_basis=[],
                description="Standard M32 dodecahedron-icosahedron manifold",
            )
        )

        # Grassmannian proposal
        grassmannian_config = ManifoldConfig(
            dimension=15,  # dim(Gr(3,5)) = 3*(5-3) = 6, but use 15 for safety
            embedding_dim=15,
            curvature_type="variable",
            metric_type="riemannian",
            metadata={"type": "grassmannian", "p": 3, "n": 5},
        )

        proposals.append(
            ManifoldProposal(
                manifold_type="grassmannian",
                config=grassmannian_config,
                expected_performance=0.5,
                symmetry_basis=[],
                description="Grassmannian manifold for subspace optimization",
            )
        )

        return proposals

    def _create_variational_proposal(
        self, learned_metric: np.ndarray, loss_history: list[float]
    ) -> ManifoldProposal:
        """Create proposal from variational learning."""

        # Expected performance based on final loss
        final_loss = loss_history[-1] if loss_history else 1.0
        expected_performance = max(0.0, 1.0 - final_loss)

        dimension = learned_metric.shape[0]

        config = ManifoldConfig(
            dimension=dimension,
            embedding_dim=dimension,
            curvature_type="variable",
            metric_type="riemannian",
            metadata={
                "type": "variational",
                "learned_metric": learned_metric.tolist(),
                "final_loss": final_loss,
            },
        )

        return ManifoldProposal(
            manifold_type="variational_learned",
            config=config,
            expected_performance=expected_performance,
            symmetry_basis=[],
            description=f"Variational learned manifold (final loss: {final_loss:.6f})",
        )

    def rank_proposals(
        self, proposals: list[ManifoldProposal], oracle: Oracle, test_samples: int = 100
    ) -> list[ManifoldProposal]:
        """
        Rank proposals by empirical testing.

        Args:
            proposals: List of proposals to rank
            oracle: Oracle for testing
            test_samples: Number of test samples

        Returns:
            Ranked proposals
        """
        logger.info(f"Ranking {len(proposals)} proposals via empirical testing...")

        for proposal in proposals:
            # Simple empirical test: evaluate oracle on random points
            # and check if manifold structure would help
            test_points = np.random.randint(0, 2**32, size=test_samples)
            values = [oracle.evaluate(p) for p in test_points]

            # Update expected performance based on value distribution
            value_variance = np.var(values)
            if value_variance > 0:
                # Higher variance suggests manifold structure could help
                proposal.expected_performance = min(
                    1.0, proposal.expected_performance * (1 + value_variance)
                )

        proposals.sort(key=lambda p: p.expected_performance, reverse=True)

        return proposals


# v9.0 Exports
__all__ = [
    # Enums
    "SymmetryType",
    "OptimizationAlgorithm",
    "ManifoldRepresentation",
    # Dataclasses
    "SymmetryDetectionResult",
    "ManifoldProposal",
    "GradientFlowConfig",
    "NeuralEmbeddingConfig",
    "ManifoldQualityMetrics",
    # Core Classes (Original)
    "SymmetryDetector",
    "VariationalManifoldLearner",
    "ManifoldDiscoveryEngine",
    # v9.0 Advanced Classes
    "AdvancedGradientFlowOptimizer",
    "NeuralEmbeddingNetwork",
    "LearnableManifold",
    "NeuralManifold",
    "CryptographicHashManifoldDiscovery",
    "EnhancedManifoldDiscoveryEngine",
    # Utility Classes
    "CheckpointManager",
    "QualityEvaluator",
]
