"""
HYBA Cortex Gauge-Invariant Training with Lie Algebra SU(n)
Integrates Lie Algebra for gauge-invariant distributed training with
adjoint action and structure constants for multi-GPU coordination.
"""

import numpy as np

# Add yang_mills_data.py to path

try:
    from python_backend.yang_mills_data import LieAlgebra

    LIE_ALGEBRA_AVAILABLE = True
except ImportError:
    LIE_ALGEBRA_AVAILABLE = False
    print("Warning: yang_mills_data.py not available, using fallback implementation")


class CortexGaugeInvariantTraining:
    """
    Gauge-invariant training using Lie Algebra SU(n) for distributed
    multi-GPU coordination with adjoint action and structure constants.
    """

    def __init__(self, n_gpus: int = 2, use_lie_algebra: bool = True):
        self.use_lie_algebra = use_lie_algebra and LIE_ALGEBRA_AVAILABLE
        self.n_gpus = n_gpus

        # Initialize Lie Algebra if available
        if self.use_lie_algebra:
            self.gauge_group = LieAlgebra(dimension=n_gpus)
            self.gauge_transforms = self._generate_gauge_transforms()
            self.structure_constants = self.gauge_group.structure_constants
        else:
            self.gauge_group = None
            self.gauge_transforms = []
            self.structure_constants = None

    def _generate_gauge_transforms(self):
        """Generate SU(n) gauge transformations."""
        transforms = []
        for alpha in np.linspace(0, 2 * np.pi, 8):
            coefficients = np.array([alpha, alpha / 1.618])  # φ-scaled
            transform = self.gauge_group.exponential_map(coefficients)
            transforms.append(transform)
        return transforms

    def apply_gauge_transform(self, gradients: np.ndarray, transform_idx: int) -> np.ndarray:
        """
        Apply gauge transformation for gradient invariance.

        Args:
            gradients: Gradient tensor
            transform_idx: Index of gauge transform to apply

        Returns:
            Gauge-transformed gradients
        """
        if not self.use_lie_algebra or not self.gauge_transforms:
            return gradients

        transform = self.gauge_transforms[transform_idx % len(self.gauge_transforms)]

        # Adjoint action: Ad_g(X) = g @ X @ g†
        if len(gradients.shape) == 2:
            return transform @ gradients @ transform.conj().T
        else:
            # For higher dimensions, apply to last two dimensions
            original_shape = gradients.shape
            grad_2d = gradients.reshape(-1, original_shape[-1])
            transformed_2d = transform @ grad_2d @ transform.conj().T
            return transformed_2d.reshape(original_shape)

    def synchronize_gradients(self, local_gradients: list) -> np.ndarray:
        """
        Synchronize gradients with gauge invariance.

        Args:
            local_gradients: List of local gradients from each GPU

        Returns:
            Synchronized gradients
        """
        if not self.use_lie_algebra:
            # Fallback: simple averaging
            return np.mean(local_gradients, axis=0)

        # Apply gauge transforms
        transformed = [
            self.apply_gauge_transform(g, i % len(self.gauge_transforms))
            for i, g in enumerate(local_gradients)
        ]

        # Aggregate with structure constants
        aggregated = np.sum(transformed, axis=0)

        # Apply structure constant coordination
        if self.structure_constants is not None:
            for a in range(self.gauge_group.dimension):
                for b in range(self.gauge_group.dimension):
                    for c in range(self.gauge_group.dimension):
                        f_abc = self.structure_constants[a, b, c]
                        if abs(f_abc) > 1e-10:
                            aggregated[a] += f_abc * aggregated[b] * aggregated[c]

        return aggregated

    def get_gauge_metrics(self, gradients: np.ndarray) -> dict:
        """
        Get gauge-invariant metrics for monitoring.

        Args:
            gradients: Gradient tensor

        Returns:
            Dictionary of gauge metrics
        """
        if not self.use_lie_algebra:
            # Same keys as the gauge path so callers see one metrics contract
            # regardless of which path executed.
            return {
                "gauge_invariant": False,
                "gradient_norm": np.linalg.norm(gradients),
                "gauge_norm_mean": np.linalg.norm(gradients),
                "gauge_norm_std": 0.0,
                "gauge_variance": 0.0,
                "n_gpus": self.n_gpus,
            }

        # Compute gauge-invariant norm
        gauge_norms = []
        for i, transform in enumerate(self.gauge_transforms):
            transformed = self.apply_gauge_transform(gradients, i)
            gauge_norms.append(np.linalg.norm(transformed))

        return {
            "gauge_invariant": True,
            "gradient_norm": np.linalg.norm(gradients),
            "gauge_norm_mean": np.mean(gauge_norms),
            "gauge_norm_std": np.std(gauge_norms),
            "gauge_variance": np.var(gauge_norms),
            "n_gpus": self.n_gpus,
        }


class CortexDistributedOptimizer:
    """
    Distributed optimizer with gauge-invariant gradient synchronization.
    """

    def __init__(self, n_gpus: int = 2, base_learning_rate: float = 0.001):
        self.n_gpus = n_gpus
        self.base_lr = base_learning_rate
        self.gauge_training = CortexGaugeInvariantTraining(n_gpus=n_gpus)
        self.synchronization_history = []

    def distributed_step(self, local_gradients: list, parameters: list, epoch: int) -> dict:
        """
        Perform distributed optimization step with gauge invariance.

        Args:
            local_gradients: List of local gradients from each GPU
            parameters: List of parameters from each GPU
            epoch: Current training epoch

        Returns:
            Optimization results
        """
        # Synchronize gradients with gauge invariance
        synchronized_gradients = self.gauge_training.synchronize_gradients(local_gradients)

        # Apply learning rate
        scaled_gradients = self.base_lr * synchronized_gradients

        # Update parameters (use first parameter set as reference)
        updated_parameters = [p - scaled_gradients for p in parameters]

        # Compute gauge metrics
        gauge_metrics = self.gauge_training.get_gauge_metrics(synchronized_gradients)

        # Store synchronization history
        self.synchronization_history.append(
            {
                "epoch": epoch,
                "gradient_norm": gauge_metrics["gradient_norm"],
                "gauge_variance": gauge_metrics.get("gauge_variance", 0),
                "n_gpus": self.n_gpus,
            }
        )

        return {
            "updated_parameters": updated_parameters,
            "gauge_metrics": gauge_metrics,
            "synchronized_gradients": synchronized_gradients,
        }

    def get_synchronization_summary(self) -> dict:
        """Get summary of synchronization history."""
        if not self.synchronization_history:
            return {"status": "no_synchronization_history"}

        epochs = [h["epoch"] for h in self.synchronization_history]
        gradient_norms = [h["gradient_norm"] for h in self.synchronization_history]
        gauge_variances = [h.get("gauge_variance", 0) for h in self.synchronization_history]

        return {
            "total_steps": len(self.synchronization_history),
            "final_epoch": epochs[-1],
            "avg_gradient_norm": np.mean(gradient_norms),
            "final_gradient_norm": gradient_norms[-1],
            "avg_gauge_variance": np.mean(gauge_variances),
            "final_gauge_variance": gauge_variances[-1],
            "convergence_stability": 1.0 / (1.0 + np.std(gradient_norms)),
        }


# Convenience function for quick testing
def test_cortex_gauge_training():
    """Test the Cortex Gauge-Invariant Training enhancement."""
    print("\n=== Testing Cortex Gauge-Invariant Training Enhancement ===\n")

    # Initialize
    gauge_training = CortexGaugeInvariantTraining(n_gpus=2)
    distributed_optimizer = CortexDistributedOptimizer(n_gpus=2, base_learning_rate=0.001)

    # Test gauge transforms
    print("Testing gauge transforms:")
    gradients = np.random.randn(10, 10) * 0.1
    print(f"  Original gradient norm: {np.linalg.norm(gradients):.6f}")

    for i in range(3):
        transformed = gauge_training.apply_gauge_transform(gradients, i)
        print(f"  Transform {i} norm: {np.linalg.norm(transformed):.6f}")

    # Test gradient synchronization
    print("\nTesting gradient synchronization:")
    local_gradients = [np.random.randn(10, 10) * 0.1 for _ in range(2)]
    synchronized = gauge_training.synchronize_gradients(local_gradients)
    print(f"  Synchronized gradient norm: {np.linalg.norm(synchronized):.6f}")

    # Test gauge metrics
    print("\nTesting gauge metrics:")
    metrics = gauge_training.get_gauge_metrics(gradients)
    print(f"  Gauge invariant: {metrics['gauge_invariant']}")
    print(f"  Gradient norm: {metrics['gradient_norm']:.6f}")
    if metrics["gauge_invariant"]:
        print(f"  Gauge norm mean: {metrics['gauge_norm_mean']:.6f}")
        print(f"  Gauge norm std: {metrics['gauge_norm_std']:.6f}")
        print(f"  Gauge variance: {metrics['gauge_variance']:.6f}")

    # Test distributed optimization
    print("\nTesting distributed optimization:")
    parameters = [np.random.randn(10, 10) for _ in range(2)]

    for epoch in range(5):
        local_grads = [np.random.randn(10, 10) * 0.01 for _ in range(2)]
        result = distributed_optimizer.distributed_step(local_grads, parameters, epoch)
        parameters = result["updated_parameters"]
        metrics = result["gauge_metrics"]
        print(
            f"  Epoch {epoch}: Gradient norm = {metrics['gradient_norm']:.6f}, "
            f"Gauge variance = {metrics.get('gauge_variance', 0):.6f}"
        )

    # Get synchronization summary
    print("\nSynchronization Summary:")
    summary = distributed_optimizer.get_synchronization_summary()
    print(f"  Total steps: {summary['total_steps']}")
    print(f"  Average gradient norm: {summary['avg_gradient_norm']:.6f}")
    print(f"  Final gradient norm: {summary['final_gradient_norm']:.6f}")
    print(f"  Convergence stability: {summary['convergence_stability']:.4f}")

    print("\n=== Test Complete ===\n")

    return {"metrics": metrics, "synchronized": synchronized, "summary": summary}


if __name__ == "__main__":
    test_cortex_gauge_training()
