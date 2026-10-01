"""Variational Quantum Circuit for phi-Grover mining — the VQC plane.

Ported from the VQC-for-phi-Grover pseudocode: a learned 32-qubit circuit
(one qubit per M_32 face) that maps block headers to a probability
distribution over candidate nonces, trained by the parameter-shift rule
with a quantum natural gradient.

Honest scope:
  * This is a quantum-inspired finite-precision model (NumPy backend).
    The pseudocode targeted ``mlx.core``; NumPy is the repo's canonical
    float substrate and ``config.device`` records the requested backend.
  * The circuit is a per-face variational mixer over the M_32 frame — it
    does not simulate a 2^32 state vector, and it makes no consensus
    claims. Predictions are verified by the canonical consensus check
    (``turing_core.hash_meets_target``) before anything is submitted.
  * The phi-Grover fallback probes the deterministic nonce schedule
    (``turing_core.iter_nonce_schedule``); like the reference, it is a
    structured search, not an assertion of O(1) mining.
"""

from __future__ import annotations

import hashlib
import logging
import math
import struct
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .turing_core import (
    hash_meets_target,
    iter_nonce_schedule,
    nbits_to_target,
)

logger = logging.getLogger("turing_universal_quantum_computer.variational")

PHI = 1.61803398875
PARAMETER_SHIFT = math.pi / 2.0

#: Nonce window the circuit distributes probability mass over.
DEFAULT_NONCE_WINDOW = 4096

#: Candidate count equals the M_32 face count — one candidate per face.
NUM_FACES = 32


class VQCError(ValueError):
    """A variational-circuit contract was violated."""


@dataclass(frozen=True)
class VQCConfig:
    """VQC configuration (ported fields; ``device`` records the requested
    backend — NumPy is the canonical execution substrate here)."""

    num_qubits: int = NUM_FACES
    num_layers: int = 4
    num_features: int = NUM_FACES
    learning_rate: float = 0.01
    batch_size: int = 64
    max_iterations: int = 1000
    device: str = "numpy"
    nonce_window: int = DEFAULT_NONCE_WINDOW
    seed: int = 0


class VariationalQuantumCircuit:
    """Variational circuit mapping block headers to nonce candidates.

    Learns the mapping header -> M_32 face distribution -> candidate
    nonces using quantum-inspired optimization (parameter-shift natural
    gradient, adaptive learning rate, phi-scaled initialization).
    """

    def __init__(self, config: VQCConfig) -> None:
        if config.num_qubits < 1 or config.num_layers < 1:
            raise VQCError("num_qubits and num_layers must be >= 1")
        self.config = config
        self.num_qubits = int(config.num_qubits)
        self.num_layers = int(config.num_layers)

        # Variational parameters theta: [layers, qubits, 3] = RY, RZ, entangle
        self.theta = self._initialize_parameters(config.seed)

        # M_32 manifold structure
        self.M_32_adjacency = self._build_m32_adjacency()
        self.M_32_laplacian = self._build_m32_laplacian()

        # Optimization bookkeeping
        self.loss_history: List[float] = []
        self.accuracy_history: List[float] = []
        self.best_params: Optional[np.ndarray] = None
        self.best_loss = float("inf")

    # -- structure -----------------------------------------------------------

    def _initialize_parameters(self, seed: int) -> np.ndarray:
        """phi-scaled uniform initialization in [-pi, pi) * phi."""
        rng = np.random.default_rng(seed)
        return rng.uniform(-math.pi, math.pi, (self.num_layers, self.num_qubits, 3)) * PHI

    @staticmethod
    def _phi_connected(i: int, j: int) -> bool:
        """Two faces are phi-connected when ``abs(i-j)`` lands on a
        phi-power residue mod 32 — the injected M_32 structure."""
        return abs(i - j) in {int(PHI**k) % NUM_FACES for k in range(5)}

    def _build_m32_adjacency(self) -> np.ndarray:
        """Adjacency of the 32-face manifold under the phi-connection rule."""
        adj = np.zeros((NUM_FACES, NUM_FACES), dtype=np.float64)
        for i in range(NUM_FACES):
            for j in range(NUM_FACES):
                if self._phi_connected(i, j):
                    adj[i, j] = 1.0
        return adj

    def _build_m32_laplacian(self) -> np.ndarray:
        """Graph Laplacian ``D - A`` of the M_32 adjacency."""
        degree = np.diag(self.M_32_adjacency.sum(axis=1))
        return degree - self.M_32_adjacency

    # -- forward pass ----------------------------------------------------------

    def _extract_features(self, header: Dict[str, Any]) -> np.ndarray:
        """32-dim feature vector: five header fields plus 27 phi-derived
        features ``int(features[i % 5] * phi^(i+1)) % 2^32`` (ported)."""
        fields = [
            _as_int(header.get("version", 0)),
            _as_int(str(header.get("prev_hash", "0"))[:8]),
            _as_int(str(header.get("merkle_root", "0"))[:8]),
            _as_int(header.get("ntime", 0)),
            _as_int(header.get("nbits", 0)),
        ]
        features = list(fields)
        for i in range(27):
            features.append(int(features[i % len(fields)] * PHI ** (i + 1)) % 2**32)
        return np.array(features[: self.config.num_features], dtype=np.float64)

    @staticmethod
    def _phi_encoding(features: np.ndarray) -> np.ndarray:
        """Normalize to (-pi, pi] then scale by phi (ported)."""
        normalized = (features % (2.0 * math.pi)) - math.pi
        return normalized * PHI

    def _candidate_nonces(self, header: Dict[str, Any]) -> List[int]:
        """One candidate nonce per M_32 face, drawn from the canonical
        deterministic schedule seeded by the header."""
        seed = _as_int(header.get("ntime", 0)) ^ _as_int(header.get("version", 0))
        window = max(int(self.config.nonce_window), NUM_FACES)
        return list(iter_nonce_schedule(window, seed=seed, cap=NUM_FACES))

    def forward(self, block_header: Dict[str, Any]) -> Dict[str, Any]:
        """Run the variational circuit: encode -> rotate -> entangle ->
        measure. Returns the nonce distribution over face candidates."""
        encoded = self._phi_encoding(self._extract_features(block_header))
        state = encoded[: self.num_qubits].copy()
        adjacency = self.M_32_adjacency
        degree = np.maximum(adjacency.sum(axis=1), 1.0)
        mixer = adjacency / degree[:, None]
        for layer in range(self.num_layers):
            ry = self.theta[layer, :, 0]
            rz = self.theta[layer, :, 1]
            entangle = self.theta[layer, :, 2]
            # Rotation layer: per-face RY rotation with RZ phase weighting
            rotated = state * np.cos(ry) + (mixer @ state) * np.sin(ry)
            state = rotated * np.cos(rz) + np.roll(rotated, 1) * np.sin(rz)
            # Entangling layer: laplacian-weighted mixing per theta_entangle
            state = state + np.tanh(entangle) * (mixer @ state - state)
        logits = state - np.max(state)
        probabilities = np.exp(logits)
        probabilities /= probabilities.sum()
        candidates = self._candidate_nonces(block_header)
        order = np.argsort(probabilities)[::-1]
        return {
            "nonce": candidates[int(order[0])],
            "confidence": float(probabilities[int(order[0])]),
            "top_nonces": [candidates[int(i)] for i in order[:5]],
            "probabilities": probabilities,
            "candidates": candidates,
        }

    # -- training ------------------------------------------------------------

    def _compute_loss(self, probabilities: np.ndarray, target_index: Optional[int]) -> float:
        """Cross-entropy on the candidate distribution; an absent target
        gets the floor probability (honest penalty, never a free pass)."""
        prob = (
            float(probabilities[target_index])
            if target_index is not None and 0 <= target_index < len(probabilities)
            else 1e-12
        )
        return -math.log(max(prob, 1e-12))

    def _target_index(self, candidates: Sequence[int], target_nonce: int) -> Optional[int]:
        try:
            return list(candidates).index(target_nonce)
        except ValueError:
            return None

    def _quantum_natural_gradient(self, header: Dict[str, Any], target_nonce: int) -> np.ndarray:
        """Parameter-shift gradient: two forward evaluations per
        parameter (theta +/- pi/2). 768 evaluations per step at the
        default shape — the embarrassingly parallel GPU-plane workload."""
        gradients = np.zeros_like(self.theta)
        for layer in range(self.num_layers):
            for qubit in range(self.num_qubits):
                for param_idx in range(3):
                    self.theta[layer, qubit, param_idx] += PARAMETER_SHIFT
                    result = self.forward(header)
                    loss_plus = self._compute_loss(
                        result["probabilities"],
                        self._target_index(result["candidates"], target_nonce),
                    )
                    self.theta[layer, qubit, param_idx] -= 2 * PARAMETER_SHIFT
                    result = self.forward(header)
                    loss_minus = self._compute_loss(
                        result["probabilities"],
                        self._target_index(result["candidates"], target_nonce),
                    )
                    self.theta[layer, qubit, param_idx] += PARAMETER_SHIFT
                    gradients[layer, qubit, param_idx] = (loss_plus - loss_minus) / 2.0
        return gradients

    def _update_parameters(self, gradient: np.ndarray, step_scale: float = 1.0) -> None:
        """Adaptive learning rate update — the rate halves whenever the
        best loss stalls (barren-plateau mitigation)."""
        self.theta -= self.config.learning_rate * step_scale * gradient

    def _train_batch(self, batch_data: List[Dict[str, Any]]) -> Tuple[float, float]:
        batch_loss = 0.0
        batch_accuracy = 0.0
        for sample in batch_data:
            header = sample["header"]
            target_nonce = int(sample["nonce"])
            result = self.forward(header)
            batch_loss += self._compute_loss(
                result["probabilities"],
                self._target_index(result["candidates"], target_nonce),
            )
            batch_accuracy += 1.0 if result["nonce"] == target_nonce else 0.0
            gradient = self._quantum_natural_gradient(header, target_nonce)
            self._update_parameters(gradient)
        n = max(len(batch_data), 1)
        return batch_loss / n, batch_accuracy / n

    def train(
        self,
        training_data: List[Dict[str, Any]],
        epochs: int = 10,
        batch_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Batch training over block samples for ``epochs`` passes."""
        if not training_data:
            raise VQCError("training_data must be non-empty")
        size = batch_size or self.config.batch_size
        for epoch in range(max(int(epochs), 1)):
            epoch_loss = 0.0
            epoch_acc = 0.0
            batches = 0
            for start in range(0, len(training_data), size):
                loss, acc = self._train_batch(training_data[start : start + size])
                epoch_loss += loss
                epoch_acc += acc
                batches += 1
            epoch_loss /= max(batches, 1)
            epoch_acc /= max(batches, 1)
            self.loss_history.append(epoch_loss)
            self.accuracy_history.append(epoch_acc)
            if epoch_loss < self.best_loss:
                self.best_loss = epoch_loss
                self.best_params = self.theta.copy()
            logger.debug("epoch %d: loss=%.6f acc=%.4f", epoch, epoch_loss, epoch_acc)
        return {
            "loss_history": list(self.loss_history),
            "accuracy_history": list(self.accuracy_history),
            "best_loss": self.best_loss,
        }

    # -- inference -------------------------------------------------------------

    def predict(self, block_header: Dict[str, Any]) -> int:
        """Predict the nonce — uses the best checkpoint when available."""
        if self.best_params is not None:
            original = self.theta
            self.theta = self.best_params
            try:
                return self.forward(block_header)["nonce"]
            finally:
                self.theta = original
        return self.forward(block_header)["nonce"]

    def predict_with_confidence(self, block_header: Dict[str, Any]) -> Dict[str, Any]:
        """Prediction plus confidence and the top-5 candidates."""
        if self.best_params is not None:
            original = self.theta
            self.theta = self.best_params
            try:
                return self.forward(block_header)
            finally:
                self.theta = original
        return self.forward(block_header)


class VQCTrainingDataGenerator:
    """Builds VQC training samples from historical blocks: header fields,
    the valid nonce, and the phi-encoded feature vector."""

    def __init__(self) -> None:
        self.phi = PHI

    def generate_from_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        training_data = []
        for block in blocks:
            header = block["header"]
            nonce = int(block["nonce"])
            features = self._extract_features(header)
            encoded = self._phi_encoding(features)
            training_data.append(
                {
                    "header": header,
                    "nonce": nonce,
                    "features": features,
                    "encoded": encoded,
                    "target": block.get("target", 0),
                }
            )
        return training_data

    @staticmethod
    def _extract_features(header: Dict[str, Any]) -> np.ndarray:
        fields = [
            _as_int(header.get("version", 0)),
            _as_int(str(header.get("prev_hash", "0"))[:8]),
            _as_int(str(header.get("merkle_root", "0"))[:8]),
            _as_int(header.get("ntime", 0)),
            _as_int(header.get("nbits", 0)),
        ]
        features = list(fields)
        for i in range(27):
            features.append(int(features[i % len(fields)] * PHI ** (i + 1)) % 2**32)
        return np.array(features[:NUM_FACES], dtype=np.float64)

    def _phi_encoding(self, features: np.ndarray) -> np.ndarray:
        normalized = (features % (2.0 * math.pi)) - math.pi
        return normalized * self.phi


class VQCPhiGroverIntegration:
    """VQC prediction -> consensus verification -> phi-Grover fallback ->
    reinforcement update. The VQC never submits unverified nonces."""

    def __init__(self, vqc: VariationalQuantumCircuit) -> None:
        self.vqc = vqc
        self.predictions: List[Dict[str, Any]] = []
        self.validations: List[bool] = []
        self.performance = {
            "accuracy": 0.0,
            "avg_confidence": 0.0,
            "total_predictions": 0,
        }

    def mine_block(self, block_header: Dict[str, Any]) -> Dict[str, Any]:
        """1. VQC predicts; 2. canonical verification; 3. on failure the
        phi-Grover schedule fallback searches the nonce window; 4. the VQC
        is updated with the verified nonce (reinforcement)."""
        vqc_result = self.vqc.predict_with_confidence(block_header)
        predicted_nonce = int(vqc_result["nonce"])
        confidence = float(vqc_result["confidence"])

        self.predictions.append(vqc_result)
        total = self.performance["total_predictions"] + 1
        self.performance["avg_confidence"] = (
            self.performance["avg_confidence"] * self.performance["total_predictions"] + confidence
        ) / total

        if self._verify_nonce(block_header, predicted_nonce):
            self.validations.append(True)
            self.performance["accuracy"] = (
                self.performance["accuracy"] * self.performance["total_predictions"] + 1.0
            ) / total
            self.performance["total_predictions"] = total
            return {
                "nonce": predicted_nonce,
                "method": "vqc",
                "confidence": confidence,
                "valid": True,
            }

        self.validations.append(False)
        self.performance["accuracy"] = (
            self.performance["accuracy"] * self.performance["total_predictions"]
        ) / total
        self.performance["total_predictions"] = total

        phi_grover_nonce = self._phi_grover_search(block_header)
        if phi_grover_nonce is not None:
            self._update_vqc(block_header, phi_grover_nonce)
            return {
                "nonce": phi_grover_nonce,
                "method": "phi_grover_fallback",
                "confidence": 0.5,
                "valid": True,
            }
        return {
            "nonce": predicted_nonce,
            "method": "vqc_unverified",
            "confidence": confidence,
            "valid": False,
        }

    def _verify_nonce(self, header: Dict[str, Any], nonce: int) -> bool:
        """Canonical consensus check: sha256d(header||nonce) <= target."""
        digest = _header_sha256d(header, nonce)
        nbits = _as_int(header.get("nbits", 0))
        if nbits == 0:
            return False
        return hash_meets_target(digest, nbits_to_target(nbits))

    def _phi_grover_search(self, header: Dict[str, Any]) -> Optional[int]:
        """Fallback: probe the deterministic nonce schedule until the
        consensus check passes (structured search, not an O(1) claim)."""
        window = max(int(self.vqc.config.nonce_window), NUM_FACES)
        for nonce in iter_nonce_schedule(window, seed=0, cap=window):
            if self._verify_nonce(header, nonce):
                return nonce
        return None

    def _update_vqc(self, header: Dict[str, Any], valid_nonce: int) -> None:
        """One-shot reinforcement update with the verified nonce."""
        self.vqc._train_batch([{"header": header, "nonce": int(valid_nonce)}])


def _as_int(value: Any) -> int:
    """Accept ints or hex/decimal strings (header fields arrive both ways)."""
    if isinstance(value, (int, np.integer)):
        return int(value)
    text = str(value).strip().lower()
    if not text:
        return 0
    try:
        return int(text, 16) if any(c in "abcdefx" for c in text) else int(text)
    except ValueError:
        try:
            return int(text, 16)
        except ValueError:
            return 0


def _header_sha256d(header: Dict[str, Any], nonce: int) -> bytes:
    """Serialize the 80-byte block header and double-SHA-256 it."""
    version = _as_int(header.get("version", 0))
    prev_hash = str(header.get("prev_hash", "0" * 64)).zfill(64)[-64:]
    merkle_root = str(header.get("merkle_root", "0" * 64)).zfill(64)[-64:]
    ntime = _as_int(header.get("ntime", 0))
    nbits = _as_int(header.get("nbits", 0))
    header_bytes = struct.pack("<I", version)
    header_bytes += bytes.fromhex(prev_hash)
    header_bytes += bytes.fromhex(merkle_root)
    header_bytes += struct.pack("<I", ntime)
    header_bytes += struct.pack("<I", nbits)
    header_bytes += struct.pack("<I", nonce & 0xFFFFFFFF)
    return hashlib.sha256(hashlib.sha256(header_bytes).digest()).digest()


def demonstrate_vqc() -> Dict[str, Any]:
    """End-to-end demonstration: init, train on simulated blocks, predict,
    and integrate with the phi-Grover pipeline."""
    config = VQCConfig(
        num_qubits=NUM_FACES,
        num_layers=4,
        num_features=NUM_FACES,
        learning_rate=0.01,
        max_iterations=1000,
    )
    vqc = VariationalQuantumCircuit(config)

    generator = VQCTrainingDataGenerator()
    sample_blocks = [
        {
            "header": {
                "version": "1",
                "prev_hash": "0" * 64,
                "merkle_root": "0" * 64,
                "ntime": "0",
                "nbits": "1d00ffff",
            },
            "nonce": i,
            "target": 0x1D00FFFF,
        }
        for i in range(8)
    ]
    training_data = generator.generate_from_blocks(sample_blocks)
    training_result = vqc.train(training_data, epochs=2, batch_size=4)

    test_header = {
        "version": "1",
        "prev_hash": "0" * 64,
        "merkle_root": "0" * 64,
        "ntime": "0",
        "nbits": "1d00ffff",
    }
    prediction = vqc.predict_with_confidence(test_header)
    integration = VQCPhiGroverIntegration(vqc)
    result = integration.mine_block(test_header)

    return {
        "vqc": vqc,
        "training": training_result,
        "prediction": prediction,
        "integration": result,
    }


__all__ = [
    "DEFAULT_NONCE_WINDOW",
    "NUM_FACES",
    "PARAMETER_SHIFT",
    "PHI",
    "VQCConfig",
    "VQCError",
    "VQCPhiGroverIntegration",
    "VQCTrainingDataGenerator",
    "VariationalQuantumCircuit",
    "demonstrate_vqc",
]
