"""Bounded phi-VQC nonce ranking integrated with Turing.

The July 2026 VQC artifact is retained as a trainable 32-face ranking model,
but its production contract is tightened: it may only score/reorder candidate
nonces supplied by the canonical miner. It cannot synthesize nonces, alter a
Bitcoin header, change a target, validate proof, submit a share, or interpret a
pool response.

The exact Clifford skeleton is a capability demonstration. It does not enter
the ranking forward path. The ranker is a classical NumPy MLP. This module
is labelled accordingly so that the skeleton cannot be read as load-bearing
for inference.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Any, Callable, Iterable, Optional, Sequence

import numpy as np

from .phi_quantum_machine import PhiQuantumCircuit, PhiQuantumMachine

PHI = (1.0 + math.sqrt(5.0)) / 2.0


@dataclass(frozen=True)
class VQCConfig:
    num_layers: int = 4
    learning_rate: float = 0.025
    graph_coupling: float = 0.25
    fisher_regularization: float = 1e-4
    gradient_clip: float = 5.0
    batch_size: int = 16
    seed: int = 20260724

    def __post_init__(self) -> None:
        if self.num_layers < 1:
            raise ValueError("num_layers must be positive")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        if self.batch_size < 1:
            raise ValueError("batch_size must be positive")


class PhiGroverVQC:
    """Trainable 32-face candidate ranker with an exact Clifford skeleton."""

    execution_type = "classical_trainable_ranker_with_exact_clifford_skeleton_capability_demonstration_only"
    authority = "candidate-order-only"

    def __init__(
        self,
        config: Optional[VQCConfig] = None,
        adjacency: Optional[np.ndarray] = None,
        feature_hook: Optional[Callable[[dict[str, Any]], np.ndarray]] = None,
    ) -> None:
        self.config = config or VQCConfig()
        self.rng = np.random.default_rng(self.config.seed)
        self.adjacency = self._validate_adjacency(
            adjacency if adjacency is not None else self._public_phi_adjacency()
        )
        degree = np.maximum(self.adjacency.sum(axis=1, keepdims=True), 1.0)
        self.graph = self.adjacency / degree
        self.feature_hook = feature_hook
        scale = 1.0 / math.sqrt(32.0)
        self.theta = self.rng.normal(0.0, scale, size=(self.config.num_layers, 32, 3)) / PHI
        self.best_theta = self.theta.copy()
        self.best_loss = float("inf")
        self.loss_history: list[float] = []
        self.accuracy_history: list[float] = []

    @staticmethod
    def _public_phi_adjacency() -> np.ndarray:
        adjacency = np.zeros((32, 32), dtype=np.float64)
        for i in range(32):
            for offset in (1, 2, 3, 5, 8, 13):
                j = (i + offset) % 32
                adjacency[i, j] = adjacency[j, i] = 1.0
        np.fill_diagonal(adjacency, 0.0)
        return adjacency

    @staticmethod
    def _validate_adjacency(adjacency: np.ndarray) -> np.ndarray:
        a = np.asarray(adjacency, dtype=np.float64)
        if a.shape != (32, 32) or not np.all(np.isfinite(a)):
            raise ValueError("M32 adjacency must be a finite 32x32 matrix")
        if np.any(a < 0) or not np.allclose(a, a.T, atol=1e-12):
            raise ValueError("M32 adjacency must be symmetric and non-negative")
        if not np.allclose(np.diag(a), 0.0):
            raise ValueError("M32 adjacency diagonal must be zero")
        return a.copy()

    @staticmethod
    def _canonical_header_bytes(header: dict[str, Any]) -> bytes:
        parts = []
        for key in sorted(header):
            if key == "nonce":
                continue
            value = header[key]
            encoded = bytes(value).hex() if isinstance(value, (bytes, bytearray)) else str(value)
            parts.append(f"{key}={encoded}")
        return "|".join(parts).encode("utf-8")

    def extract_features(self, header: dict[str, Any]) -> np.ndarray:
        if self.feature_hook is not None:
            features = np.asarray(self.feature_hook(header), dtype=np.float64)
            if features.shape != (32,) or not np.all(np.isfinite(features)):
                raise ValueError("feature_hook must return 32 finite values")
            return features
        digest = hashlib.sha512(self._canonical_header_bytes(header)).digest()
        return np.frombuffer(digest, dtype=">u2").astype(np.float64)[:32]

    def encode_input(self, header: dict[str, Any]) -> np.ndarray:
        f = self.extract_features(header)
        centred = (f / 65535.0) * (2.0 * math.pi) - math.pi
        powers = PHI ** (np.arange(32) % 8)
        encoded = np.sin(centred * powers) + np.cos(centred / powers)
        norm = max(float(np.linalg.norm(encoded)), 1e-15)
        return encoded / norm * math.sqrt(32.0)

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        x = np.clip(x, -40.0, 40.0)
        return 1.0 / (1.0 + np.exp(-x))

    def _forward_with_cache(self, encoded: np.ndarray, theta: Optional[np.ndarray] = None):
        theta = self.theta if theta is None else theta
        h = np.asarray(encoded, dtype=np.float64).copy()
        cache = []
        for layer in range(self.config.num_layers):
            mix = self.graph @ h
            coupling = np.tanh(theta[layer, :, 2]) * self.config.graph_coupling
            pre = h + theta[layer, :, 0] + coupling * mix
            rotated = np.tanh(pre)
            out = rotated + theta[layer, :, 1]
            cache.append((mix, coupling, rotated))
            h = out
        return self._sigmoid(h), cache

    def bit_probabilities(self, header: dict[str, Any], *, use_best: bool = True) -> np.ndarray:
        theta = self.best_theta if use_best and math.isfinite(self.best_loss) else self.theta
        probabilities, _ = self._forward_with_cache(self.encode_input(header), theta)
        return probabilities

    @staticmethod
    def nonce_to_bits(nonce: int) -> np.ndarray:
        if not isinstance(nonce, (int, np.integer)) or not 0 <= int(nonce) <= 0xFFFFFFFF:
            raise ValueError("nonce must be a uint32 integer")
        value = np.uint32(int(nonce))
        return ((value >> np.arange(32, dtype=np.uint32)) & 1).astype(np.float64)

    @staticmethod
    def binary_cross_entropy(probs: np.ndarray, targets: np.ndarray) -> float:
        p = np.clip(probs, 1e-9, 1.0 - 1e-9)
        y = np.asarray(targets, dtype=np.float64)
        return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))

    def _loss_and_gradient(self, headers: list[dict[str, Any]], nonces: list[int]):
        total_loss = 0.0
        total_grad = np.zeros_like(self.theta)
        bit_accuracy = 0.0
        for header, nonce in zip(headers, nonces):
            encoded = self.encode_input(header)
            probs, cache = self._forward_with_cache(encoded)
            target = self.nonce_to_bits(nonce)
            total_loss += self.binary_cross_entropy(probs, target)
            bit_accuracy += float(np.mean((probs >= 0.5) == target.astype(bool)))
            delta = (probs - target) / 32.0
            for layer in range(self.config.num_layers - 1, -1, -1):
                mix, coupling, rotated = cache[layer]
                total_grad[layer, :, 1] += delta
                dpre = delta * (1.0 - rotated * rotated)
                total_grad[layer, :, 0] += dpre
                tanh_control = np.tanh(self.theta[layer, :, 2])
                total_grad[layer, :, 2] += (
                    dpre * mix * self.config.graph_coupling * (1.0 - tanh_control * tanh_control)
                )
                delta = dpre + self.graph.T @ (dpre * coupling)
        count = max(len(headers), 1)
        total_grad /= count
        fisher = total_grad * total_grad + self.config.fisher_regularization
        natural_grad = total_grad / np.sqrt(fisher)
        norm = float(np.linalg.norm(natural_grad))
        if norm > self.config.gradient_clip:
            natural_grad *= self.config.gradient_clip / norm
        return total_loss / count, natural_grad, bit_accuracy / count

    def train(self, training_data: Iterable[dict[str, Any]], epochs: int = 20) -> dict[str, Any]:
        data = list(training_data)
        if not data:
            raise ValueError("training_data cannot be empty")
        for item in data:
            if "header" not in item or "nonce" not in item:
                raise ValueError("each training example requires header and nonce")
            self.nonce_to_bits(int(item["nonce"]))
        for _ in range(int(epochs)):
            order = self.rng.permutation(len(data))
            losses: list[float] = []
            accuracies: list[float] = []
            for start in range(0, len(data), self.config.batch_size):
                batch = [data[int(i)] for i in order[start:start + self.config.batch_size]]
                headers = [dict(item["header"]) for item in batch]
                nonces = [int(item["nonce"]) for item in batch]
                loss, grad, accuracy = self._loss_and_gradient(headers, nonces)
                self.theta -= self.config.learning_rate * grad
                losses.append(loss)
                accuracies.append(accuracy)
            epoch_loss = float(np.mean(losses))
            epoch_accuracy = float(np.mean(accuracies))
            self.loss_history.append(epoch_loss)
            self.accuracy_history.append(epoch_accuracy)
            if epoch_loss < self.best_loss:
                self.best_loss = epoch_loss
                self.best_theta = self.theta.copy()
        return {
            "epochs": int(epochs),
            "best_loss": self.best_loss,
            "final_loss": self.loss_history[-1],
            "final_bit_accuracy": self.accuracy_history[-1],
            "execution_type": self.execution_type,
            "authority": self.authority,
        }

    def score_candidate(self, header: dict[str, Any], nonce: int) -> float:
        probs = np.clip(self.bit_probabilities(header), 1e-12, 1.0 - 1e-12)
        bits = self.nonce_to_bits(nonce).astype(bool)
        return float(np.where(bits, np.log(probs), np.log(1.0 - probs)).sum())

    def rank_candidates(self, header: dict[str, Any], candidates: Sequence[int]) -> dict[str, Any]:
        """Reorder an existing candidate set without adding/removing nonces."""
        if not candidates:
            raise ValueError("candidates cannot be empty")
        validated = []
        for nonce in candidates:
            if not isinstance(nonce, (int, np.integer)) or not 0 <= int(nonce) <= 0xFFFFFFFF:
                raise ValueError("all candidates must be uint32 integers")
            validated.append(int(nonce))
        if len(set(validated)) != len(validated):
            raise ValueError("candidate set contains duplicates")
        scored = [(nonce, self.score_candidate(header, nonce)) for nonce in validated]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        ranked = [nonce for nonce, _ in scored]
        if set(ranked) != set(validated) or len(ranked) != len(validated):
            raise RuntimeError("ranker violated candidate-preservation invariant")
        return {
            "candidates": ranked,
            "scores": [score for _, score in scored],
            "candidate_count": len(ranked),
            "candidate_set_preserved": True,
            "execution_type": self.execution_type,
            "authority": self.authority,
            "proof_authority": False,
        }

    def quantum_skeleton(self) -> PhiQuantumCircuit:
        circuit = PhiQuantumCircuit(32)
        for q in range(32):
            circuit.h(q)
        edges = np.argwhere(np.triu(self.adjacency > 0, k=1))
        for control, target in edges:
            circuit.cx(int(control), int(target))
        return circuit

    def verify_quantum_skeleton(self) -> dict[str, Any]:
        machine = PhiQuantumMachine(32, fold_depth=8)
        result = machine.execute(self.quantum_skeleton(), shots=1, seed=self.config.seed)
        checkpoint = machine.checkpoint(depth=8)
        before = machine.state_digest()
        machine.register.x(0)
        machine.restore(checkpoint)
        return {
            "logical_qubits": 32,
            "gates_executed": result.gates_executed,
            "state_digest": result.state_digest,
            "checkpoint_depth": checkpoint.depth,
            "checkpoint_restore_verified": machine.state_digest() == before,
            "truth_class": result.truth_class,
            "execution_type": self.execution_type,
        }


__all__ = ["PHI", "PhiGroverVQC", "VQCConfig"]
