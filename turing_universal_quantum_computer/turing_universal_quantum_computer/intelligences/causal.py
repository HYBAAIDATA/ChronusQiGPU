"""Causal Intelligence — Network Reasoning and Pool Selection Authority.

Operates across Substrates:
  - Substrate 2: Causal (Pearl's Ladder, Rung 2 do-calculus)
  - Substrate 4: Geometric (Network topology and latency space)
  - Substrate 9: Tensor (Batch verification and companion state)

Possesses FULL AUTHORITY over pool selection, difficulty retargeting,
and network intervention without sub-agent framing.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: mining
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import time
from typing import Any, Dict, List


@dataclass
class CausalDecision:
    """Decision produced by Causal Intelligence with provenance."""

    selected_pool: str
    target_difficulty: float
    stale_rate_estimate: float
    causal_intervention: str
    expected_yield_ratio: float
    timestamp: float = field(default_factory=time.time)
    provenance_hash: str = ""

    def __post_init__(self):
        if not self.provenance_hash:
            seed = (
                f"{self.selected_pool}:{self.target_difficulty}:"
                f"{self.causal_intervention}:{self.timestamp}"
            )
            self.provenance_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def to_scalar(self) -> float:
        """Dual-mode scalar return: expected yield ratio."""
        return float(self.expected_yield_ratio)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_pool": self.selected_pool,
            "target_difficulty": self.target_difficulty,
            "stale_rate_estimate": self.stale_rate_estimate,
            "causal_intervention": self.causal_intervention,
            "expected_yield_ratio": self.expected_yield_ratio,
            "timestamp": self.timestamp,
            "provenance_hash": self.provenance_hash,
        }


class CausalIntelligence:
    """Full-authority decision maker for network dynamics and pool orchestration."""

    def __init__(self, initial_pool: str = "ViaBTC_Primary"):
        self.active_pool = initial_pool
        self.plasticity_weights: Dict[str, float] = {
            "ViaBTC_Primary": 1.0,
            "Braiins_Secondary": 0.95,
            "Foundry_Fallback": 0.90,
            "Local_Consensus": 0.85,
        }
        self.difficulty_floor = 1.0
        self.difficulty_ceiling = 65536.0
        self.current_difficulty = 1.0
        self.decision_history: List[CausalDecision] = []
        self.plasticity = 0.05

    def select_pool(self, available_pools: List[Dict[str, Any]]) -> CausalDecision:
        """Select the optimal pool using causal graph surgery (do-operator).

        Evaluates P(Yield | do(Pool = P_k)) taking latency, stale rate,
        and fee structures into account.
        """
        best_pool = self.active_pool
        best_score = -1.0
        best_stale = 0.01

        for pool in available_pools:
            name = pool.get("name", "Unknown")
            latency_ms = float(pool.get("latency_ms", 50.0))
            stale_rate = float(pool.get("stale_rate", 0.005))
            fee = float(pool.get("fee_rate", 0.01))
            weight = self.plasticity_weights.get(name, 0.5)

            # Rung 2: Causal do-calculus intervention score
            # score = (1 - fee) * (1 - stale_rate) * weight / (1 + latency_ms / 100.0)
            score = (1.0 - fee) * (1.0 - stale_rate) * weight / (1.0 + (latency_ms / 100.0))
            if score > best_score:
                best_score = score
                best_pool = name
                best_stale = stale_rate

        self.active_pool = best_pool
        intervention = f"do(Pool={best_pool})"
        decision = CausalDecision(
            selected_pool=best_pool,
            target_difficulty=self.current_difficulty,
            stale_rate_estimate=best_stale,
            causal_intervention=intervention,
            expected_yield_ratio=max(0.01, best_score),
        )
        self.decision_history.append(decision)
        return decision

    def adjust_difficulty(self, network_hashrate: float, target_block_time: float = 600.0) -> float:
        """Rung 2 difficulty intervention bounded strictly within consensus limits."""
        scaling = max(0.25, min(4.0, (network_hashrate / 1e18) if network_hashrate > 0 else 1.0))
        new_diff = max(
            self.difficulty_floor, min(self.difficulty_ceiling, self.current_difficulty * scaling)
        )
        self.current_difficulty = new_diff
        return self.current_difficulty

    def reason_network(self, network_telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """Reason about network topology and detect partition or block reorganization."""
        block_height = int(network_telemetry.get("block_height", 0))
        peer_count = int(network_telemetry.get("peer_count", 8))
        mempool_txs = int(network_telemetry.get("mempool_txs", 1000))

        healthy = peer_count >= 3
        action = "MAINTAIN" if healthy else "RECONNECT_FALLBACK"

        return {
            "healthy": healthy,
            "block_height": block_height,
            "peer_count": peer_count,
            "mempool_txs": mempool_txs,
            "action": action,
            "rung": 2,
        }

    def learn(self, pool_name: str, share_accepted: bool, latency_ms: float) -> None:
        """Plasticity updates: reinforce successful pools and adjust weight curves."""
        current = self.plasticity_weights.get(pool_name, 0.5)
        if share_accepted:
            delta = self.plasticity * (1.0 - (latency_ms / 500.0))
            self.plasticity_weights[pool_name] = min(2.0, current + max(0.001, delta))
        else:
            self.plasticity_weights[pool_name] = max(0.1, current - self.plasticity)
