"""
HYBA SOFTWARE LTD
Core Intelligence Infrastructure - Intelligence Bus
==================================================
Author  : Andre Taylor-Morris, Founder & CEO
Date    : March 2026
Status  : Production Implementation
Classification: Most Sensitive — Internal Engineering

System-level intelligence: endpoints talking to each other.
The bus is not a message queue. It is a shared cognitive layer.
"""

import logging
import time
from collections import deque
from typing import Any

import numpy as np

from .intelligent_endpoint import IntelligentEndpoint, LearningSignal

logger = logging.getLogger("hyba.intelligence.bus")


class IntelligenceBus:
    """Shared intelligence layer connecting endpoint cognition."""

    def __init__(self):
        self.endpoints: dict[str, IntelligentEndpoint] = {}
        self.message_log: deque = deque(maxlen=10000)
        self.system_phi: deque = deque(maxlen=1000)
        self.shared_mining_priors: dict[str, dict[str, Any]] = {}

    def register(self, endpoint: IntelligentEndpoint) -> None:
        """Register an endpoint on the bus."""
        endpoint._bus = self
        self.endpoints[endpoint.endpoint_id] = endpoint
        logger.info(
            f"[BUS] Registered {endpoint.endpoint_id} "
            f"({type(endpoint).__name__}). "
            f"Total endpoints: {len(self.endpoints)}"
        )

    async def broadcast(
        self,
        sender_id: str,
        signal: LearningSignal,
    ) -> None:
        """Broadcast a learning signal to all relevant endpoints."""
        self.message_log.append(
            {
                "sender": sender_id,
                "signal": signal.__dict__,
                "timestamp": time.time(),
            }
        )

        if signal.phi_resonance >= 0.5:
            for eid, endpoint in self.endpoints.items():
                if eid != sender_id:
                    try:
                        await self._relay_signal(endpoint, sender_id, signal)
                    except Exception as e:
                        logger.error(f"[BUS] Relay to {eid} failed: {e}")

    async def _relay_signal(
        self,
        endpoint: IntelligentEndpoint,
        sender_id: str,
        signal: LearningSignal,
    ) -> None:
        """Relay a signal to an endpoint in a form it can use."""
        endpoint._update_phi_profile(signal.phi_resonance)
        if hasattr(endpoint, "receive_peer_signal"):
            endpoint.receive_peer_signal(sender_id, signal)
        logger.debug(
            f"[BUS] Relayed signal from {sender_id} to "
            f"{endpoint.endpoint_id}: phi={signal.phi_resonance:.3f}"
        )

    def share_priors_with_mining(
        self,
        mining_endpoint_id: str,
        priors: dict[str, Any],
        source_endpoint_id: str | None = None,
    ) -> dict[str, Any]:
        """Exchange priors bidirectionally between mining and other intelligence endpoints."""
        source = source_endpoint_id or mining_endpoint_id
        self.shared_mining_priors[source] = dict(priors)

        merged = self._merge_mining_priors()
        mining_endpoint = self.endpoints.get(mining_endpoint_id)
        if mining_endpoint and hasattr(mining_endpoint, "share_priors_with_mining"):
            merged = mining_endpoint.share_priors_with_mining(merged)

        for endpoint_id, endpoint in self.endpoints.items():
            if endpoint_id == mining_endpoint_id:
                continue
            if hasattr(endpoint, "receive_mining_priors"):
                endpoint.receive_mining_priors(merged)

        self.shared_mining_priors[mining_endpoint_id] = merged
        return merged

    def _merge_mining_priors(self) -> dict[str, Any]:
        """Merge observed mining priors from all contributors."""
        if not self.shared_mining_priors:
            return {
                "phi_prior": 0.7,
                "strategy_weights": {},
                "phi_grover_hit_rate": 0.0,
                "emergent_phi_convergence": 0.0,
            }

        phi_values = [
            float(payload.get("phi_prior", 0.7))
            for payload in self.shared_mining_priors.values()
            if isinstance(payload, dict)
        ]
        phi_prior = float(np.mean(phi_values)) if phi_values else 0.7

        strategy_weights: dict[str, list[float]] = {}
        for payload in self.shared_mining_priors.values():
            weights = payload.get("strategy_weights", {}) if isinstance(payload, dict) else {}
            for strategy, weight in weights.items():
                strategy_weights.setdefault(str(strategy), []).append(float(weight))

        merged_weights = {
            strategy: float(np.mean(values))
            for strategy, values in strategy_weights.items()
            if values
        }

        def _mean_key(key: str, default: float = 0.0) -> float:
            values = [
                float(payload.get(key, default))
                for payload in self.shared_mining_priors.values()
                if isinstance(payload, dict) and key in payload
            ]
            return float(np.mean(values)) if values else default

        return {
            "phi_prior": phi_prior,
            "strategy_weights": merged_weights,
            "phi_grover_hit_rate": _mean_key("phi_grover_hit_rate", 0.0),
            "emergent_phi_convergence": _mean_key("emergent_phi_convergence", 0.0),
        }

    def get_emergent_intelligence_state(self) -> dict[str, Any]:
        """Report whether bus connectivity and phi flow reached emergent operation."""
        report = self.system_intelligence_report()
        endpoint_count = report["total_endpoints"]
        high_phi_messages = report["high_phi_messages"]
        connectivity_ratio = endpoint_count / max(endpoint_count + 1, 1) if endpoint_count else 0.0

        emergent = bool(
            endpoint_count >= 2 and report["system_phi"] >= 0.5 and high_phi_messages >= 1
        )
        return {
            "emergent": emergent,
            "endpoint_count": endpoint_count,
            "connectivity_ratio": float(connectivity_ratio),
            "system_phi": float(report["system_phi"]),
            "high_phi_messages": int(high_phi_messages),
            "system_phi_trend": report["system_phi_trend"],
        }

    def system_intelligence_report(self) -> dict[str, Any]:
        """Generate a system-level intelligence report."""
        summaries = [ep.working_memory_summary() for ep in self.endpoints.values()]
        phi_values = [float(s["phi_resonance"]) for s in summaries]
        system_phi = float(np.mean(phi_values)) if phi_values else 0.0

        history = list(self.system_phi)
        system_phi_trend = "stable"
        if len(history) >= 10:
            recent = history[-5:]
            earlier = history[:-5]
            earlier_mean = float(np.mean(earlier)) if earlier else float(np.mean(history[-10:-5]))
            recent_mean = float(np.mean(recent))
            if recent_mean > earlier_mean:
                system_phi_trend = "improving"

        self.system_phi.append(system_phi)

        return {
            "timestamp": time.time(),
            "total_endpoints": len(self.endpoints),
            "system_phi": system_phi,
            "system_in_structure": bool(system_phi >= 0.5),
            "endpoint_summaries": summaries,
            "message_volume": len(self.message_log),
            "high_phi_messages": sum(
                1 for m in self.message_log if m["signal"].get("phi_resonance", 0) >= 0.5
            ),
            "system_phi_trend": system_phi_trend,
        }
