"""Chronus algebraic search optimisation for the mining execution fabric.

The generated search plan is portable across CPU, GPU, ASIC, and Super ASIC
hashing routes.  Consensus verification remains SHA-256d so stronger execution
technology can scale without creating an incompatible proof.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

import numpy as np

from quantum_compute_substrate.phi_tensor_core import FoldState, QuantumFoldTensorCore


@dataclass(frozen=True)
class SubstrateOrderingEvidence:
    candidate_count: int
    original_dim: int
    folded_dim: int
    fold_depth: int
    compression_ratio: float
    reconstruction_error_l2: float
    state_norm: float
    transformed_norm: float
    permutation_preserved: bool
    input_fingerprint: str
    output_fingerprint: str
    operator: str = "phi-tensor-diffusion"
    role: str = "SEARCH_OPTIMIZATION"
    execution_scope: str = "CPU/GPU/ASIC/SUPER_ASIC"
    consensus_authority: bool = False
    consensus_rule: str = "SHA256d(header) <= target"
    claim_lane: str = "RESTRICTED (INTERNAL)"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ChronusSubstrateMiningBridge:
    """Build accelerator-portable search plans with the integrated tensor core."""

    def __init__(self, *, seed: int = 0) -> None:
        self.seed = int(seed)

    @staticmethod
    def _validate_nonces(nonces: Sequence[int]) -> list[int]:
        normalized: list[int] = []
        for raw in nonces:
            if isinstance(raw, bool):
                raise ValueError("nonce candidates must be uint32 integers")
            nonce = int(raw)
            if nonce != raw or not 0 <= nonce <= 0xFFFFFFFF:
                raise ValueError("nonce candidates must be uint32 integers")
            normalized.append(nonce)
        if len(set(normalized)) != len(normalized):
            raise ValueError("nonce candidates must be unique")
        return normalized

    @staticmethod
    def _fingerprint(nonces: list[int]) -> str:
        # Deferred import avoids a module cycle while using the canonical seal.
        from mining.hash_pipeline import nonce_order_fingerprint

        return nonce_order_fingerprint(nonces).hex()

    def order(
        self,
        nonces: Sequence[int],
        scores: Sequence[float],
        *,
        fold_depth: int = 1,
    ) -> tuple[list[int], SubstrateOrderingEvidence]:
        """Return a sealed permutation and measured substrate evidence."""

        if not isinstance(fold_depth, int) or isinstance(fold_depth, bool) or fold_depth < 0:
            raise ValueError("fold_depth must be a non-negative integer")
        candidates = self._validate_nonces(nonces)
        values = np.asarray(scores, dtype=np.float64)
        if values.ndim != 1 or values.size != len(candidates):
            raise ValueError("scores must be one-dimensional and match candidate count")
        if not np.all(np.isfinite(values)) or np.any(values < 0.0):
            raise ValueError("scores must be finite and non-negative")

        if not candidates:
            evidence = SubstrateOrderingEvidence(
                candidate_count=0,
                original_dim=0,
                folded_dim=0,
                fold_depth=0,
                compression_ratio=1.0,
                reconstruction_error_l2=0.0,
                state_norm=0.0,
                transformed_norm=0.0,
                permutation_preserved=True,
                input_fingerprint=self._fingerprint([]),
                output_fingerprint=self._fingerprint([]),
            )
            return [], evidence

        if not np.any(values):
            values = np.ones(values.size, dtype=np.float64)
        state = FoldState(values.astype(np.complex128), 0, values.size).normalize()
        core = QuantumFoldTensorCore(core_id=0, dim=values.size, seed=self.seed)
        transformed = core.amplitude_amplification(state)
        if not core.integrity_check(state) or not core.integrity_check(transformed):
            raise RuntimeError("substrate transformation failed norm integrity")

        probabilities = np.abs(transformed.data) ** 2
        order = np.lexsort((np.arange(values.size), -probabilities))
        ordered = [candidates[int(index)] for index in order]
        permutation_preserved = sorted(ordered) == sorted(candidates)
        if not permutation_preserved:
            raise RuntimeError("substrate ordering changed the candidate set")

        folded = transformed.fold(target_depth=fold_depth)
        reconstruction_error = folded.reconstruction_error(transformed)
        evidence = SubstrateOrderingEvidence(
            candidate_count=len(candidates),
            original_dim=transformed.dim,
            folded_dim=folded.dim,
            fold_depth=folded.depth,
            compression_ratio=float(transformed.dim / folded.dim),
            reconstruction_error_l2=reconstruction_error,
            state_norm=state.norm,
            transformed_norm=transformed.norm,
            permutation_preserved=permutation_preserved,
            input_fingerprint=self._fingerprint(candidates),
            output_fingerprint=self._fingerprint(ordered),
        )
        return ordered, evidence


__all__ = ["ChronusSubstrateMiningBridge", "SubstrateOrderingEvidence"]
