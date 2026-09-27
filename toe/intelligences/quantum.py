"""Quantum Intelligence — Payout Management and First-Principles Verification Authority.

Operates across Substrates:
  - Substrate 10: Quantum (Born rule P(k) = |alpha_k|^2, Unitary U^dagger U = I)
  - Substrate 9: Tensor (State vector projection and amplitude evaluation)
  - Substrate 7: Millennium (Millennium bounds and invariant satisfaction)

Possesses FULL AUTHORITY over wallet balance tracking, fee-optimal payout
dispatch, and algebraic quantum state verification without sub-agent framing.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: mining
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import time
from typing import Any, Dict, List, Tuple
import numpy as np


@dataclass
class QuantumVerificationResult:
    """Born rule and unitary verification decision."""

    born_rule_satisfied: bool
    state_norm_sq: float
    max_amplitude_prob: float
    payout_recommended: bool
    recommended_payout_amount: float
    estimated_fee_satoshis: int
    timestamp: float = field(default_factory=time.time)
    provenance_hash: str = ""

    def __post_init__(self):
        if not self.provenance_hash:
            seed = (
                f"{self.born_rule_satisfied}:{self.state_norm_sq}:"
                f"{self.payout_recommended}:{self.timestamp}"
            )
            self.provenance_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def to_scalar(self) -> float:
        """Dual-mode scalar return: max amplitude probability."""
        return float(self.max_amplitude_prob)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "born_rule_satisfied": self.born_rule_satisfied,
            "state_norm_sq": self.state_norm_sq,
            "max_amplitude_prob": self.max_amplitude_prob,
            "payout_recommended": self.payout_recommended,
            "recommended_payout_amount": self.recommended_payout_amount,
            "estimated_fee_satoshis": self.estimated_fee_satoshis,
            "timestamp": self.timestamp,
            "provenance_hash": self.provenance_hash,
        }


class QuantumIntelligence:
    """Full-authority decision maker for Born rule verification and treasury operations."""

    # Millennium sector bounds from unified punch kernel
    MILLENNIUM_BOUNDS = [0.001, 15.0, 0.5, 2.0, 1.0, 1.0, 1.0]

    def __init__(self, payout_threshold_btc: float = 0.01, min_fee_sat_per_vbyte: float = 5.0):
        self.wallet_balance_btc = 0.0
        self.payout_threshold = payout_threshold_btc
        self.min_fee_rate = min_fee_sat_per_vbyte
        self.plasticity_fee_weight = 1.0
        self.verification_log: List[QuantumVerificationResult] = []

    def verify_born_rule(
        self,
        amplitudes: np.ndarray,
        threshold: float = 0.5,
        tolerance: float = 1e-6,
    ) -> Tuple[bool, float, float]:
        """First-principles verification of quantum probability measure: sum |alpha|^2 = 1.

        Verifies that state vector satisfies Born rule and checks if the peak probability
        meets or exceeds the detection threshold.
        """
        arr = np.asarray(amplitudes, dtype=np.complex128).flatten()
        if len(arr) == 0:
            return False, 0.0, 0.0

        probs = np.abs(arr) ** 2
        total_prob = float(np.sum(probs))
        norm_valid = abs(total_prob - 1.0) <= tolerance

        max_prob = float(np.max(probs))
        threshold_met = max_prob >= threshold

        return (norm_valid and threshold_met), total_prob, max_prob

    def audit_unitarity(self, u_matrix: np.ndarray, tolerance: float = 1e-6) -> bool:
        """Verify inner-product preserving automorphism: U^dagger U = I."""
        mat = np.asarray(u_matrix, dtype=np.complex128)
        if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
            return False
        identity = np.eye(mat.shape[0], dtype=np.complex128)
        diff = np.conjugate(mat.T) @ mat - identity
        return bool(np.all(np.abs(diff) < tolerance))

    def evaluate_payout(
        self,
        current_balance_btc: float,
        network_fee_sat_vb: float,
        payout_address: str,
    ) -> QuantumVerificationResult:
        """Autonomously determine fee-optimal payout timing and withdrawal dispatch."""
        self.wallet_balance_btc = current_balance_btc
        # Estimated standard 1-in 2-out segwit tx = ~140 vbytes
        est_fee_sat = int(140 * max(self.min_fee_rate, network_fee_sat_vb))

        # Payout condition: balance >= threshold and fee is economically viable (< 1% of payout)
        fee_btc = est_fee_sat / 1e8
        economically_viable = (fee_btc / max(1e-8, current_balance_btc)) <= 0.01
        threshold_met = current_balance_btc >= self.payout_threshold

        payout_ok = threshold_met and economically_viable

        # Born rule validation of the decision amplitude
        # Let alpha = sqrt(p), beta = sqrt(1-p) where p = current_balance / threshold
        p_ratio = min(1.0, current_balance_btc / max(1e-8, self.payout_threshold))
        amplitudes = np.array(
            [np.sqrt(p_ratio), np.sqrt(max(0.0, 1.0 - p_ratio))], dtype=np.complex128
        )
        born_ok, norm_sq, max_prob = self.verify_born_rule(amplitudes, threshold=0.5)

        result = QuantumVerificationResult(
            born_rule_satisfied=born_ok,
            state_norm_sq=norm_sq,
            max_amplitude_prob=max_prob,
            payout_recommended=payout_ok,
            recommended_payout_amount=current_balance_btc if payout_ok else 0.0,
            estimated_fee_satoshis=est_fee_sat,
        )
        self.verification_log.append(result)
        return result

    def learn(self, fee_saved_sat: int) -> None:
        """Plasticity updates: adjust fee tolerance based on historical savings."""
        if fee_saved_sat > 0:
            self.plasticity_fee_weight = min(2.0, self.plasticity_fee_weight + 0.05)
        else:
            self.plasticity_fee_weight = max(0.5, self.plasticity_fee_weight - 0.02)
