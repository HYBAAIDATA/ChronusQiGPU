"""32-face MIDAS variational candidate ranker for Turing.

Recovered from the July 2026 VQC artifact and adapted to Turing's current truth
boundary. The model is a classical variational ranker with a Clifford circuit
skeleton. It may reorder nonce candidates, but it has no authority to declare
a Bitcoin share valid: SHA-256d against the target remains the only validator.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import struct
from typing import Any, Callable, Iterable

import numpy as np

from .phi_machine import PhiQuantumCircuit, PhiQuantumMachine1000

PHI = (1.0 + math.sqrt(5.0)) / 2.0


@dataclass
class VQCConfig:
    num_qubits: int = 32
    num_layers: int = 4
    num_features: int = 32
    learning_rate: float = 0.02
    batch_size: int = 32
    candidate_count: int = 4096
    graph_coupling: float = 0.15
    fisher_regularization: float = 1e-3
    gradient_clip: float = 5.0
    seed: int = 42

    def __post_init__(self) -> None:
        if self.num_qubits != 32 or self.num_features != 32:
            raise ValueError("MIDAS nonce VQC requires 32 qubits/features")
        if self.num_layers < 1 or self.learning_rate <= 0 or self.candidate_count < 1:
            raise ValueError("invalid VQC configuration")


def _parse_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, (int, np.integer)):
        return int(value)
    text = str(value).strip().lower()
    if not text:
        return default
    if text.startswith("0x"):
        return int(text, 16)
    if any(ch in "abcdef" for ch in text):
        return int(text, 16)
    return int(text, 10)


def _hash32_bytes(value: Any) -> bytes:
    text = str(value or "0" * 64).removeprefix("0x").zfill(64)[-64:]
    return bytes.fromhex(text)[::-1]


class MidasPhiVQCRanker:
    """Trainable 32-face candidate-ordering model with explicit boundaries."""

    execution_class = "classical_variational_ranker_with_clifford_skeleton"
    consensus_authority = False

    def __init__(self, config: VQCConfig | None = None,
                 adjacency: np.ndarray | None = None,
                 feature_hook: Callable[[dict[str, Any]], np.ndarray] | None = None) -> None:
        self.config = config or VQCConfig()
        self.rng = np.random.default_rng(self.config.seed)
        self.adjacency = self._validate_adjacency(
            adjacency if adjacency is not None else self._public_phi_adjacency())
        degree = np.maximum(self.adjacency.sum(axis=1, keepdims=True), 1.0)
        self.graph = self.adjacency / degree
        self.feature_hook = feature_hook
        scale = 1.0 / math.sqrt(32.0)
        self.theta = self.rng.normal(0.0, scale,
                                     size=(self.config.num_layers, 32, 3)) / PHI
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
            raise ValueError("M32 adjacency must be finite 32x32")
        if not np.allclose(a, a.T, atol=1e-12) or not np.allclose(np.diag(a), 0.0):
            raise ValueError("M32 adjacency must be symmetric with zero diagonal")
        if np.any(a < 0):
            raise ValueError("M32 weights must be non-negative")
        return a.copy()

    @staticmethod
    def serialize_header(header: dict[str, Any], nonce: int) -> bytes:
        if not isinstance(nonce, (int, np.integer)) or not 0 <= int(nonce) <= 0xFFFFFFFF:
            raise ValueError("nonce outside uint32")
        version = _parse_int(header.get("version", 0)) & 0xFFFFFFFF
        ntime = _parse_int(header.get("ntime", header.get("time", 0))) & 0xFFFFFFFF
        nbits = _parse_int(header.get("nbits", header.get("bits", 0))) & 0xFFFFFFFF
        return (
            struct.pack("<I", version)
            + _hash32_bytes(header.get("prev_hash"))
            + _hash32_bytes(header.get("merkle_root"))
            + struct.pack("<III", ntime, nbits, int(nonce))
        )

    def extract_features(self, header: dict[str, Any]) -> np.ndarray:
        if self.feature_hook is not None:
            features = np.asarray(self.feature_hook(header), dtype=np.float64)
            if features.shape != (32,) or not np.all(np.isfinite(features)):
                raise ValueError("feature_hook must return 32 finite values")
            return features
        digest = hashlib.sha512(self.serialize_header(header, 0)[:-4]).digest()
        return np.frombuffer(digest, dtype=">u2").astype(np.float64)[:32]

    def encode_input(self, header: dict[str, Any]) -> np.ndarray:
        f = self.extract_features(header)
        centred = (f / 65535.0) * (2 * math.pi) - math.pi
        powers = PHI ** (np.arange(32) % 8)
        encoded = np.sin(centred * powers) + np.cos(centred / powers)
        norm = max(float(np.linalg.norm(encoded)), 1e-15)
        return encoded / norm * math.sqrt(32.0)

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(x, -40.0, 40.0)))

    def _forward_with_cache(self, encoded: np.ndarray, theta: np.ndarray | None = None):
        theta = self.theta if theta is None else theta
        h = np.asarray(encoded, dtype=np.float64).copy()
        cache = []
        for layer in range(self.config.num_layers):
            mix = self.graph @ h
            coupling = np.tanh(theta[layer, :, 2]) * self.config.graph_coupling
            pre = h + theta[layer, :, 0] + coupling * mix
            rotated = np.tanh(pre)
            cache.append((mix, coupling, rotated))
            h = rotated + theta[layer, :, 1]
        return self._sigmoid(h), cache

    def bit_probabilities(self, header: dict[str, Any], use_best: bool = True) -> np.ndarray:
        theta = self.best_theta if use_best and np.isfinite(self.best_loss) else self.theta
        return self._forward_with_cache(self.encode_input(header), theta)[0]

    @staticmethod
    def nonce_to_bits(nonce: int) -> np.ndarray:
        if not isinstance(nonce, (int, np.integer)) or not 0 <= int(nonce) <= 0xFFFFFFFF:
            raise ValueError("nonce outside uint32")
        return ((np.uint32(nonce) >> np.arange(32, dtype=np.uint32)) & 1).astype(np.float64)

    @staticmethod
    def bits_to_nonces(bits: np.ndarray) -> np.ndarray:
        b = np.asarray(bits, dtype=np.uint64)
        weights = np.uint64(1) << np.arange(32, dtype=np.uint64)
        return (b @ weights).astype(np.uint64)

    @staticmethod
    def binary_cross_entropy(probs: np.ndarray, targets: np.ndarray) -> float:
        p = np.clip(probs, 1e-9, 1 - 1e-9)
        y = np.asarray(targets, dtype=np.float64)
        return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

    def _loss_and_gradient(self, headers: list[dict[str, Any]], nonces: list[int]):
        total_loss = 0.0
        total_grad = np.zeros_like(self.theta)
        correct = 0
        for header, nonce in zip(headers, nonces):
            probs, cache = self._forward_with_cache(self.encode_input(header))
            target = self.nonce_to_bits(nonce)
            total_loss += self.binary_cross_entropy(probs, target)
            correct += int(np.all((probs >= 0.5) == target.astype(bool)))
            delta = (probs - target) / 32.0
            for layer in range(self.config.num_layers - 1, -1, -1):
                mix, coupling, rotated = cache[layer]
                total_grad[layer, :, 1] += delta
                dpre = delta * (1.0 - rotated ** 2)
                total_grad[layer, :, 0] += dpre
                total_grad[layer, :, 2] += (
                    dpre * mix * self.config.graph_coupling
                    * (1.0 - np.tanh(self.theta[layer, :, 2]) ** 2)
                )
                delta = dpre + self.graph.T @ (dpre * coupling)
        count = max(len(headers), 1)
        total_grad /= count
        fisher = total_grad * total_grad + self.config.fisher_regularization
        natural_grad = total_grad / np.sqrt(fisher)
        norm = float(np.linalg.norm(natural_grad))
        if norm > self.config.gradient_clip:
            natural_grad *= self.config.gradient_clip / norm
        return total_loss / count, natural_grad, correct / count

    def train(self, training_data: Iterable[dict[str, Any]], epochs: int = 20,
              batch_size: int | None = None) -> dict[str, Any]:
        data = list(training_data)
        if not data:
            raise ValueError("training_data cannot be empty")
        batch_size = int(batch_size or self.config.batch_size)
        for _ in range(int(epochs)):
            order = self.rng.permutation(len(data))
            losses: list[float] = []
            accuracies: list[float] = []
            for start in range(0, len(data), batch_size):
                batch = [data[int(i)] for i in order[start:start + batch_size]]
                loss, grad, accuracy = self._loss_and_gradient(
                    [item["header"] for item in batch],
                    [int(item["nonce"]) for item in batch],
                )
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
            "epochs": int(epochs), "best_loss": self.best_loss,
            "final_loss": self.loss_history[-1],
            "final_accuracy": self.accuracy_history[-1],
            "execution_class": self.execution_class,
            "consensus_authority": False,
        }

    def rank_candidates(self, header: dict[str, Any], count: int | None = None,
                        seed: int | None = None) -> dict[str, Any]:
        count = int(count or self.config.candidate_count)
        if count < 1:
            raise ValueError("candidate count must be positive")
        probs = self.bit_probabilities(header)
        if seed is None:
            seed = int.from_bytes(hashlib.sha256(self.serialize_header(header, 0)).digest()[:8],
                                  "little")
        rng = np.random.default_rng(seed)
        bits = rng.random((count, 32)) < probs
        bits[0] = probs >= 0.5
        nonces = self.bits_to_nonces(bits)
        logp = bits * np.log(np.clip(probs, 1e-12, 1.0)) + (~bits) * np.log(
            np.clip(1 - probs, 1e-12, 1.0))
        scores = logp.sum(axis=1)
        order = np.argsort(scores)[::-1]
        ranked: list[tuple[int, float]] = []
        seen: set[int] = set()
        for idx in order:
            nonce = int(nonces[int(idx)])
            if nonce not in seen:
                seen.add(nonce)
                ranked.append((nonce, float(scores[int(idx)])))
        top = ranked[:count]
        normalizer = max(sum(math.exp(score - top[0][1]) for _, score in top), 1e-15)
        return {
            "nonce": top[0][0], "confidence": float(1.0 / normalizer),
            "candidates": [nonce for nonce, _ in top],
            "scores": [score for _, score in top],
            "execution_class": self.execution_class,
            "consensus_authority": False,
        }

    def clifford_skeleton(self) -> PhiQuantumCircuit:
        circuit = PhiQuantumCircuit(32)
        for q in range(32):
            circuit.h(q)
        edges = np.argwhere(np.triu(self.adjacency > 0, k=1))
        for control, target in edges:
            circuit.cx(int(control), int(target))
        return circuit

    def execute_clifford_skeleton(self) -> dict[str, Any]:
        machine = PhiQuantumMachine1000(32, fold_depth=8)
        result = machine.execute(self.clifford_skeleton())
        checkpoint = machine.checkpoint(8)
        return {
            "logical_qubits": 32, "gates": result.gates_executed,
            "state_digest": result.state_digest,
            "checkpoint_depth": checkpoint.depth,
            "truth_class": result.truth_class,
            "consensus_authority": False,
        }

    @staticmethod
    def nbits_to_target(nbits: Any) -> int:
        compact = _parse_int(nbits)
        exponent = compact >> 24
        mantissa = compact & 0x007FFFFF
        if compact & 0x00800000:
            raise ValueError("negative compact target")
        if exponent <= 3:
            return mantissa >> (8 * (3 - exponent))
        return mantissa << (8 * (exponent - 3))

    @classmethod
    def verify_nonce(cls, header: dict[str, Any], nonce: int) -> bool:
        raw = cls.serialize_header(header, nonce)
        digest = hashlib.sha256(hashlib.sha256(raw).digest()).digest()
        target = cls.nbits_to_target(header.get("nbits", header.get("bits", 0)))
        return int.from_bytes(digest, "little") <= target

    def order_existing_window(self, header: dict[str, Any],
                              candidates: Iterable[int]) -> list[int]:
        """Reorder a supplied window without adding, dropping, or mutating nonces."""
        window = list(candidates)
        if not window:
            return []
        for nonce in window:
            if not isinstance(nonce, (int, np.integer)) or not 0 <= int(nonce) <= 0xFFFFFFFF:
                raise ValueError("candidate window contains invalid nonce")
        probs = self.bit_probabilities(header)
        scored = []
        for position, nonce in enumerate(window):
            bits = self.nonce_to_bits(int(nonce)).astype(bool)
            score = float(np.sum(
                bits * np.log(np.clip(probs, 1e-12, 1.0))
                + (~bits) * np.log(np.clip(1 - probs, 1e-12, 1.0))))
            scored.append((score, position, int(nonce)))
        scored.sort(key=lambda item: (-item[0], item[1]))
        ordered = [nonce for _, _, nonce in scored]
        if sorted(ordered) != sorted(int(v) for v in window):
            raise RuntimeError("VQC ordering changed candidate membership")
        return ordered


__all__ = ["MidasPhiVQCRanker", "VQCConfig"]
