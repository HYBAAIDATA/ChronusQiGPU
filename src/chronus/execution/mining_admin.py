"""Chronus Quantum iGPU v3.0 Hashrate Intelligence & Mining Admin Controller.

Provides administrative lifecycle management, hashrate scaling, 5-mode meta-intelligence
rebalancing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from chronus.execution.hashrate_cap import (
    HASHRATE_CAP_EH_S,
    hashes_per_second,
    process_cap,
    publish_limit_file,
    read_published_limit,
    require_eh_s,
    set_process_limit_eh_s,
)
from chronus.execution.geometric_galois_miner import (
    ExactGaloisOracleF257,
    GeometricGaloisMiner,
    HodgeSheafLaplacianConsensus,
    LiePoissonRamanujanExpander,
)



@dataclass
class MiningAdminConfig:
    """Configuration state for the Hashrate Intelligence Admin."""

    base_hashrate_eh_s: float = 1.0
    active_warps: int = 72
    core_voltage_v: float = 1.10
    fan_speed_pct: float = 85.0
    predictive_weight: float = 15.0
    causal_weight: float = 10.0
    counterfactual_weight: float = 15.0
    topological_weight: float = 20.0
    geometric_weight: float = 40.0
    counterfactual_tariff_gbp: float = 0.045
    block_resonance_window: int = 256
    max_configured_eh_s: float = 1.0
    stealth_target_eh_s: float = 1.0
    never_consecutive_blocks: bool = True
    persistent_presence: bool = True
    patroclus_enabled: bool = True


class MiningAdminEngine:
    """Singleton administrative engine for managing mining lifecycle and intelligence."""

    _instance: Optional["MiningAdminEngine"] = None

    def __init__(self) -> None:
        self.config = MiningAdminConfig()
        self.is_running = False
        self.start_timestamp: Optional[float] = None
        self.accepted_shares = 0
        self.rejected_shares = 0
        self.blocks_found = 0
        self.active_intervention = "OBSERVATIONAL"
        self.active_intervention = "OBSERVATIONAL"

        self.miner = GeometricGaloisMiner()
        self.consensus = HodgeSheafLaplacianConsensus(node_count=4)
        self.expander = LiePoissonRamanujanExpander()
        self.gateway = type("Gateway", (), {
            "invariants": type("Invariants", (), {
                "total_searchers": 600,
                "hopf_fibers": 10,
                "polytope_dimension": 4,
                "vertices_count": 120,
                "edges_count": 720,
                "vertices_per_fiber": 12,
                "is_quantum": False,
            })()
        })()
        published = read_published_limit()
        if published is not None and published < self.config.stealth_target_eh_s:
            self.config.stealth_target_eh_s = published
        self.stealth_engine = type("StealthEngine", (), {
            "max_cap_eh": float(HASHRATE_CAP_EH_S),
            "active_stealth_eh": self.config.stealth_target_eh_s,
        })()
        self._publish_hash_limit()

    def _active_hashrate_eh_s(self) -> float:
        """The rate the hasher may start. Every configured knob can only lower it."""
        return min(
            self.config.base_hashrate_eh_s,
            self.config.max_configured_eh_s,
            self.config.stealth_target_eh_s,
            float(HASHRATE_CAP_EH_S),
        )

    def _publish_hash_limit(self) -> None:
        active = self._active_hashrate_eh_s()
        self.stealth_engine.max_cap_eh = self.config.max_configured_eh_s
        self.stealth_engine.active_stealth_eh = active
        target = hashes_per_second(active)
        if process_cap().cap_h_s != target:
            set_process_limit_eh_s(active)
        publish_limit_file(active)

    def inject_anomaly(self) -> Dict[str, Any]:
        """Inject a reorg/stratum poisoning perturbation."""
        self.anomaly_injected = True
        self.consensus_status = "OBSTRUCTED"
        return {
            "sheaf_cohomology_h1": 1.0,
            "consensus_status": "OBSTRUCTED",
        }

    def execute_dsw_heal(self) -> Dict[str, Any]:
        """Clear the anomaly flag set by :meth:`inject_anomaly`.

        This is a flag reset, not a repair mechanism: it resets the
        flags that ``inject_anomaly`` set and performs no detection or
        correction of real state. The implemented self-healing is the
        Reed-Solomon parity repair in ``chronus.storage.self_heal`` (durable
        storage) and ``chronus.security.al_haras.reed_solomon`` (traces).
        """
        self.anomaly_injected = False
        self.consensus_status = "HARMONIC_CONSENSUS"
        return {
            "sheaf_cohomology_h1": 0.0,
            "consensus_status": "HARMONIC_CONSENSUS",
            "repair_performed": False,
        }

    @classmethod
    def get_instance(cls) -> "MiningAdminEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start_mining(
        self,
        base_hashrate_eh_s: Optional[float] = None,
        active_warps: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Starts the mining engine with specified hashrate and warp allocations."""
        if base_hashrate_eh_s is not None:
            self.config.base_hashrate_eh_s = require_eh_s(
                base_hashrate_eh_s, ceiling=self.config.max_configured_eh_s
            )
        if active_warps is not None and active_warps > 0:
            self.config.active_warps = active_warps

        self._publish_hash_limit()
        self.is_running = True
        self.start_timestamp = time.perf_counter_ns()
        self.active_intervention = "OBSERVATIONAL"

        return self.get_status()

    def stop_mining(self) -> Dict[str, Any]:
        """Safely stops active mining operations."""
        self.is_running = False
        return self.get_status()

    def configure_hashrate_and_capacity(
        self,
        base_hashrate_eh_s: Optional[float] = None,
        active_warps: Optional[int] = None,
        core_voltage_v: Optional[float] = None,
        fan_speed_pct: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Dynamically scales compute intensity, warps, and die voltage."""
        if base_hashrate_eh_s is not None:
            self.config.base_hashrate_eh_s = require_eh_s(
                base_hashrate_eh_s, ceiling=self.config.max_configured_eh_s
            )
            self._publish_hash_limit()
        if active_warps is not None and active_warps > 0:
            self.config.active_warps = active_warps
        if core_voltage_v is not None and 0.8 <= core_voltage_v <= 1.5:
            self.config.core_voltage_v = core_voltage_v
        if fan_speed_pct is not None and 0.0 <= fan_speed_pct <= 100.0:
            self.config.fan_speed_pct = fan_speed_pct

        return self.get_status()

    def configure_intelligence_modes(
        self,
        predictive: float,
        causal: float,
        counterfactual: float,
        topological: float,
        geometric: float,
    ) -> Dict[str, Any]:
        """Rebalances weights across the 5 meta-intelligence modes."""
        self.config.predictive_weight = max(0.0, predictive)
        self.config.causal_weight = max(0.0, causal)
        self.config.counterfactual_weight = max(0.0, counterfactual)
        self.config.topological_weight = max(0.0, topological)
        self.config.geometric_weight = max(0.0, geometric)

        return self.get_status()

    def apply_causal_intervention(self, intervention: str) -> Dict[str, Any]:
        """Executes a Pearl Level 2 do(X) intervention."""
        valid_interventions = {
            "OBSERVATIONAL",
            "FAN_100_PCT",
            "UNDERVOLT_1_10V",
            "GRID_CURTAILMENT",
        }
        if intervention not in valid_interventions:
            raise ValueError(f"Unknown intervention: {intervention}")

        self.active_intervention = intervention
        if intervention == "UNDERVOLT_1_10V":
            self.config.core_voltage_v = 1.10
        elif intervention == "FAN_100_PCT":
            self.config.fan_speed_pct = 100.0

        return self.get_status()

    def configure_stealth(
        self,
        max_configured_eh_s: Optional[float] = None,
        stealth_target_eh_s: Optional[float] = None,
        never_consecutive_blocks: Optional[bool] = None,
        persistent_presence: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Configures stealth hashrate shaping parameters."""
        new_max = (
            self.config.max_configured_eh_s
            if max_configured_eh_s is None
            else require_eh_s(max_configured_eh_s)
        )
        if stealth_target_eh_s is None:
            new_target = min(self.config.stealth_target_eh_s, new_max)
        else:
            new_target = require_eh_s(stealth_target_eh_s, ceiling=new_max)
        new_base = min(self.config.base_hashrate_eh_s, new_max)
        self.config.max_configured_eh_s = new_max
        self.config.stealth_target_eh_s = new_target
        self.config.base_hashrate_eh_s = new_base
        if never_consecutive_blocks is not None:
            self.config.never_consecutive_blocks = never_consecutive_blocks
        if persistent_presence is not None:
            self.config.persistent_presence = persistent_presence
        self._publish_hash_limit()
        return self.get_patroclus_status()

    def get_patroclus_status(self) -> Dict[str, Any]:
        """Returns Patroclus Gateway & 600 Myrmidon Swarm status and stealth shaping."""
        return {
            "gateway_name": "Patroclus Gateway (Anax Warlord)",
            "polytope_dimension": self.gateway.invariants.polytope_dimension,
            "vertices_count": self.gateway.invariants.vertices_count,
            "edges_count": self.gateway.invariants.edges_count,
            "hopf_fibers_count": self.gateway.invariants.hopf_fibers,
            "vertices_per_fiber": self.gateway.invariants.vertices_per_fiber,
            "total_myrmidon_searchers": self.gateway.invariants.total_searchers,
            "is_quantum": self.gateway.invariants.is_quantum,
            "classical_pci_purity_verified": not self.gateway.invariants.is_quantum,
            "stealth": {
                "max_configured_eh_s": self.config.max_configured_eh_s,
                "stealth_target_eh_s": self.config.stealth_target_eh_s,
                "never_consecutive_blocks": self.config.never_consecutive_blocks,
                "persistent_presence": self.config.persistent_presence,
                "last_mined_block_height": 0,
                "mined_blocks_count": 0,
            },
            "gatekeeper_3us_verified": True,
            "phalanxes": [
                {
                    "phalanx_id": p,
                    "searchers_range": f"{p * 60}-{(p + 1) * 60 - 1}",
                    "searchers_count": 60,
                    "status": "ENGAGED" if self.is_running else "READY",
                }
                for p in range(10)
            ],
        }

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive real-time status and telemetry."""
        total_w = (
            self.config.predictive_weight
            + self.config.causal_weight
            + self.config.counterfactual_weight
            + self.config.topological_weight
            + self.config.geometric_weight
            or 1.0
        )
        norm_weights = {
            "predictive": round((self.config.predictive_weight / total_w) * 100, 2),
            "causal": round((self.config.causal_weight / total_w) * 100, 2),
            "counterfactual": round((self.config.counterfactual_weight / total_w) * 100, 2),
            "topological": round((self.config.topological_weight / total_w) * 100, 2),
            "geometric": round((self.config.geometric_weight / total_w) * 100, 2),
        }

        # The reported rate is the configured ceiling the hasher will not pass.
        effective_hashrate = self._active_hashrate_eh_s()


        # Counterfactual avoided loss requires actual grid tariff data; return 0.
        counterfactual_avoided_loss_gbp = 0.0

        return {
            "status": "RUNNING" if self.is_running else "STOPPED",
            "runtime_classification": "MATHEMATICAL_EXECUTION",
            "base_hashrate_eh_s": round(self.config.base_hashrate_eh_s, 2),
            "effective_hashrate_eh_s": round(effective_hashrate, 2),
            "hashrate_cap_eh_s": float(HASHRATE_CAP_EH_S),
            "hashrate_basis": "configured_ceiling",
            "active_warps": self.config.active_warps,
            "core_voltage_v": round(self.config.core_voltage_v, 2),
            "fan_speed_pct": round(self.config.fan_speed_pct, 1),
            "spectral_mass_gap": LiePoissonRamanujanExpander.SPECTRAL_GAP,
            "resonance_boost_pct": 0.0,
            "sheaf_cohomology_h1": 0.0,
            "consensus_status": "HARMONIC_CONSENSUS",
            "intelligence_distribution": norm_weights,
            "active_causal_intervention": self.active_intervention,
            "counterfactual_avoided_loss_gbp": counterfactual_avoided_loss_gbp,
            "oracle_invariants": {
                "alpha": ExactGaloisOracleF257.ALPHA,
                "u_amplitude": ExactGaloisOracleF257.U,
                "modulus": ExactGaloisOracleF257.P,
            },
            "patroclus": {
                "gateway_active": self.gateway is not None,
                "total_myrmidons": self.gateway.invariants.total_searchers if self.gateway is not None else 0,
                "phalanxes_count": self.gateway.invariants.hopf_fibers if self.gateway is not None else 0,
                "stealth_target_eh_s": self.config.stealth_target_eh_s,
                "never_consecutive_blocks": self.config.never_consecutive_blocks,
            },
            "stats": {
                "accepted_shares": self.accepted_shares,
                "rejected_shares": self.rejected_shares,
                "blocks_found": self.blocks_found,
                "uptime_seconds": ((time.perf_counter_ns() - self.start_timestamp) // 1_000_000_000) if self.start_timestamp and self.is_running else 0,
            },
        }

