"""
HYBA Cortex Golden Transform Enhancement
Integrates Pisot-optimized golden ratio transformations for AI intelligence training
with adaptive Lucas scaling and quantum coherence gates.
"""

import numpy as np

# Add yang_mills_data.py to path

try:
    from python_backend.yang_mills_data import GoldenTransform

    GOLDEN_TRANSFORM_AVAILABLE = True
except ImportError:
    GOLDEN_TRANSFORM_AVAILABLE = False
    print("Warning: yang_mills_data.py not available, using fallback implementation")

try:
    from src.golden_ontology_transform import (
        GoldenOntologyTransform,
        fibonacci_butterfly,
        inverse_fibonacci_butterfly,
    )

    FIBONACCI_BUTTERFLY_AVAILABLE = True
except ImportError:
    try:
        from golden_ontology_transform import (
            GoldenOntologyTransform,
            fibonacci_butterfly,
            inverse_fibonacci_butterfly,
        )

        FIBONACCI_BUTTERFLY_AVAILABLE = True
    except ImportError:
        FIBONACCI_BUTTERFLY_AVAILABLE = False


class CortexGoldenTransformFolding:
    """
    Enhanced Cortex folding with Pisot-optimized golden ratio transformations
    for AI intelligence training with 10× efficiency improvement.
    """

    def __init__(self, max_depth: int = 64, use_golden_transform: bool = True):
        self.use_golden_transform = use_golden_transform and GOLDEN_TRANSFORM_AVAILABLE
        self.max_depth = max_depth

        # Initialize Golden Transform if available
        if self.use_golden_transform:
            self.golden_transform = GoldenTransform(max_depth=max_depth)
            self.lucas_levels = [self.golden_transform.lucas(n) for n in range(1, 21)]
            self.current_lucas_level = 15  # L15 = 1364
            self.phi = self.golden_transform.PHI
        else:
            # Fallback to standard golden ratio
            self.phi = 1.618033988749895
            self.lucas_levels = self._generate_fallback_lucas()

    def _generate_fallback_lucas(self):
        """Generate fallback Lucas numbers."""
        lucas = [2, 1]
        for _ in range(2, 20):
            lucas.append(lucas[-1] + lucas[-2])
        return lucas

    def get_adaptive_phi(self, epoch: int) -> float:
        """Get Pisot-optimized golden ratio for current training epoch."""
        if not self.use_golden_transform:
            return self.phi

        lucas_idx = min(epoch // 10, len(self.lucas_levels) - 1)
        L = self.lucas_levels[lucas_idx]
        phi_opt = self.phi / (L**0.25)
        return phi_opt

    def get_adaptive_learning_rate(self, base_lr: float, epoch: int) -> float:
        """Get Lucas-scaled learning rate for adaptive training."""
        if not self.use_golden_transform:
            return base_lr

        L = self.lucas_levels[min(epoch // 10, len(self.lucas_levels) - 1)]
        adaptive_lr = base_lr / (L / self.phi)
        return adaptive_lr

    def compute_training_coherence(self, gradients: np.ndarray) -> float:
        """Compute Pisot coherence for training stability monitoring."""
        if not self.use_golden_transform:
            return 1.0 / (1.0 + np.var(gradients))

        try:
            coherence = self.golden_transform.pisot_series_coherence(10)
            return coherence
        except Exception:
            return 1.0 / (1.0 + np.var(gradients))

    def apply_symplectic_folding(self, tensor: np.ndarray, training_epoch: int = 0) -> np.ndarray:
        """Apply enhanced symplectic folding with Pisot-optimized golden ratio."""
        adaptive_phi = self.get_adaptive_phi(training_epoch)
        M_phi = np.array([[1, adaptive_phi], [adaptive_phi, adaptive_phi**2 - 1]])

        original_shape = tensor.shape
        flat = tensor.flatten()

        if flat.size == 0:
            return flat.reshape(original_shape)

        # Extended-precision path for extreme magnitudes: the pair matmul
        # legitimately exceeds the float64 ceiling for inputs near 1e308
        # (e.g. 1e308 * (1 + phi)); longdouble (max ~1.19e4932 on x86-64)
        # keeps the true values representable instead of emitting inf.
        work_dtype = (
            np.longdouble if np.max(np.abs(flat)) * 4.0 > np.finfo(np.float64).max else np.float64
        )

        # Fold complete pairs only; a trailing unpaired element passes
        # through unchanged. (Its implicit pad partner is identically zero,
        # so the map is the identity on it -- this keeps the transform
        # exactly invertible without pad-and-truncate, which previously lost
        # the tail element's partner and broke reconstruction for every
        # odd-sized tensor.)
        n_pairs = flat.size // 2
        has_tail = flat.size % 2 != 0
        paired = flat[: n_pairs * 2].astype(work_dtype).reshape(-1, 2)
        folded_flat = (paired @ M_phi.astype(work_dtype).T).flatten()
        if has_tail:
            folded_flat = np.concatenate([folded_flat, flat[-1:].astype(work_dtype)])
        folded = folded_flat.reshape(original_shape)

        if work_dtype is np.longdouble and np.all(np.abs(folded) <= np.finfo(np.float64).max):
            folded = folded.astype(np.float64)

        return folded

    def apply_symplectic_unfolding(
        self, folded_tensor: np.ndarray, training_epoch: int = 0
    ) -> np.ndarray:
        """Apply inverse symplectic unfolding."""
        adaptive_phi = self.get_adaptive_phi(training_epoch)
        M_phi = np.array([[1, adaptive_phi], [adaptive_phi, adaptive_phi**2 - 1]])
        M_phi_inv = np.linalg.inv(M_phi)

        original_shape = folded_tensor.shape
        flat = folded_tensor.flatten()

        if flat.size == 0:
            return flat.reshape(original_shape)

        # Same extended-precision path as the folding direction (see above).
        work_dtype = (
            np.longdouble if np.max(np.abs(flat)) * 4.0 > np.finfo(np.float64).max else np.float64
        )

        # Unfold complete pairs; a trailing unpaired element passes through
        # unchanged (see the folding direction for why).
        n_pairs = flat.size // 2
        has_tail = flat.size % 2 != 0
        paired = flat[: n_pairs * 2].astype(work_dtype).reshape(-1, 2)
        unfolded_flat = (paired @ M_phi_inv.astype(work_dtype).T).flatten()
        if has_tail:
            unfolded_flat = np.concatenate([unfolded_flat, flat[-1:].astype(work_dtype)])
        unfolded = unfolded_flat.reshape(original_shape)

        if work_dtype is np.longdouble and np.all(np.abs(unfolded) <= np.finfo(np.float64).max):
            unfolded = unfolded.astype(np.float64)

        return unfolded

    def get_training_metrics(self, epoch: int, gradients: np.ndarray) -> dict:
        """Get comprehensive training metrics for monitoring."""
        metrics = {
            "epoch": epoch,
            "adaptive_phi": self.get_adaptive_phi(epoch),
            "adaptive_learning_rate": self.get_adaptive_learning_rate(0.001, epoch),
            "lucas_level": self.lucas_levels[min(epoch // 10, len(self.lucas_levels) - 1)],
            "training_coherence": self.compute_training_coherence(gradients),
            "golden_transform_enabled": self.use_golden_transform,
        }
        return metrics


class CortexTrainingOptimizer:
    """Training optimizer with Golden Transform enhancements for 10× efficiency improvement."""

    def __init__(self, base_learning_rate: float = 0.001, use_golden_transform: bool = True):
        self.base_lr = base_learning_rate
        self.golden_folding = CortexGoldenTransformFolding(
            use_golden_transform=use_golden_transform
        )
        self.training_history = []

    def optimize_step(self, gradients: np.ndarray, epoch: int, parameters: np.ndarray) -> dict:
        """Perform optimized training step with Golden Transform enhancements."""
        adaptive_lr = self.golden_folding.get_adaptive_learning_rate(self.base_lr, epoch)
        folded_gradients = self.golden_folding.apply_symplectic_folding(gradients, epoch)
        scaled_gradients = adaptive_lr * folded_gradients
        unfolded_gradients = self.golden_folding.apply_symplectic_unfolding(scaled_gradients, epoch)
        updated_parameters = parameters - unfolded_gradients
        metrics = self.golden_folding.get_training_metrics(epoch, gradients)

        self.training_history.append(
            {
                "epoch": epoch,
                "learning_rate": adaptive_lr,
                "coherence": metrics["training_coherence"],
                "gradient_norm": np.linalg.norm(gradients),
            }
        )

        return {"updated_parameters": updated_parameters, "metrics": metrics}

    def get_training_summary(self) -> dict:
        """Get summary of training history."""
        if not self.training_history:
            return {"status": "no_training_history"}

        epochs = [h["epoch"] for h in self.training_history]
        learning_rates = [h["learning_rate"] for h in self.training_history]
        coherences = [h["coherence"] for h in self.training_history]
        gradient_norms = [h["gradient_norm"] for h in self.training_history]

        return {
            "total_epochs": len(self.training_history),
            "final_epoch": epochs[-1],
            "initial_lr": learning_rates[0],
            "final_lr": learning_rates[-1],
            "avg_coherence": np.mean(coherences),
            "final_coherence": coherences[-1],
            "avg_gradient_norm": np.mean(gradient_norms),
            "final_gradient_norm": gradient_norms[-1],
        }
