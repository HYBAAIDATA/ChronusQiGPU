"""
Neural-Combine memory index (2026 hybrid layer).

A small, real, trainable MLP that maps classical addresses to soft
routing weights over a bank of MPS memory slots or classical payloads.

Honesty constraints (matches Chronos audit doctrine):
  - Network is tiny (≤ 64 hidden units) and trained here on synthetic data.
  - No claim of 6 M-sample training, 100-qubit nets, or external datasets.
  - The neural layer is an *index / router*, not a replacement for the
    mathematical QRAM or MPS store.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from .table import Table
from .mps_store import MPSStore


class TinyRouter:
    """Minimal 2-layer MLP: address features → soft slot weights."""

    def __init__(self, n_in: int, n_hidden: int, n_out: int, seed: int = 0):
        rng = np.random.default_rng(seed)
        self.W1 = rng.normal(0, 0.4, size=(n_in, n_hidden))
        self.b1 = np.zeros(n_hidden)
        self.W2 = rng.normal(0, 0.4, size=(n_hidden, n_out))
        self.b2 = np.zeros(n_out)

    def forward(self, x: np.ndarray) -> np.ndarray:
        h = np.tanh(x @ self.W1 + self.b1)
        logits = h @ self.W2 + self.b2
        # Softmax
        e = np.exp(logits - logits.max(axis=-1, keepdims=True))
        return e / e.sum(axis=-1, keepdims=True)

    def train_step(self, x: np.ndarray, target: np.ndarray, lr: float = 0.05) -> float:
        """Cross-entropy style gradient on soft targets (real backprop)."""
        h = np.tanh(x @ self.W1 + self.b1)
        logits = h @ self.W2 + self.b2
        e = np.exp(logits - logits.max(axis=-1, keepdims=True))
        p = e / e.sum(axis=-1, keepdims=True)
        loss = float(-np.mean(np.sum(target * np.log(p + 1e-12), axis=-1)))
        grad_logits = (p - target) / x.shape[0]
        grad_W2 = h.T @ grad_logits
        grad_b2 = grad_logits.sum(axis=0)
        grad_h = grad_logits @ self.W2.T * (1 - h**2)
        grad_W1 = x.T @ grad_h
        grad_b1 = grad_h.sum(axis=0)
        self.W1 -= lr * grad_W1
        self.b1 -= lr * grad_b1
        self.W2 -= lr * grad_W2
        self.b2 -= lr * grad_b2
        return loss


@dataclass
class NeuralIndexReport:
    loss_curve: List[float]
    final_loss: float
    n_slots: int
    n_hidden: int
    accuracy_top1: float


class NeuralCombineMemory:
    """
    Hybrid memory: classical Table payloads + neural soft router + optional
    MPS slot bank.

    Address → neural router → weighted combination of slot payloads.
    """

    def __init__(
        self,
        n_slots: int = 8,
        address_bits: int = 6,
        value_bits: int = 8,
        n_hidden: int = 32,
        seed: int = 0,
        use_mps_slots: bool = False,
        mps_qubits_per_slot: int = 4,
        mps_bond_dim: int = 8,
    ):
        self.n_slots = n_slots
        self.address_bits = address_bits
        self.value_bits = value_bits
        self.router = TinyRouter(
            n_in=address_bits,
            n_hidden=n_hidden,
            n_out=n_slots,
            seed=seed,
        )
        # Classical payload table per slot
        self.slot_tables: List[Table] = [
            Table.from_integers(
                [0] * (1 << min(address_bits, 8)),
                domain_bits=min(address_bits, 8),
                value_bits=value_bits,
            )
            for _ in range(n_slots)
        ]
        self.use_mps = use_mps_slots
        self.mps_slots: List[Optional[MPSStore]] = [
            MPSStore(n_qubits=mps_qubits_per_slot, bond_dim=mps_bond_dim)
            if use_mps_slots
            else None
            for _ in range(n_slots)
        ]
        self._train_report: Optional[NeuralIndexReport] = None

    def _address_features(self, address: int) -> np.ndarray:
        bits = np.array(
            [(address >> i) & 1 for i in range(self.address_bits)],
            dtype=float,
        )
        return bits

    def route(self, address: int) -> np.ndarray:
        x = self._address_features(address).reshape(1, -1)
        return self.router.forward(x)[0]

    def read(self, address: int) -> Tuple[float, np.ndarray]:
        """Soft-weighted read: returns (expected payload float, routing weights)."""
        weights = self.route(address)
        total = 0.0
        for s, w in enumerate(weights):
            total += w * self.slot_tables[s].lookup_int(address % self.slot_tables[s].n_entries())
        return total, weights

    def write(self, address: int, value: int, slot: Optional[int] = None) -> None:
        if slot is None:
            weights = self.route(address)
            slot = int(np.argmax(weights))
        self.slot_tables[slot].set(address % self.slot_tables[slot].n_entries(), value)

    def train_router(
        self,
        n_samples: int = 256,
        epochs: int = 80,
        seed: int = 0,
    ) -> NeuralIndexReport:
        """
        Train the router on a synthetic address→preferred-slot mapping
        (modular assignment). Real backprop, measured loss curve.
        """
        if n_samples <= 0:
            raise ValueError("n_samples must be positive")
        rng = np.random.default_rng(seed)
        loss_curve = []
        for _ in range(epochs):
            addrs = rng.integers(0, 1 << self.address_bits, size=n_samples)
            x = np.stack([self._address_features(a) for a in addrs])
            # Target: one-hot preferred slot = address % n_slots
            target = np.zeros((n_samples, self.n_slots))
            for i, a in enumerate(addrs):
                target[i, a % self.n_slots] = 1.0
            loss = self.router.train_step(x, target, lr=0.08)
            loss_curve.append(loss)

        # Top-1 accuracy on a fresh batch
        test_addrs = rng.integers(0, 1 << self.address_bits, size=n_samples)
        correct = 0
        for a in test_addrs:
            w = self.route(a)
            if int(np.argmax(w)) == a % self.n_slots:
                correct += 1
        acc = correct / len(test_addrs)
        report = NeuralIndexReport(
            loss_curve=loss_curve,
            final_loss=loss_curve[-1] if loss_curve else float("inf"),
            n_slots=self.n_slots,
            n_hidden=self.router.W1.shape[1],
            accuracy_top1=acc,
        )
        self._train_report = report
        return report


def _self_test() -> str:
    mem = NeuralCombineMemory(n_slots=4, address_bits=4, value_bits=4, n_hidden=16, seed=1)
    report = mem.train_router(epochs=60, seed=1)
    assert report.final_loss < report.loss_curve[0], "loss must decrease"
    assert report.accuracy_top1 >= 0.5, f"router accuracy too low: {report.accuracy_top1}"
    mem.write(3, 7)
    val, weights = mem.read(3)
    assert weights.shape == (4,)
    assert abs(weights.sum() - 1.0) < 1e-6
    return "memory.neural_combine._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
