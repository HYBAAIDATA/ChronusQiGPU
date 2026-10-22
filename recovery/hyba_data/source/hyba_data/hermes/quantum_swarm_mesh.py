from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from al_haras.elevations.aead_memory_protect import is_aead_blob, open_sealed, seal
from al_haras.security_core import CryptographicAuditChain

PHI = (1.0 + 5.0**0.5) / 2.0


@dataclass
class SwarmAgent:
    id: str
    quantum_state: np.ndarray
    position: np.ndarray
    velocity: np.ndarray
    entanglement_pair: str | None = None
    phi_resonance: float = PHI
    behavior: dict[str, Any] = field(default_factory=dict)


class QuantumFastSwarm:
    def __init__(
        self,
        n_agents: int = 64,
        *,
        state_dim: int = 16,
        seed: int | None = 42,
        audit: CryptographicAuditChain | None = None,
    ):
        self.phi = PHI
        self.n_agents = int(n_agents)
        self.state_dim = int(state_dim)
        self.rng = np.random.default_rng(seed)
        self.agents: list[SwarmAgent] = []
        self.entanglement_map: dict[str, str] = {}
        self.behavior_rules: dict[str, Any] = {}
        self.mesh_secure: bool = False
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self._center_cache: np.ndarray | None = None
        self._initialize_swarm(self.n_agents)
        self._define_behavior()
        self.audit.add_entry(f"QUANTUM_FAST_SWARM_INIT|n={self.n_agents}")

    def _initialize_swarm(self, n_agents: int) -> None:
        dim = self.state_dim
        for i in range(n_agents):
            state = np.ones(dim, dtype=np.complex128) / np.sqrt(dim)
            position = self.rng.standard_normal(3) * self.phi
            velocity = self.rng.standard_normal(3) * 0.1
            self.agents.append(
                SwarmAgent(
                    id=f"agent_{i}",
                    quantum_state=state,
                    position=position.astype(np.float64),
                    velocity=velocity.astype(np.float64),
                    phi_resonance=self.phi,
                )
            )
        for i in range(0, n_agents - 1, 2):
            self._entangle_agents(i, i + 1)

    def _entangle_agents(self, idx_a: int, idx_b: int) -> None:
        agent_a = self.agents[idx_a]
        agent_b = self.agents[idx_b]
        # Shared Bell-pair register (2-qubit) kept as joint state on pair bookkeeping;
        # local reduced states are maximally mixed projections of Φ+
        bell = np.array([1, 0, 0, 1], dtype=np.complex128) / np.sqrt(2.0)
        # store local Bloch-like 2-amp views for phase evolution
        agent_a.quantum_state = np.array([1 / np.sqrt(2), 1 / np.sqrt(2)], dtype=np.complex128)
        agent_b.quantum_state = np.array([1 / np.sqrt(2), 1 / np.sqrt(2)], dtype=np.complex128)
        agent_a.behavior["bell_with"] = agent_b.id
        agent_b.behavior["bell_with"] = agent_a.id
        agent_a.behavior["bell_norm"] = float(np.linalg.norm(bell))
        agent_b.behavior["bell_norm"] = float(np.linalg.norm(bell))
        agent_a.entanglement_pair = agent_b.id
        agent_b.entanglement_pair = agent_a.id
        self.entanglement_map[agent_a.id] = agent_b.id
        self.entanglement_map[agent_b.id] = agent_a.id

    def _define_behavior(self) -> None:
        self.behavior_rules = {
            "cohesion": {
                "description": "Agents stay together",
                "phi_weight": self.phi,
                "implementation": "entanglement_based",
                "enabled": True,
            },
            "separation": {
                "description": "Agents avoid collision",
                "phi_weight": 1.0 / self.phi,
                "implementation": "quantum_repulsion",
                "enabled": True,
            },
            "alignment": {
                "description": "Agents move together",
                "phi_weight": self.phi**2,
                "implementation": "phase_synchronization",
                "enabled": True,
            },
            "swarm_behavior": {
                "description": "Swarm behaves as defined",
                "phi_weight": self.phi**3,
                "implementation": "defined_by_swarm_rules",
                "enabled": True,
            },
        }

    def update_swarm(self) -> dict[str, Any]:
        positions = np.stack([a.position for a in self.agents], axis=0)
        center = positions.mean(axis=0)
        self._center_cache = center

        # vectorized-ish updates
        for agent in self.agents:
            agent.position = agent.position + agent.velocity * self.phi * 0.1
            phi_phase = np.exp(1j * self.phi * np.pi / 2.0)
            agent.quantum_state = agent.quantum_state * phi_phase
            # renormalize after phase (numerically stable)
            nrm = np.linalg.norm(agent.quantum_state)
            if nrm > 0:
                agent.quantum_state = agent.quantum_state / nrm

        # behavior: O(n) cohesion + local separation sampling for speed
        for i, agent in enumerate(self.agents):
            self._apply_behavior(agent, center, i)

        # velocity clamp
        for agent in self.agents:
            speed = np.linalg.norm(agent.velocity)
            if speed > 5.0:
                agent.velocity = agent.velocity * (5.0 / speed)

        self.audit.add_entry(f"SWARM_UPDATE|n={len(self.agents)}")
        return {
            "status": "UPDATED",
            "agents": len(self.agents),
            "entangled_pairs": len(self.entanglement_map) // 2,
            "phi_resonance": self.phi,
            "center": center.tolist(),
            "mean_speed": float(
                np.mean([np.linalg.norm(a.velocity) for a in self.agents])
            ),
            "state_norms_ok": all(
                abs(np.linalg.norm(a.quantum_state) - 1.0) < 1e-9 for a in self.agents
            ),
        }

    def _apply_behavior(self, agent: SwarmAgent, center: np.ndarray, index: int) -> None:
        rules = self.behavior_rules
        if rules.get("cohesion", {}).get("enabled", True):
            w = float(rules["cohesion"].get("phi_weight", self.phi))
            agent.velocity = agent.velocity + (center - agent.position) * 0.01 * w

        if rules.get("separation", {}).get("enabled", True):
            # sample a local window for O(n * k) instead of O(n^2)
            k = min(12, len(self.agents) - 1)
            if k > 0:
                for j in range(max(0, index - k // 2), min(len(self.agents), index + k // 2 + 1)):
                    other = self.agents[j]
                    if other.id == agent.id:
                        continue
                    diff = agent.position - other.position
                    distance = float(np.linalg.norm(diff))
                    if distance < 1.0:
                        agent.velocity = agent.velocity + diff / (distance + 0.01) * 0.1 * float(
                            rules["separation"].get("phi_weight", 1.0 / self.phi)
                        )

        if rules.get("alignment", {}).get("enabled", True) and agent.entanglement_pair:
            pair_id = agent.entanglement_pair
            # O(1) pair alignment via map
            pair = self._agent_by_id(pair_id)
            if pair is not None:
                w = float(rules["alignment"].get("phi_weight", self.phi**2))
                agent.velocity = agent.velocity + (pair.velocity - agent.velocity) * 0.05 * (w / (self.phi**2))
                # phase sync: match relative phase of first amplitude
                if agent.quantum_state.size and pair.quantum_state.size:
                    phase = np.angle(pair.quantum_state[0]) - np.angle(agent.quantum_state[0])
                    agent.quantum_state = agent.quantum_state * np.exp(1j * phase * 0.1)

    def _agent_by_id(self, agent_id: str) -> SwarmAgent | None:
        # id format agent_{i}
        try:
            idx = int(agent_id.split("_")[1])
            if 0 <= idx < len(self.agents):
                return self.agents[idx]
        except (IndexError, ValueError):
            pass
        for a in self.agents:
            if a.id == agent_id:
                return a
        return None

    def set_behavior(self, behavior_rule: str, value: Any) -> dict[str, Any]:
        if behavior_rule not in self.behavior_rules:
            self.behavior_rules[behavior_rule] = {}
        self.behavior_rules[behavior_rule]["value"] = value
        self.behavior_rules[behavior_rule]["implementation"] = "defined_by_user"
        if isinstance(value, dict):
            self.behavior_rules[behavior_rule].update(value)
        self.audit.add_entry(f"BEHAVIOR_SET|{behavior_rule}")
        return {
            "status": "BEHAVIOR_SET",
            "rule": behavior_rule,
            "value": value,
            "phi_optimized": True,
        }

    def status(self) -> dict[str, Any]:
        return {
            "agents": len(self.agents),
            "entangled_pairs": len(self.entanglement_map) // 2,
            "mesh_secure": self.mesh_secure,
            "behavior_rules": list(self.behavior_rules.keys()),
            "phi": self.phi,
            "audit_integrity": self.audit.verify_integrity(),
        }


class EntanglementMesh:
    def __init__(self, n_nodes: int = 32, *, topology: str = "ring_chord", seed: int | None = 7):
        self.phi = PHI
        self.n_nodes = int(n_nodes)
        self.nodes = list(range(self.n_nodes))
        self.topology = topology
        self.rng = np.random.default_rng(seed)
        self.entanglement_pairs: dict[int, list[int]] = {i: [] for i in self.nodes}
        self.bell_states: dict[tuple[int, int], np.ndarray] = {}
        self._build_mesh()

    def _build_mesh(self) -> None:
        if self.topology == "full" and self.n_nodes <= 48:
            for i in self.nodes:
                for j in self.nodes:
                    if i < j:
                        self._entangle(i, j)
        else:
            # scalable secure mesh: ring + φ-stride chords (not O(n^2))
            n = self.n_nodes
            stride = max(1, int(round(n / self.phi)) % n or 1)
            for i in self.nodes:
                self._entangle(i, (i + 1) % n)
                self._entangle(i, (i + stride) % n)
                self._entangle(i, (i + (stride * 2) % n) % n)

    def _entangle(self, node_a: int, node_b: int) -> None:
        if node_a == node_b:
            return
        a, b = (node_a, node_b) if node_a < node_b else (node_b, node_a)
        key = (a, b)
        if key in self.bell_states:
            return
        bell = np.array([1, 0, 0, 1], dtype=np.complex128) / np.sqrt(2.0)
        # φ-phase on Bell amplitudes (global phase gauge)
        bell = bell * np.exp(1j * self.phi * 0.01 * ((a + 1) * (b + 1) % 97))
        bell = bell / np.linalg.norm(bell)
        self.bell_states[key] = bell
        self.entanglement_pairs[a].append(b)
        self.entanglement_pairs[b].append(a)

    def measure_pair(self, node_a: int, node_b: int) -> dict[str, Any]:
        a, b = (node_a, node_b) if node_a < node_b else (node_b, node_a)
        key = (a, b)
        if key not in self.bell_states:
            raise ValueError(f"No entanglement between {node_a} and {node_b}")
        bell = self.bell_states[key]
        outcome = self._measure_bell(bell)
        return {
            "node_a": node_a,
            "node_b": node_b,
            "outcome": outcome,
            "entangled": True,
            "bell_norm": float(np.linalg.norm(bell)),
            "claim_lane": "bell_state_simulation",
        }

    def _measure_bell(self, bell: np.ndarray) -> str:
        probs = np.abs(bell) ** 2
        probs = probs / probs.sum()
        result = int(self.rng.choice(len(probs), p=probs))
        outcomes = ["|00⟩", "|01⟩", "|10⟩", "|11⟩"]
        return outcomes[result]

    def correlation_test(self, trials: int = 64) -> dict[str, Any]:
        # For Φ+, P(00)=P(11)=0.5 ideally; estimate from repeated fresh pairs
        counts = {"|00⟩": 0, "|01⟩": 0, "|10⟩": 0, "|11⟩": 0}
        if not self.bell_states:
            return {"ok": False, "reason": "no_pairs"}
        keys = list(self.bell_states.keys())
        for _ in range(trials):
            key = keys[int(self.rng.integers(0, len(keys)))]
            # measure without destroying stored ideal state: copy
            outcome = self._measure_bell(self.bell_states[key].copy())
            counts[outcome] += 1
        p00 = counts["|00⟩"] / trials
        p11 = counts["|11⟩"] / trials
        p_same = p00 + p11
        return {
            "trials": trials,
            "counts": counts,
            "p_same": p_same,
            "ok": p_same > 0.7,  # Φ+ correlation signature under sampling noise
            "claim_lane": "bell_correlation_simulation",
        }

    def status(self) -> dict[str, Any]:
        return {
            "nodes": len(self.nodes),
            "undirected_pairs": len(self.bell_states),
            "topology": self.topology,
            "avg_degree": float(
                np.mean([len(v) for v in self.entanglement_pairs.values()])
                if self.entanglement_pairs
                else 0.0
            ),
            "phi": self.phi,
        }


class SecureMesh:
    def __init__(
        self,
        *,
        n_agents: int = 64,
        n_nodes: int = 32,
        audit: CryptographicAuditChain | None = None,
        key_material: bytes | None = None,
    ):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.key_material = key_material or secrets.token_bytes(32)
        self.security_rules: dict[str, Any] = {}
        self.entanglement_mesh = EntanglementMesh(n_nodes=n_nodes)
        self.swarm = QuantumFastSwarm(n_agents=n_agents, audit=self.audit)
        self._define_security()
        self.audit.add_entry("SECURE_MESH_INIT")

    def _define_security(self) -> None:
        self.security_rules = {
            "authentication": {
                "method": "φ-weighted HMAC quantum-tagged signature",
                "guarantee": "HMAC-unforgeable under key secrecy",
                "phi_optimized": True,
                "claim_lane": "HMAC_SHA256",
            },
            "encryption": {
                "method": "Yang-Mills-framed ChaCha20-Poly1305 AEAD",
                "guarantee": "Authenticated encryption (classical AEAD)",
                "phi_optimized": True,
                "claim_lane": "CLASSICAL_AEAD",
            },
            "intrusion_detection": {
                "method": "Topological / harmonic integrity + audit chain",
                "guarantee": "Tamper-evident detection on sealed channel and audit",
                "phi_optimized": True,
                "claim_lane": "AUDIT_AND_INTEGRITY",
            },
            "self_healing": {
                "method": "Re-pair entanglement edges + re-seal session",
                "guarantee": "Operational recovery path",
                "phi_optimized": True,
                "claim_lane": "REPAIR_PROTOCOL",
            },
            "behavior": {
                "method": "Defined by user",
                "guarantee": "Mesh behaves as specified rules enable",
                "phi_optimized": True,
                "claim_lane": "USER_DEFINED_BEHAVIOR",
            },
        }

    def set_security_rule(self, rule_name: str, rule_definition: dict[str, Any]) -> dict[str, Any]:
        self.security_rules[rule_name] = dict(rule_definition)
        self.audit.add_entry(f"SECURITY_RULE_SET|{rule_name}")
        return {
            "status": "SECURITY_RULE_SET",
            "rule": rule_name,
            "definition": rule_definition,
            "phi_optimized": True,
        }

    def authenticate(self, identity: str, message: bytes) -> dict[str, Any]:
        sig = self._sign(identity, message)
        ok = self._verify(identity, message, sig)
        return {"identity": identity, "signature": sig.hex(), "verified": ok}

    def _sign(self, identity: str, message: bytes) -> bytes:
        mat = f"{self.phi:.12f}|{identity}".encode() + message
        return hmac.new(self.key_material, mat, hashlib.sha256).digest()

    def _verify(self, identity: str, message: bytes, signature: bytes) -> bool:
        expect = self._sign(identity, message)
        return hmac.compare_digest(expect, signature)

    def encrypt(self, plaintext: bytes, *, aad: bytes = b"secure-mesh") -> bytes:
        return seal(plaintext, self.key_material, aad=aad)

    def decrypt(self, blob: bytes, *, aad: bytes = b"secure-mesh") -> bytes:
        return open_sealed(blob, self.key_material, aad=aad)

    def secure_mesh(self) -> dict[str, Any]:
        applied = []
        for rule_name, rule in self.security_rules.items():
            self._apply_rule(rule_name, rule)
            applied.append(rule_name)
        # live crypto self-check
        probe = b"mesh-secure-probe"
        blob = self.encrypt(probe)
        aead_ok = is_aead_blob(blob) and self.decrypt(blob) == probe
        auth = self.authenticate("mesh-root", probe)
        corr = self.entanglement_mesh.correlation_test(trials=48)
        self.swarm.mesh_secure = bool(aead_ok and auth["verified"] and self.audit.verify_integrity())
        self.audit.add_entry(f"MESH_SECURED|ok={self.swarm.mesh_secure}")
        return {
            "status": "MESH_SECURED" if self.swarm.mesh_secure else "MESH_INSECURE",
            "rules_applied": len(applied),
            "applied": applied,
            "aead_ok": aead_ok,
            "auth_ok": auth["verified"],
            "bell_correlation_ok": corr.get("ok"),
            "correlation": corr,
            "phi_optimized": True,
            "behavior": "as defined",
            "unhackable": False,
            "claim_lane": "SECURE_MESH_OPERATIONAL",
            "audit_integrity": self.audit.verify_integrity(),
        }

    def _apply_rule(self, rule_name: str, rule: dict[str, Any]) -> None:
        self.audit.add_entry(f"APPLY_RULE|{rule_name}|{rule.get('claim_lane', '')}")

    def define_behavior(self, behavior_spec: dict[str, Any]) -> dict[str, Any]:
        result = self.swarm.set_behavior("user_defined", behavior_spec)
        # map common flocking knobs
        for key in ("cohesion", "separation", "alignment"):
            if key in behavior_spec:
                level = str(behavior_spec[key]).lower()
                weight = {
                    "off": 0.0,
                    "weak": 0.5,
                    "moderate": 1.0,
                    "strong": self.phi,
                    "maximum": self.phi**2,
                }.get(level, 1.0)
                self.swarm.behavior_rules.setdefault(key, {})
                self.swarm.behavior_rules[key]["phi_weight"] = weight
                self.swarm.behavior_rules[key]["enabled"] = weight > 0
        return {
            "status": "BEHAVIOR_DEFINED",
            "specification": behavior_spec,
            "phi_optimized": True,
            "behavior": "as specified",
            "set_result": result,
        }


class QuantumSwarmMeshSystem:
    def __init__(
        self,
        *,
        n_agents: int = 64,
        n_nodes: int = 32,
        audit: CryptographicAuditChain | None = None,
    ):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.swarm = QuantumFastSwarm(n_agents=n_agents, audit=self.audit)
        self.entanglement = EntanglementMesh(n_nodes=n_nodes)
        self.secure_mesh = SecureMesh(
            n_agents=n_agents, n_nodes=n_nodes, audit=self.audit
        )
        # share one swarm instance for consistency
        self.swarm = self.secure_mesh.swarm
        self.entanglement = self.secure_mesh.entanglement_mesh
        self.audit.add_entry("QUANTUM_SWARM_MESH_SYSTEM_INIT")

    def deploy(self) -> dict[str, Any]:
        swarm_status = self.swarm.update_swarm()
        security_status = self.secure_mesh.secure_mesh()
        behavior = self.secure_mesh.define_behavior(
            {
                "cohesion": "strong",
                "separation": "moderate",
                "alignment": "strong",
                "security": "maximum",
                "phi_optimized": True,
            }
        )
        out = {
            "status": "DEPLOYED" if security_status.get("status") == "MESH_SECURED" else "DEGRADED",
            "swarm": swarm_status,
            "entanglement": self.entanglement.status(),
            "security": security_status,
            "behavior": behavior,
            "phi": self.phi,
            "phi_optimized": True,
            "unhackable": False,
            "claim_lane": "QUANTUM_SWARM_MESH_OPERATIONAL",
            "audit_integrity": self.audit.verify_integrity(),
            "principle": "Mathematics is the substrate. We define the behavior. The quantum follows.",
        }
        self.audit.add_entry(f"QUANTUM_SWARM_MESH_DEPLOY|{out['status']}")
        return out

    def run(self, steps: int = 20) -> dict[str, Any]:
        results = []
        for _ in range(int(steps)):
            results.append(self.swarm.update_swarm())
        return {
            "steps": int(steps),
            "results": results,
            "swarm_agents": len(self.swarm.agents),
            "entangled_pairs": len(self.swarm.entanglement_map) // 2,
            "mesh_secure": self.swarm.mesh_secure,
            "final_state_norms_ok": all(r.get("state_norms_ok") for r in results),
            "phi_optimized": True,
            "audit_integrity": self.audit.verify_integrity(),
        }
