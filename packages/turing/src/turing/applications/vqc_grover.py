"""Variational φ-Grover nonce-ranking workload.

This module replaces the dense 2**32 pseudocode and no-op gates with a bounded,
trainable 32-face variational model, an exact SHA-256d nonce verifier, an
injectable private M_32 topology, and a Clifford skeleton executable on the
HYBA 1,000-logical-qubit machine.

The VQC ranks nonce candidates; validity is determined only by SHA-256d against
the compact target.  Fallback search is bounded and never reports success
without verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional
import hashlib
import math
import struct
import time
import numpy as np

from turing.applications.vqc_fold import PHI, ValidationError
from turing.applications.vqc_machine import PhiQuantumCircuit, PhiQuantumMachine1000


@dataclass
class VQCConfig:
    num_qubits: int = 32
    num_layers: int = 4
    num_features: int = 32
    learning_rate: float = 0.02
    batch_size: int = 32
    max_iterations: int = 1000
    candidate_count: int = 4096
    graph_coupling: float = 0.15
    fisher_regularization: float = 1e-3
    gradient_clip: float = 5.0
    seed: int = 42

    def __post_init__(self) -> None:
        if self.num_qubits != 32 or self.num_features != 32:
            raise ValidationError("nonce VQC requires 32 qubits and 32 features")
        if self.num_layers < 1 or self.learning_rate <= 0 or self.candidate_count < 1:
            raise ValidationError("invalid VQC configuration")


def _parse_int(value: Any, *, default: int = 0) -> int:
    if value is None: return default
    if isinstance(value, (int, np.integer)): return int(value)
    text = str(value).strip().lower()
    if not text: return default
    if text.startswith("0x"): return int(text, 16)
    if any(ch in "abcdef" for ch in text): return int(text, 16)
    return int(text, 10)


def _hash32_bytes(value: Any) -> bytes:
    text = str(value or "0" * 64).removeprefix("0x").zfill(64)[-64:]
    raw = bytes.fromhex(text)
    return raw[::-1]


class PhiGroverVQC:
    """Trainable 32-face variational nonce ranker."""

    def __init__(self, config: Optional[VQCConfig] = None,
                 adjacency: Optional[np.ndarray] = None,
                 feature_hook: Optional[Callable[[dict[str, Any]], np.ndarray]] = None):
        self.config = config or VQCConfig()
        self.rng = np.random.default_rng(self.config.seed)
        self.adjacency = self._validate_adjacency(adjacency if adjacency is not None else self._public_phi_adjacency())
        degree = np.maximum(self.adjacency.sum(axis=1, keepdims=True), 1.0)
        self.graph = self.adjacency / degree
        self.laplacian = np.diag(self.adjacency.sum(axis=1)) - self.adjacency
        self.feature_hook = feature_hook
        scale = 1.0 / math.sqrt(self.config.num_qubits)
        self.theta = self.rng.normal(0.0, scale, size=(self.config.num_layers, 32, 3)) / PHI
        self.best_theta = self.theta.copy()
        self.best_loss = float("inf")
        self.loss_history: list[float] = []
        self.accuracy_history: list[float] = []

    @staticmethod
    def _public_phi_adjacency() -> np.ndarray:
        adjacency = np.zeros((32, 32), dtype=np.float64)
        offsets = sorted({1, 2, 3, 5, 8, 13})
        for i in range(32):
            for offset in offsets:
                j = (i + offset) % 32
                adjacency[i, j] = adjacency[j, i] = 1.0
        np.fill_diagonal(adjacency, 0.0)
        return adjacency

    @staticmethod
    def _validate_adjacency(adjacency: np.ndarray) -> np.ndarray:
        a = np.asarray(adjacency, dtype=np.float64)
        if a.shape != (32, 32) or not np.all(np.isfinite(a)):
            raise ValidationError("M_32 adjacency must be finite 32x32")
        if not np.allclose(a, a.T, atol=1e-12) or not np.allclose(np.diag(a), 0.0):
            raise ValidationError("M_32 adjacency must be symmetric with zero diagonal")
        if np.any(a < 0): raise ValidationError("M_32 weights must be non-negative")
        return a.copy()

    def extract_features(self, header: dict[str, Any]) -> np.ndarray:
        if self.feature_hook is not None:
            features = np.asarray(self.feature_hook(header), dtype=np.float64)
            if features.shape != (32,) or not np.all(np.isfinite(features)):
                raise ValidationError("private feature hook must return 32 finite values")
            return features
        canonical = self.serialize_header(header, nonce=0)[:-4]
        digest = hashlib.sha512(canonical).digest()
        words = np.frombuffer(digest, dtype=">u2").astype(np.float64)[:32]
        return words

    def encode_input(self, header: dict[str, Any]) -> np.ndarray:
        f = self.extract_features(header)
        centred = (f / 65535.0) * (2 * math.pi) - math.pi
        powers = PHI ** (np.arange(32) % 8)
        encoded = np.sin(centred * powers) + np.cos(centred / powers)
        norm = max(float(np.linalg.norm(encoded)), 1e-15)
        return encoded / norm * math.sqrt(32)

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
            cache.append((h, mix, coupling, pre, rotated))
            h = out
        logits = h
        return self._sigmoid(logits), cache

    def bit_probabilities(self, header: dict[str, Any], *, use_best: bool = True) -> np.ndarray:
        theta = self.best_theta if use_best and np.isfinite(self.best_loss) else self.theta
        probs, _ = self._forward_with_cache(self.encode_input(header), theta)
        return probs

    @staticmethod
    def nonce_to_bits(nonce: int) -> np.ndarray:
        if nonce < 0 or nonce > 0xFFFFFFFF: raise ValidationError("nonce outside uint32")
        return ((np.uint32(nonce) >> np.arange(32, dtype=np.uint32)) & 1).astype(np.float64)

    @staticmethod
    def bits_to_nonces(bits: np.ndarray) -> np.ndarray:
        b = np.asarray(bits, dtype=np.uint64)
        weights = (np.uint64(1) << np.arange(32, dtype=np.uint64))
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
            encoded = self.encode_input(header)
            probs, cache = self._forward_with_cache(encoded)
            target = self.nonce_to_bits(int(nonce))
            total_loss += self.binary_cross_entropy(probs, target)
            correct += int(np.all((probs >= 0.5) == target.astype(bool)))
            delta = (probs - target) / 32.0
            for layer in range(self.config.num_layers - 1, -1, -1):
                h_prev, mix, coupling, pre, rotated = cache[layer]
                total_grad[layer, :, 1] += delta
                dpre = delta * (1.0 - rotated ** 2)
                total_grad[layer, :, 0] += dpre
                total_grad[layer, :, 2] += dpre * mix * self.config.graph_coupling * (1.0 - np.tanh(self.theta[layer, :, 2]) ** 2)
                delta = dpre + self.graph.T @ (dpre * coupling)
        count = max(len(headers), 1)
        total_grad /= count
        # Diagonal Fisher preconditioning: bounded quantum natural-gradient step.
        fisher = total_grad * total_grad + self.config.fisher_regularization
        natural_grad = total_grad / np.sqrt(fisher)
        norm = float(np.linalg.norm(natural_grad))
        if norm > self.config.gradient_clip:
            natural_grad *= self.config.gradient_clip / norm
        return total_loss / count, natural_grad, correct / count

    def train(self, training_data: Iterable[dict[str, Any]], epochs: int = 20,
              batch_size: Optional[int] = None) -> dict[str, Any]:
        data = list(training_data)
        if not data: raise ValidationError("training_data cannot be empty")
        batch_size = batch_size or self.config.batch_size
        for _ in range(int(epochs)):
            order = self.rng.permutation(len(data))
            losses = []; accuracies = []
            for start in range(0, len(data), batch_size):
                batch = [data[int(i)] for i in order[start:start + batch_size]]
                headers = [item["header"] for item in batch]
                nonces = [int(item["nonce"]) for item in batch]
                loss, grad, accuracy = self._loss_and_gradient(headers, nonces)
                self.theta -= self.config.learning_rate * grad
                losses.append(loss); accuracies.append(accuracy)
            epoch_loss = float(np.mean(losses)); epoch_accuracy = float(np.mean(accuracies))
            self.loss_history.append(epoch_loss); self.accuracy_history.append(epoch_accuracy)
            if epoch_loss < self.best_loss:
                self.best_loss = epoch_loss; self.best_theta = self.theta.copy()
        return {
            "epochs": int(epochs), "best_loss": self.best_loss,
            "final_loss": self.loss_history[-1],
            "final_accuracy": self.accuracy_history[-1],
            "loss_history": list(self.loss_history),
        }

    def rank_candidates(self, header: dict[str, Any], count: Optional[int] = None,
                        seed: Optional[int] = None) -> dict[str, Any]:
        count = int(count or self.config.candidate_count)
        probs = self.bit_probabilities(header)
        if seed is None:
            seed = int.from_bytes(hashlib.sha256(self.serialize_header(header, 0)).digest()[:8], "little")
        rng = np.random.default_rng(seed)
        bits = rng.random((count, 32)) < probs
        map_bits = probs >= 0.5
        bits[0] = map_bits
        nonces = self.bits_to_nonces(bits)
        logp = bits * np.log(np.clip(probs, 1e-12, 1)) + (~bits) * np.log(np.clip(1 - probs, 1e-12, 1))
        scores = logp.sum(axis=1)
        order = np.argsort(scores)[::-1]
        unique = []
        seen = set()
        for idx in order:
            nonce = int(nonces[idx])
            if nonce not in seen:
                seen.add(nonce); unique.append((nonce, float(scores[idx])))
        top = unique[:count]
        normalizer = max(sum(math.exp(s - top[0][1]) for _, s in top), 1e-15)
        return {
            "nonce": top[0][0],
            "confidence": float(1.0 / normalizer),
            "candidates": [n for n, _ in top],
            "scores": [s for _, s in top],
            "bit_probabilities": probs,
        }

    def quantum_skeleton(self) -> PhiQuantumCircuit:
        circuit = PhiQuantumCircuit(32)
        for q in range(32): circuit.h(q)
        edges = np.argwhere(np.triu(self.adjacency > 0, k=1))
        for control, target in edges: circuit.cx(int(control), int(target))
        return circuit

    def run_quantum_skeleton(self, shots: int = 64) -> dict[str, Any]:
        machine = PhiQuantumMachine1000(32, fold_depth=8)
        result = machine.execute(self.quantum_skeleton(), shots=shots, seed=self.config.seed)
        checkpoint = machine.checkpoint()
        return {
            "logical_qubits": 32,
            "gates": result.gates_executed,
            "shots": shots,
            "unique_outcomes": len(result.counts),
            "checkpoint_error": checkpoint.reconstruction_error,
            "digest": checkpoint.digest,
        }

    @staticmethod
    def serialize_header(header: dict[str, Any], nonce: int) -> bytes:
        version = _parse_int(header.get("version", 0)) & 0xFFFFFFFF
        ntime = _parse_int(header.get("ntime", header.get("time", 0))) & 0xFFFFFFFF
        nbits = _parse_int(header.get("nbits", header.get("bits", 0))) & 0xFFFFFFFF
        return (struct.pack("<I", version) + _hash32_bytes(header.get("prev_hash")) +
                _hash32_bytes(header.get("merkle_root")) + struct.pack("<III", ntime, nbits, int(nonce) & 0xFFFFFFFF))

    @staticmethod
    def nbits_to_target(nbits: Any) -> int:
        compact = _parse_int(nbits)
        exponent = compact >> 24; mantissa = compact & 0x007FFFFF
        if compact & 0x00800000: raise ValidationError("negative compact target")
        if exponent <= 3: return mantissa >> (8 * (3 - exponent))
        return mantissa << (8 * (exponent - 3))

    @classmethod
    def verify_nonce(cls, header: dict[str, Any], nonce: int) -> bool:
        digest = hashlib.sha256(hashlib.sha256(cls.serialize_header(header, nonce)).digest()).digest()
        target = cls.nbits_to_target(header.get("nbits", header.get("bits", 0)))
        return int.from_bytes(digest, "little") <= target


class VQCPhiGroverIntegration:
    """Verified VQC ranking with injectable φ-Grover fallback."""

    def __init__(self, vqc: PhiGroverVQC,
                 fallback: Optional[Callable[[dict[str, Any], int], Optional[int]]] = None):
        self.vqc = vqc; self.fallback = fallback
        self.total_predictions = 0; self.valid_predictions = 0

    def mine_block(self, header: dict[str, Any], *, candidate_count: Optional[int] = None,
                   max_fallback_checks: int = 0) -> dict[str, Any]:
        started = time.perf_counter()
        ranked = self.vqc.rank_candidates(header, candidate_count)
        checked = 0
        for nonce in ranked["candidates"]:
            checked += 1
            if self.vqc.verify_nonce(header, nonce):
                self.total_predictions += 1; self.valid_predictions += 1
                return {"nonce": nonce, "valid": True, "method": "vqc_ranked", "checked": checked,
                        "confidence": ranked["confidence"], "runtime_ms": (time.perf_counter()-started)*1000}
        if self.fallback is not None:
            nonce = self.fallback(header, max_fallback_checks)
            if nonce is not None and self.vqc.verify_nonce(header, int(nonce)):
                self.total_predictions += 1; self.valid_predictions += 1
                return {"nonce": int(nonce), "valid": True, "method": "phi_grover_fallback", "checked": checked,
                        "confidence": 0.0, "runtime_ms": (time.perf_counter()-started)*1000}
        # Deterministic bounded fallback for offline validation.
        for nonce in range(max(0, int(max_fallback_checks))):
            checked += 1
            if self.vqc.verify_nonce(header, nonce):
                self.total_predictions += 1; self.valid_predictions += 1
                return {"nonce": nonce, "valid": True, "method": "bounded_verified_fallback", "checked": checked,
                        "confidence": 0.0, "runtime_ms": (time.perf_counter()-started)*1000}
        self.total_predictions += 1
        return {"nonce": None, "valid": False, "method": "not_found_within_budget", "checked": checked,
                "confidence": ranked["confidence"], "runtime_ms": (time.perf_counter()-started)*1000}

    def reinforce(self, header: dict[str, Any], valid_nonce: int, epochs: int = 1) -> dict[str, Any]:
        if not self.vqc.verify_nonce(header, valid_nonce):
            raise ValidationError("reinforcement nonce is not valid for header target")
        return self.vqc.train([{"header": header, "nonce": int(valid_nonce)}], epochs=epochs, batch_size=1)


class VQCTrainingDataGenerator:
    def generate_from_blocks(self, blocks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for block in blocks:
            if "header" not in block or "nonce" not in block:
                raise ValidationError("block requires header and nonce")
            result.append({"header": dict(block["header"]), "nonce": int(block["nonce"]),
                           "valid": PhiGroverVQC.verify_nonce(block["header"], int(block["nonce"]))})
        return result
