"""Quantum state visualization utilities.

Works without a GUI backend. If matplotlib is available, saves PNG plots;
otherwise emits ASCII bar charts and Bloch-vector summaries. Every function
is pure and deterministic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass
class BlochSummary:
    x: float
    y: float
    z: float

    @property
    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)


def ascii_amplitude_bar(state: np.ndarray, width: int = 40) -> str:
    """Return an ASCII bar chart of |amplitude|^2 for a state vector."""
    probs = np.abs(state) ** 2
    if probs.size == 0:
        return "(empty state)"
    m = float(probs.max()) or 1.0
    lines: List[str] = []
    for i, p in enumerate(probs):
        bar_len = int(round((float(p) / m) * width))
        lines.append(f"|{i:03d}> {'#' * bar_len}{'.' * (width - bar_len)} {float(p):.4f}")
    return "\n".join(lines)


class StateVisualizer:
    """Compute visual/statistical summaries of a state or density matrix."""

    @staticmethod
    def bloch_vector(state: np.ndarray) -> BlochSummary:
        """Compute the Bloch vector for a 2-dim state (or leading 2 dims)."""
        if state.shape[-1] < 2:
            raise ValueError("State must be at least 2-dim for Bloch view")
        a = complex(state[0])
        b = complex(state[1])
        n = math.sqrt(abs(a) ** 2 + abs(b) ** 2) or 1.0
        a, b = a / n, b / n
        x = 2.0 * (a.conjugate() * b).real
        y = 2.0 * (a.conjugate() * b).imag
        z = float(abs(a) ** 2 - abs(b) ** 2)
        return BlochSummary(x=x, y=y, z=z)

    @staticmethod
    def probability_distribution(state: np.ndarray) -> np.ndarray:
        return np.abs(state) ** 2

    @staticmethod
    def entanglement_entropy(rho: np.ndarray, tol: float = 1e-12) -> float:
        """Von Neumann entropy S(rho) = -Tr(rho log rho), natural log."""
        w = np.linalg.eigvalsh(rho)
        w = np.clip(w.real, 0.0, None)
        w = w[w > tol]
        if w.size == 0:
            return 0.0
        return float(-np.sum(w * np.log(w)))

    def try_save_png(self, state: np.ndarray, path: str) -> Optional[str]:
        """Best-effort PNG save; returns path if written, else None."""
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            probs = self.probability_distribution(state)
            fig, ax = plt.subplots(figsize=(6, 3))
            ax.bar(range(len(probs)), probs)
            ax.set_xlabel("basis index")
            ax.set_ylabel("|amplitude|^2")
            fig.tight_layout()
            fig.savefig(path, dpi=120)
            plt.close(fig)
            return path
        except Exception:
            return None
