"""Counterfactual Intelligence — Share Submission and Alternative Reasoning Authority.

Operates across Substrates:
  - Substrate 5: Counterfactual (Rung 3 what-if trajectory projection)
  - Substrate 2: Causal (Structural counterfactuals via Pearl's Ladder)
  - Substrate 6: Yang-Mills (finite 2I spectral gap, not a share accept)

Provides ADVISORY intelligence for alternative-branch evaluation and submission
timing analysis. PYTHIA remains final authority for mining truth, SearchPlan
finalization, nonce-estate coverage, SHA256d/target proof semantics, share
validation/submission, credentials, and pool acknowledgements.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: mining
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import time
from typing import Any, Dict, List, Optional


@dataclass
class CounterfactualAnalysis:
    """Rung 3 Counterfactual trajectory report."""

    candidate_nonce: int
    candidate_hash_hex: str
    is_valid_share: bool
    counterfactual_alternatives: List[Dict[str, Any]]
    yang_mills_bound_met: bool
    recommended_action: str
    timestamp: float = field(default_factory=time.time)
    provenance_hash: str = ""

    def __post_init__(self):
        if not self.provenance_hash:
            seed = (
                f"{self.candidate_nonce}:{self.candidate_hash_hex}:"
                f"{self.recommended_action}:{self.timestamp}"
            )
            self.provenance_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def to_scalar(self) -> float:
        """Dual-mode scalar return: 1.0 if submit recommended, 0.0 otherwise."""
        return 1.0 if self.recommended_action == "SUBMIT" else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_nonce": self.candidate_nonce,
            "candidate_hash_hex": self.candidate_hash_hex,
            "is_valid_share": self.is_valid_share,
            "counterfactual_count": len(self.counterfactual_alternatives),
            "yang_mills_bound_met": self.yang_mills_bound_met,
            "recommended_action": self.recommended_action,
            "timestamp": self.timestamp,
            "provenance_hash": self.provenance_hash,
            "alternatives_sample": self.counterfactual_alternatives[:3],
        }


class CounterfactualIntelligence:
    """Advisory intelligence for counterfactual evaluation and submission-timing analysis."""

    def __init__(self):
        self.submission_log: List[CounterfactualAnalysis] = []
        self.plasticity_weights: Dict[str, float] = {
            "direct_submission": 1.0,
            "batched_submission": 0.9,
            "burst_submission": 0.8,
        }
        self.plasticity = 0.05
        # One-time finite-model gap, computed at construction so the first
        # submission decision never pays the Laplacian cold-start latency.
        self._mass_gap: Optional[float] = None
        try:
            self._mass_gap = float(self.yang_mills_mass_gap())
        except Exception:
            self._mass_gap = None

    def yang_mills_mass_gap(self) -> float:
        """Finite 2I Laplacian gap. Not a share-accept rule."""
        if self._mass_gap is not None:
            return self._mass_gap
        from toe.poincare_yangmills import finite_gauge_gap

        return finite_gauge_gap()

    @staticmethod
    def double_sha256(header: bytes) -> bytes:
        """Exact double-SHA256 consensus function."""
        return hashlib.sha256(hashlib.sha256(header).digest()).digest()

    def evaluate_submission(
        self,
        candidate_nonce: int,
        header_template: bytes,
        target_int: int,
        alternative_nonces: Optional[List[int]] = None,
    ) -> CounterfactualAnalysis:
        """Evaluate candidate submission and project counterfactual alternatives.

        Rung 3: "What would the hash have been if alternative nonce X were chosen?"
        Applies the finite 2I spectral gap as a side condition only.
        Share validity is double-SHA256 against the target, nothing else.
        """
        if not isinstance(header_template, (bytes, bytearray)) or len(header_template) != 76:
            raise ValueError(
                f"header_template must be exactly 76 bytes, got {len(header_template)}"
            )

        # Pack nonce into the 80-byte header (bytes 76-80, little-endian nonce,
        # little-endian digest vs target — Bitcoin consensus byte order).
        header_bytes = bytes(header_template) + candidate_nonce.to_bytes(4, byteorder="little")

        # Consensus hash check (sole accept authority guidance)
        raw_hash = self.double_sha256(header_bytes)
        hash_int = int.from_bytes(raw_hash, byteorder="little")
        hash_hex = raw_hash.hex()
        is_valid_share = hash_int <= target_int

        # Finite-model spectral gap. Positive or not, it does not accept a
        # share — and a failure to compute it must not block one either.
        try:
            gap = self.yang_mills_mass_gap()
            ym_bound_ok = gap > 0.0
        except Exception:
            ym_bound_ok = False

        # Project counterfactual branches
        alternatives_report: List[Dict[str, Any]] = []
        alts = alternative_nonces or [
            (candidate_nonce ^ 1) & 0xFFFFFFFF,
            (candidate_nonce ^ 2) & 0xFFFFFFFF,
            (candidate_nonce + 1) & 0xFFFFFFFF,
        ]

        for alt_nonce in alts[:5]:
            alt_header = bytearray(header_bytes[:76])
            alt_header.extend(alt_nonce.to_bytes(4, byteorder="little"))
            alt_hash = self.double_sha256(bytes(alt_header))
            alt_int = int.from_bytes(alt_hash, byteorder="little")
            alternatives_report.append(
                {
                    "alt_nonce": alt_nonce,
                    "alt_hash_hex": alt_hash.hex(),
                    "alt_would_meet_target": alt_int <= target_int,
                    "entropy_delta": float(abs(alt_int - hash_int) % 10000) / 10000.0,
                }
            )

        action = "SUBMIT" if is_valid_share else "DISCARD"
        analysis = CounterfactualAnalysis(
            candidate_nonce=candidate_nonce,
            candidate_hash_hex=hash_hex,
            is_valid_share=is_valid_share,
            counterfactual_alternatives=alternatives_report,
            yang_mills_bound_met=ym_bound_ok,
            recommended_action=action,
        )
        self.submission_log.append(analysis)
        return analysis

    def learn(self, pattern: str, accepted: bool) -> None:
        """Plasticity updates for share acceptance rates."""
        w = self.plasticity_weights.get(pattern, 0.5)
        if accepted:
            self.plasticity_weights[pattern] = min(2.0, w + self.plasticity)
        else:
            self.plasticity_weights[pattern] = max(0.1, w - self.plasticity)
