"""Security Swarm Substrate — Cognitive Shard Entanglement & Integrity Verification.

Implements the canonical Python single-backend port of the Security Swarm
substrate (`SecuritySwarmAgent` / `SecuritySwarm`), providing dual cryptographic
state shards (`shard_a`, `shard_b`), cross-layer bitwise XOR entanglement with
mining entropy, counterfactual shard corruption detection, and swarm telemetry.

# LUCAS WIRING: draws from lucas/ (pool) only. MUST NOT import from any
# sibling Intelligence algorithm module.
# Substrate route: amplitude
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class SwarmTelemetryEvent:
    event_id: int
    kind: str
    severity: str
    detail: str
    irreducibility: float
    timestamp: float = field(default_factory=time.time)


class SecuritySwarmAgent:
    """Autonomous security swarm agent managing entangled cognitive shards A and B."""

    def __init__(self, shard_size: int = 32, seed: int = 0) -> None:
        if shard_size <= 0:
            raise ValueError("shard_size must be positive")
        self.shard_size = int(shard_size)
        self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)
        self._shard_a: np.ndarray = self.rng.integers(1, 255, size=self.shard_size, dtype=np.uint8)
        self._shard_b: np.ndarray = self.rng.integers(1, 255, size=self.shard_size, dtype=np.uint8)
        self._baseline_a: np.ndarray = self._shard_a.copy()
        self._baseline_b: np.ndarray = self._shard_b.copy()
        self._mining_entropy: np.ndarray = np.zeros(self.shard_size, dtype=np.uint8)
        self._mask: int = 0xAA
        self._entangled: bool = False
        self._corrupted: bool = False
        self.telemetry_log: List[SwarmTelemetryEvent] = []
        self._record_telemetry("SWARM_INIT", "INFO", "Security swarm initialized", 0.052)

    def _record_telemetry(
        self, kind: str, severity: str, detail: str, irreducibility: float
    ) -> SwarmTelemetryEvent:
        ev = SwarmTelemetryEvent(
            event_id=len(self.telemetry_log) + 1,
            kind=kind,
            severity=severity,
            detail=detail,
            irreducibility=float(irreducibility),
        )
        self.telemetry_log.append(ev)
        return ev

    def get_shard_a(self) -> np.ndarray:
        """Return a copy of security shard A (snake_case canonical)."""
        return self._shard_a.copy()

    def get_shard_b(self) -> np.ndarray:
        """Return a copy of security shard B (snake_case canonical)."""
        return self._shard_b.copy()

    # CamelCase aliases matching the original TypeScript Achievement Report API
    def getShardA(self) -> np.ndarray:  # noqa: N802
        return self.get_shard_a()

    def getShardB(self) -> np.ndarray:  # noqa: N802
        return self.get_shard_b()

    def entangle_with_mining(
        self, mining_entropy: np.ndarray | List[int], mask: int = 0xAA
    ) -> Dict[str, Any]:
        """XOR mining weights into security shards A and B:
        shardA[i] ^= miningEntropy[i] & mask
        shardB[i] ^= miningEntropy[i] & ~mask
        """
        ent = np.asarray(mining_entropy, dtype=np.uint8)
        if ent.size < self.shard_size:
            ent = np.resize(ent, self.shard_size)
        else:
            ent = ent[: self.shard_size]
        self._mining_entropy = ent.copy()
        self._mask = int(mask) & 0xFF
        inv_mask = (~self._mask) & 0xFF

        self._shard_a = np.bitwise_xor(self._baseline_a, np.bitwise_and(ent, self._mask))
        self._shard_b = np.bitwise_xor(self._baseline_b, np.bitwise_and(ent, inv_mask))
        self._entangled = True
        self._corrupted = False
        irred = self.measure_irreducibility()
        self._record_telemetry(
            "COGNITIVE_ENTANGLEMENT",
            "INFO",
            f"Shards entangled with mask 0x{self._mask:02x}",
            irred,
        )
        return {
            "entangled": True,
            "irreducibility": irred,
            "digest_a": hashlib.sha256(self._shard_a.tobytes()).hexdigest()[:16],
            "digest_b": hashlib.sha256(self._shard_b.tobytes()).hexdigest()[:16],
        }

    def reconstruct_mining_entropy(self) -> np.ndarray:
        """Reconstruct mining entropy from entangled shards A and B.
        If either shard is corrupted, reconstruction fails to match mining_entropy.
        """
        if not self._entangled:
            return np.zeros(self.shard_size, dtype=np.uint8)
        part_a = np.bitwise_xor(self._shard_a, self._baseline_a)
        part_b = np.bitwise_xor(self._shard_b, self._baseline_b)
        return np.bitwise_or(part_a, part_b)

    def verify_mining_integrity(self) -> bool:
        """Verify that mining entropy can be exactly recovered from security shards."""
        if not self._entangled:
            return not self._corrupted
        recovered = self.reconstruct_mining_entropy()
        valid = bool(np.array_equal(recovered, self._mining_entropy)) and not self._corrupted
        if not valid:
            self._record_telemetry(
                "MINING_INTEGRITY_FAILURE",
                "CRITICAL",
                "Corrupted security shard broke coupled mining operation",
                self.measure_irreducibility(),
            )
        return valid

    def corrupt_shard(self, shard: str = "A",flip_mask: int = 0xFF) -> None:
        """Inject counterfactual corruption into shard A or B to prove inseparability."""
        if shard.upper() == "A":
            self._shard_a = np.bitwise_xor(
                self._shard_a, np.uint8(int(flip_mask) & 0xFF)
            )
        else:
            self._shard_b = np.bitwise_xor(
                self._shard_b, np.uint8(int(flip_mask) & 0xFF)
            )
        self._corrupted = True
        self._record_telemetry(
            "SHARD_CORRUPTION_INJECTED",
            "WARNING",
            f"Shard {shard.upper()} corrupted",
            self.measure_irreducibility(),
        )

    def heal_shards(self) -> bool:
        """Restore shards from baseline and re-apply entanglement if active."""
        if self._entangled:
            self.entangle_with_mining(self._mining_entropy, self._mask)
        else:
            self._shard_a = self._baseline_a.copy()
            self._shard_b = self._baseline_b.copy()
            self._corrupted = False
        self._record_telemetry(
            "SHARD_HEALED",
            "INFO",
            "Security shards restored to entangled equilibrium",
            self.measure_irreducibility(),
        )
        return True

    def measure_irreducibility(self) -> float:
        """Compute empirical irreducibility score from bipartite bitmask cut capacity and bitwise reconstruction integrity."""
        if not self._entangled or self._mining_entropy is None:
            integrity_a = 1.0 - float(
                np.mean(np.unpackbits(np.bitwise_xor(self._shard_a, self._baseline_a)))
            )
            integrity_b = 1.0 - float(
                np.mean(np.unpackbits(np.bitwise_xor(self._shard_b, self._baseline_b)))
            )
            return round(0.0520 * integrity_a * integrity_b, 4)

        k_a = bin(self._mask & 0xFF).count("1")
        k_b = bin((~self._mask) & 0xFF).count("1")
        bipartite_capacity = ((k_a * k_b) / 64.0) * 2.25
        recovered = self.reconstruct_mining_entropy()
        bit_integrity = 1.0 - float(
            np.mean(np.unpackbits(np.bitwise_xor(recovered, self._mining_entropy)))
        )
        return round(float(np.clip(bipartite_capacity * bit_integrity, 0.0, 1.0)), 4)

    def snapshot(self) -> Dict[str, Any]:
        """Return complete diagnostic snapshot of the security swarm."""
        return {
            "schema": "intelligence.security_swarm/1",
            "shard_size": self.shard_size,
            "entangled": self._entangled,
            "corrupted": self._corrupted,
            "mining_integrity_ok": self.verify_mining_integrity() if not self._corrupted else False,
            "irreducibility": self.measure_irreducibility(),
            "shard_a": self._shard_a.tolist(),
            "shard_b": self._shard_b.tolist(),
            "telemetry_count": len(self.telemetry_log),
            "recent_telemetry": [t.__dict__.copy() for t in self.telemetry_log[-5:]],
        }


SecuritySwarm = SecuritySwarmAgent


def lucas_bound(n: int = 10) -> dict:
    from lucas.pool import get as _lucas_get

    result = _lucas_get("amplitude_kernel")([1.0, 1.0], n)
    result["module"] = __name__
    return result


__all__ = [
    "SecuritySwarm",
    "SecuritySwarmAgent",
    "SwarmTelemetryEvent",
    "lucas_bound",
]
