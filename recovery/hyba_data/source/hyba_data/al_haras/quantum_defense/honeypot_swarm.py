"""Quantum Honeypot Swarm — observation-driven, idempotent decoy mesh."""
from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

PHI = (1 + math.sqrt(5)) / 2


@dataclass
class HoneypotState:
    id: str
    htype: str
    observed_attacks: List[Dict] = field(default_factory=list)
    attack_signature: str = ""
    compromised: bool = False


class QuantumHoneypotSwarm:
    """Honeypot swarm that only marks compromise on real observation input."""

    def __init__(self):
        self.honeypots: List[HoneypotState] = []
        self.attack_signatures: Dict[str, int] = {}
        self._deployed = False
        self._deploy_n = 0

    def deploy(self, n: int = 100) -> Dict[str, Any]:
        """Idempotent deploy — repeated calls do not double the mesh."""
        n = int(n)
        if n <= 0:
            raise ValueError("n must be positive")
        if self._deployed:
            return {
                "status": "ALREADY_DEPLOYED",
                "total": len(self.honeypots),
                "requested": n,
                "reported": self._deploy_n,
            }
        types = ["quantum_simulation", "classical_decoy", "entanglement_trap"]
        for i in range(n):
            self.honeypots.append(HoneypotState(id=f"hp_{i}", htype=types[i % 3]))
        self._deployed = True
        self._deploy_n = n
        return {"status": "DEPLOYED", "total": len(self.honeypots), "reported": n}

    def monitor(self, observations: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Without observations, nothing is compromised. Random self-fire is forbidden."""
        if not self.honeypots:
            return {"total": 0, "compromised": 0, "signatures": 0, "status": "NOT_DEPLOYED"}

        if not observations:
            return {
                "total": len(self.honeypots),
                "compromised": sum(1 for h in self.honeypots if h.compromised),
                "signatures": len(self.attack_signatures),
                "status": "IDLE_NO_OBSERVATION",
            }

        for obs in observations:
            hp_id = str(obs.get("honeypot_id") or obs.get("id") or "")
            signal = str(obs.get("signal") or obs.get("payload") or obs.get("type") or "")
            if not signal and not hp_id:
                continue
            targets = [h for h in self.honeypots if h.id == hp_id] if hp_id else list(self.honeypots)
            if hp_id and not targets:
                continue
            # if id omitted, map by type or first matching idle pot of compatible type
            if not hp_id:
                htype = str(obs.get("htype") or obs.get("type") or "")
                candidates = [h for h in self.honeypots if not h.compromised and (not htype or h.htype == htype)]
                targets = candidates[:1] if candidates else []
            for hp in targets:
                if not self._is_probe_signal(signal, hp):
                    continue
                sig = hashlib.sha256(
                    f"{hp.id}|{hp.htype}|{signal}|{obs.get('source', '')}".encode()
                ).hexdigest()[:16]
                hp.attack_signature = sig
                hp.compromised = True
                self.attack_signatures[sig] = self.attack_signatures.get(sig, 0) + 1
                hp.observed_attacks.append(
                    {"timestamp": time.time(), "signature": sig, "type": hp.htype, "signal": signal[:128]}
                )

        compromised = sum(1 for h in self.honeypots if h.compromised)
        return {
            "total": len(self.honeypots),
            "compromised": compromised,
            "signatures": len(self.attack_signatures),
            "status": "OBSERVED",
        }

    def _is_probe_signal(self, signal: str, hp: HoneypotState) -> bool:
        if not signal or not str(signal).strip():
            return False
        s = signal.lower()
        markers = (
            "probe", "scan", "exploit", "quantum_measure", "collapse", "entangle",
            "inject", "fuzz", "c2", "beacon", "attack",
        )
        if any(m in s for m in markers):
            return True
        # high-entropy binary-ish observation still counts if directed at pot
        return len(s) >= 8 and hp.id in s
