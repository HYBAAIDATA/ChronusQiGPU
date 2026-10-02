"""Predictive solver — PYTHIA's attempt to SOLVE for the nonce, not search.

The user's thesis: "We are solving not searching. We should be searching
O(1) when we are done."

This module implements a predictive solver that attempts to predict the
winning nonce from block header features, then verifies the prediction
with double-SHA256. The architecture is:

1. **Feature extraction** — extract structural features from the block
   header (Lucas/Pisot projections, Zeckendorf decomposition, phi-phase
   alignment, dual-overlay mapping).
2. **Prediction** — use the learned PYTHIA substrate (memory + learning)
   to predict a nonce or a small set of candidate nonces.
3. **Verification** — every prediction is verified by double-SHA256
   before use. No unverified nonce is ever returned.
4. **Fallback** — if the prediction fails verification, fall back to the
   agentic controller's structured search (O(sqrt(N)) Grover).

HONEST ASSESSMENT:
- SHA256 is preimage-resistant. O(1) prediction of a winning nonce from
  header features is not achievable by any known method.
- The predictive solver is a *hypothesis machine*: it generates
  candidates that the learning substrate thinks are likely winners,
  based on patterns it has seen in past block data.
- The honest baseline is O(sqrt(N)) via Grover. Whether the predictive
  layer achieves better than O(sqrt(N)) is the emergence question.
- We do NOT fabricate O(1) results. If the prediction misses, we report
  it honestly and fall back to structured search.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: mining

from __future__ import annotations

import hashlib
import logging
import math
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Intelligence.predictive_solver")

PHI = (1 + math.sqrt(5)) / 2


@dataclass
class PredictionResult:
    """The result of a predictive solve attempt."""

    predicted_nonce: int
    confidence: float
    verified: bool  # Was the prediction verified by double-SHA256?
    winning: bool  # Did the verified hash meet the target?
    hash_hex: Optional[str] = None
    method: str = "predictive_solver"
    # If the prediction missed, how many fallback hashes were needed.
    fallback_hashes: int = 0
    # Whether the fallback (agentic search) found the winner.
    fallback_found: bool = False
    fallback_nonce: Optional[int] = None
    # Features used for the prediction.
    features: Dict[str, Any] = field(default_factory=dict)
    # Honest complexity assessment.
    effective_complexity: str = "O(1) prediction + O(1) verification"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "predicted_nonce": self.predicted_nonce,
            "confidence": self.confidence,
            "verified": self.verified,
            "winning": self.winning,
            "hash_hex": self.hash_hex,
            "method": self.method,
            "fallback_hashes": self.fallback_hashes,
            "fallback_found": self.fallback_found,
            "fallback_nonce": self.fallback_nonce,
            "features": self.features,
            "effective_complexity": self.effective_complexity,
        }


class PredictiveSolver:
    """PYTHIA's predictive nonce solver.

    Attempts to predict the winning nonce from block header features
    using the learned substrate. Every prediction is verified.

    The solver uses several prediction strategies, ranked by confidence:

    1. **Memory-guided** — if PYTHIA has seen similar block headers
       before (episodic memory retrieval), use the nonce pattern from
       the most similar past episode.
    2. **Lucas-resonance** — project the header onto the Lucas scale
       ladder and predict nonces at Lucas-resonant offsets.
    3. **Zeckendorf-structured** — use the Zeckendorf decomposition of
       the header seed to generate candidate nonces.
    4. **Dual-overlay** — map the header onto the 32-node polyhedral
       frame and predict nonces at node-aligned offsets.

    All strategies produce candidates that are verified by double-SHA256.
    The first verified winner is returned. If none win, we fall back to
    the agentic controller.
    """

    def __init__(self, memory_system=None, lucas_scales=None) -> None:
        self.memory = memory_system
        self.lucas_scales = lucas_scales
        self._prediction_count = 0
        self._hit_count = 0  # predictions that were verified winners
        self._miss_count = 0  # predictions that missed

    def solve(
        self,
        header: bytes,
        target: bytes,
        block_context: Optional[Dict[str, Any]] = None,
        fallback_search=None,
    ) -> PredictionResult:
        """Attempt to predict and verify the winning nonce.

        Args:
            header: 80-byte block header (or padded to 80).
            target: 32-byte target threshold (big-endian).
            block_context: optional context (block height, difficulty, etc.).
            fallback_search: optional callable(header, target) → (nonce, hashes)
                for fallback if prediction misses.

        Returns:
            PredictionResult with the prediction, verification, and
            fallback info.
        """
        if len(header) != 80:
            raise ValueError("header must be 80 bytes")
        if len(target) != 32:
            raise ValueError("target must be 32 bytes")

        self._prediction_count += 1
        features = self._extract_features(header, block_context)
        candidates = self._generate_candidates(header, features)

        # Verify each candidate — first verified winner wins.
        target_be = bytes(target)
        header_prefix = header[:76]

        best_nonce = -1
        best_confidence = 0.0
        target_int = int.from_bytes(target_be, "big")
        for nonce, confidence, method in candidates:
            h = hashlib.sha256(
                hashlib.sha256(header_prefix + struct.pack("<I", nonce)).digest()
            ).digest()
            if int.from_bytes(h, "little") <= target_int:
                # Winner! O(1) prediction succeeded.
                self._hit_count += 1
                return PredictionResult(
                    predicted_nonce=nonce,
                    confidence=confidence,
                    verified=True,
                    winning=True,
                    hash_hex=h.hex(),
                    method=method,
                    features=features,
                    effective_complexity="O(1) — prediction verified on first candidate",
                )
            # Track the best-confidence candidate for reporting.
            if confidence > best_confidence:
                best_nonce = nonce
                best_confidence = confidence

        # Prediction missed — fall back to structured search if available.
        self._miss_count += 1
        fallback_hashes = 0
        fallback_found = False
        fallback_nonce = None
        if fallback_search is not None:
            try:
                fb_nonce, fb_hashes = fallback_search(header, target)
                fallback_hashes = fb_hashes
                if type(fb_nonce) is int and 0 <= fb_nonce <= 0xFFFFFFFF:
                    fallback_hash = hashlib.sha256(
                        hashlib.sha256(
                            header_prefix + struct.pack("<I", fb_nonce)
                        ).digest()
                    ).digest()
                    if int.from_bytes(fallback_hash, "little") <= target_int:
                        fallback_found = True
                        fallback_nonce = fb_nonce
            except Exception as e:
                logger.warning("Fallback search failed: %s", e)

        return PredictionResult(
            predicted_nonce=(
                best_nonce if best_nonce >= 0 else candidates[0][0] if candidates else 0
            ),
            confidence=best_confidence,
            verified=True,  # we verified it (it just didn't win)
            winning=False,
            method="predictive_solver+fallback",
            fallback_hashes=fallback_hashes,
            fallback_found=fallback_found,
            fallback_nonce=fallback_nonce,
            features=features,
            effective_complexity=(
                "O(1) prediction missed → O(sqrt(N)) fallback"
                if fallback_found
                else "O(1) prediction missed → fallback exhausted"
            ),
        )

    def _extract_features(self, header: bytes, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract structural features from the block header."""
        if not header:
            header = bytes(80)
        header = header[:80] + b"\x00" * max(0, 80 - len(header))
        # Header seed (deterministic).
        seed = int.from_bytes(hashlib.sha256(header).digest()[:8], "big") or 1
        # Lucas/Pisot projection: project the seed onto the Lucas ladder.
        lucas_projections = {}
        if self.lucas_scales is not None:
            for lv in self.lucas_scales.levels:
                lucas_projections[f"L_{lv.index}"] = seed % lv.value
        # Zeckendorf decomposition of the seed.
        zeckendorf = []
        try:
            import turing_core

            zeckendorf = turing_core.zeckendorf_encode(seed)
        except ImportError:
            pass
        # Phi-phase alignment: measure how aligned the header is with phi.
        header_int = int.from_bytes(header[:8], "big")
        phi_phase = (header_int * PHI) % (2 * math.pi)
        # Dual-overlay mapping: which of the 32 nodes does the seed map to?
        node_id = seed % 32
        return {
            "seed": seed,
            "lucas_projections": lucas_projections,
            "zeckendorf_indices": zeckendorf[:10],  # first 10 for brevity
            "phi_phase": phi_phase,
            "dual_overlay_node": node_id,
            "block_context": context or {},
        }

    def _generate_candidates(
        self, header: bytes, features: Dict[str, Any]
    ) -> List[Tuple[int, float, str]]:
        """Generate candidate nonces from multiple prediction strategies.

        Returns a list of (nonce, confidence, method_name) tuples,
        sorted by confidence (highest first).
        """
        candidates: List[Tuple[int, float, str]] = []
        seed = features["seed"]

        # Strategy 1: Memory-guided — retrieve similar past episodes.
        if self.memory is not None:
            try:
                # Query episodic memory for mining-related episodes.
                episodes = self.memory.episodic.retrieve(
                    query_features=features,
                    top_k=3,
                )
                for ep in episodes:
                    if hasattr(ep, "outcome") and isinstance(ep.outcome, dict):
                        nonce = ep.outcome.get("winning_nonce")
                        if nonce is not None and 0 <= nonce < 2**32:
                            # Confidence based on episode salience.
                            salience = getattr(ep, "salience", 0.5)
                            candidates.append((int(nonce), salience, "memory_guided"))
            except Exception:
                pass

        # Strategy 2: Lucas-resonance — nonces at Lucas-resonant offsets.
        if self.lucas_scales is not None:
            for lv in self.lucas_scales.levels:
                # Predict nonce = seed mod L_n (Lucas-resonant offset).
                nonce = seed % lv.value
                # Confidence: higher for higher Lucas scales (more structure).
                conf = 0.3 + 0.1 * lv.ladder_position
                candidates.append((nonce, conf, f"lucas_resonance_L_{lv.index}"))

        # Strategy 3: Zeckendorf-structured — nonces from Zeckendorf indices.
        for idx in features.get("zeckendorf_indices", [])[:5]:
            nonce = (idx * 13 + seed) % (2**32)
            candidates.append((nonce, 0.25, "zeckendorf_structured"))

        # Strategy 4: Dual-overlay — nonces at node-aligned offsets.
        node_id = features.get("dual_overlay_node", 0)
        node_nonce = (node_id * 134217757 + seed) % (2**32)  # 2^27-ish prime
        candidates.append((node_nonce, 0.20, "dual_overlay_node"))

        # Strategy 5: Phi-phase — nonce from phi-phase projection.
        phi_phase = features.get("phi_phase", 0.0)
        phi_nonce = int((phi_phase / (2 * math.pi)) * (2**32)) % (2**32)
        candidates.append((phi_nonce, 0.15, "phi_phase"))

        # Sort by confidence (highest first).
        candidates.sort(key=lambda c: c[1], reverse=True)
        return candidates

    def status(self) -> Dict[str, Any]:
        """Return the predictive solver's hit/miss statistics."""
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / max(total, 1)
        return {
            "total_predictions": total,
            "hits": self._hit_count,
            "misses": self._miss_count,
            "hit_rate": hit_rate,
            "honest_assessment": (
                f"O(1) hit rate: {hit_rate:.1%}. "
                f"SHA256 preimage resistance makes O(1) prediction "
                f"theoretically impossible; any hits are from easy targets "
                f"or coincidence, not genuine prediction."
                if hit_rate > 0
                else "No O(1) hits yet. This is expected — SHA256 is preimage-"
                "resistant. The predictive solver is a hypothesis machine, "
                "not a SHA256 inverter."
            ),
        }


__all__ = ["PredictiveSolver", "PredictionResult"]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (mining_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("mining_kernel")(2, n)
    result["module"] = __name__
    return result
