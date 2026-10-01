"""
Particle-physics application kernel — LHC-style event classification
using the φ-resonance substrate.

Implements a lightweight signal/background classifier that consumes an
(events × features) matrix (as produced by e.g. the ATLAS/CMS opendata
Higgs → ττ challenge) and returns per-event probabilities. Uses a
quantum-mathematical kernel method (feature map + kernel matrix).

Claim lane: MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC). Reference implementation only.
"""

import numpy as np
from typing import Dict

from ..quantum_kernel import QuantumKernelProcessor


class LHCEventClassifier:
    """Signal/background classifier for LHC-style events."""

    def __init__(self, num_features: int = 4):
        self.num_features = num_features
        self.kernel = QuantumKernelProcessor(num_qubits=num_features)
        self.trained = False
        self.support_vectors = None
        self.support_labels = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> Dict:
        """Fit against training events.

        Args:
            X: (n_events, num_features) real-valued feature matrix
            y: (n_events,) label vector in {-1, +1}
        """
        # Simple 1-nearest-support-vector classifier using quantum kernel
        self.support_vectors = X
        self.support_labels = y
        self.trained = True
        return {
            "num_events": len(X),
            "features": self.num_features,
            "signal_fraction": float(np.mean(y > 0)),
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict labels using quantum kernel similarity."""
        if not self.trained:
            raise RuntimeError("Classifier is not trained.")
        preds = []
        for x in X:
            # Compute kernel similarity to every support vector
            sims = np.array([
                self.kernel.compute_quantum_kernel(x, sv)
                for sv in self.support_vectors
            ])
            # Weighted majority vote
            score = np.sum(sims * self.support_labels)
            preds.append(1 if score > 0 else -1)
        return np.array(preds)

    def demo(self, n_events: int = 32, seed: int = 42) -> Dict:
        """Generate synthetic Higgs-like events, train, evaluate."""
        rng = np.random.default_rng(seed)
        # Signal centred at +1, background at -1 in each feature
        n_signal = n_events // 2
        n_bkg = n_events - n_signal
        X_signal = rng.normal(loc=+0.5, scale=0.3, size=(n_signal, self.num_features))
        X_bkg = rng.normal(loc=-0.5, scale=0.3, size=(n_bkg, self.num_features))
        X = np.vstack([X_signal, X_bkg])
        y = np.concatenate([np.ones(n_signal), -np.ones(n_bkg)])
        # Shuffle
        idx = rng.permutation(len(X))
        X, y = X[idx], y[idx]
        # Split
        n_train = int(0.75 * n_events)
        X_train, X_test = X[:n_train], X[n_train:]
        y_train, y_test = y[:n_train], y[n_train:]
        self.fit(X_train, y_train)
        preds = self.predict(X_test)
        acc = float(np.mean(preds == y_test))
        return {
            "n_train": n_train,
            "n_test": len(X_test),
            "accuracy": acc,
            "claim_lane": "RESTRICTED — synthetic data, reference kernel only",
        }
