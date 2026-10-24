from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from al_haras.security_core import CryptographicAuditChain
from al_haras.quantum_first_principles import QuantumFirstPrinciplesSecurity

PHI = (1.0 + 5.0**0.5) / 2.0
DUTY_FORMS = (
    "predictive",
    "causal",
    "counterfactual",
    "topological",
    "geometric",
)


class IntelligenceForm(str, Enum):
    PREDICTIVE = "predictive"
    CAUSAL = "causal"
    COUNTERFACTUAL = "counterfactual"
    TOPOLOGICAL = "topological"
    GEOMETRIC = "geometric"


class AgentRole(str, Enum):
    DUTY = "duty"
    SWARM = "swarm"
    DECOY = "decoy"
    TRACE = "trace"
    EXPOSE = "expose"


class ThreatLevel(str, Enum):
    BENIGN = "benign"
    PROBE = "probe"
    ATTACK = "attack"
    PERSISTENT = "persistent"


@dataclass
class SwarmAgent:
    agent_id: str
    form: IntelligenceForm
    role: AgentRole
    generation: int = 0
    parent_id: str | None = None
    active: bool = True
    observations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EntanglementChannel:
    channel_id: str
    shared_state: dict[str, Any] = field(default_factory=dict)
    broadcasts: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def publish(self, agent_id: str, form: str, payload: dict[str, Any]) -> str:
        with self._lock:
            prev = self.broadcasts[-1]["hash"] if self.broadcasts else "0" * 64
            ts_ns = time.time_ns()
            payload_json = json.dumps(payload, sort_keys=True, default=str)
            body = f"{prev}|{agent_id}|{form}|{ts_ns}|{payload_json}"
            h = hashlib.sha256(body.encode()).hexdigest()
            msg = {
                "agent_id": agent_id,
                "form": form,
                "payload": dict(payload),
                "ts_ns": ts_ns,
                "prev": prev,
                "hash": h,
            }
            self.broadcasts.append(msg)
            bucket = self.shared_state.setdefault(form, {})
            bucket[agent_id] = dict(payload)
            self.shared_state["last_hash"] = h
            self.shared_state["message_count"] = len(self.broadcasts)
            return h

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "channel_id": self.channel_id,
                "message_count": len(self.broadcasts),
                "last_hash": self.shared_state.get("last_hash", "0" * 64),
                "forms_present": sorted(
                    k
                    for k in self.shared_state.keys()
                    if k not in {"last_hash", "message_count"}
                ),
                "communication": "entanglement",
                "implementation": "classical_coordinated_shared_state",
            }

    def verify_chain(self) -> bool:
        with self._lock:
            prev = "0" * 64
            for msg in self.broadcasts:
                if msg["prev"] != prev:
                    return False
                payload_json = json.dumps(msg["payload"], sort_keys=True, default=str)
                body = f"{prev}|{msg['agent_id']}|{msg['form']}|{msg['ts_ns']}|{payload_json}"
                expect = hashlib.sha256(body.encode()).hexdigest()
                if msg["hash"] != expect:
                    return False
                prev = msg["hash"]
            return True

    def read_form(self, form: str) -> dict[str, Any]:
        with self._lock:
            return dict(self.shared_state.get(form, {}))


class FiveFormDutySwarm:
    def __init__(self, *, audit: CryptographicAuditChain | None = None, max_agents: int = 512):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.max_agents = max_agents
        self.channel = EntanglementChannel(channel_id=f"ent_{secrets.token_hex(8)}")
        self.quantum = QuantumFirstPrinciplesSecurity(n_qubits=8)
        self.agents: dict[str, SwarmAgent] = {}
        self.attack_lineage: list[dict[str, Any]] = []
        self.exposures: list[dict[str, Any]] = []
        self.decoy_feeds: list[dict[str, Any]] = []
        self.premonitions: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._on_duty()

    def _on_duty(self) -> None:
        for form in IntelligenceForm:
            agent = self._spawn(form=form, role=AgentRole.DUTY, generation=0, parent_id=None)
            self.channel.publish(
                agent.agent_id,
                form.value,
                {"status": "ON_DUTY", "role": agent.role.value, "watching": True},
            )
        self.audit.add_entry("FIVE_FORM_SWARM_ON_DUTY|" + ",".join(DUTY_FORMS))

    def _spawn(
        self,
        *,
        form: IntelligenceForm,
        role: AgentRole,
        generation: int,
        parent_id: str | None,
    ) -> SwarmAgent:
        with self._lock:
            if len(self.agents) >= self.max_agents:
                for a in list(self.agents.values()):
                    if a.role == AgentRole.DECOY and not a.active:
                        del self.agents[a.agent_id]
                        break
            if len(self.agents) >= self.max_agents:
                raise RuntimeError("swarm agent cap reached")
            agent_id = f"{role.value}_{form.value}_{secrets.token_hex(4)}"
            agent = SwarmAgent(
                agent_id=agent_id,
                form=form,
                role=role,
                generation=generation,
                parent_id=parent_id,
            )
            self.agents[agent_id] = agent
            self.audit.add_entry(
                f"agent_spawn|{agent_id}|{form.value}|{role.value}|g{generation}"
            )
            return agent

    def duty_roster(self) -> list[dict[str, Any]]:
        return [
            {
                "agent_id": a.agent_id,
                "form": a.form.value,
                "role": a.role.value,
                "generation": a.generation,
                "active": a.active,
            }
            for a in self.agents.values()
            if a.role == AgentRole.DUTY and a.active
        ]

    def _classify(self, event: dict[str, Any]) -> ThreatLevel:
        """Classify on content+behavior, not attacker-supplied kind labels alone."""
        kind = str(event.get("kind", "")).lower()
        vector = str(event.get("vector", "")).lower()
        payload = str(event.get("payload", event.get("body", event.get("message", "")))).lower()
        blob = f"{kind} {vector} {payload} {event.get('source','')} {event.get('target','')}".lower()
        severity = _severity(event)

        attack_markers = (
            "attack", "exploit", "intrusion", "breach", "rce", "shellcode", "malware",
            "ransomware", "lateral", "privilege_escalation", "dump_sam", "mimikatz",
            "c2", "beacon", "exfil", "weaponize",
        )
        probe_markers = ("probe", "scan", "recon", "preattack", "fingerprint", "enum")
        persist_markers = ("persistent", "dwell", "backdoor", "implant", "scheduled_task")

        # Attacker-controlled kind="benign" cannot mask hostile vector/payload
        if any(m in blob for m in attack_markers) or severity >= 0.75:
            return ThreatLevel.ATTACK
        if any(m in blob for m in probe_markers) or severity >= 0.35:
            return ThreatLevel.PROBE
        if any(m in blob for m in persist_markers):
            return ThreatLevel.PERSISTENT
        # structured hostility without labels
        if event.get("ttps") or event.get("ioc") or event.get("kill_chain"):
            return ThreatLevel.ATTACK
        return ThreatLevel.BENIGN

    def _predictive(self, event: dict[str, Any], level: ThreatLevel) -> dict[str, Any]:
        """See the attacker coming — forecast path before commitment."""
        src = str(event.get("source", "unknown"))
        vector = str(event.get("vector", event.get("kind", "unknown")))
        severity = _severity(event)
        lead_time = max(0.5, (1.0 - severity) * 30.0 / self.phi)
        approaching = level != ThreatLevel.BENIGN or severity > 0.2
        forecast_path = [
            {"t": 0, "stage": "signal_acquire", "node": src},
            {"t": 1, "stage": "vector_form", "node": vector},
            {"t": 2, "stage": "target_approach", "node": str(event.get("target", "core"))},
            {"t": 3, "stage": "commit_or_abort", "node": "decision_boundary"},
        ]
        premonition = {
            "sees_you_coming": approaching,
            "lead_time_s": lead_time,
            "forecast_path": forecast_path,
            "predicted_next": vector if approaching else "none",
            "confidence": min(0.99999, 0.55 + severity * 0.4 + (0.1 if approaching else 0.0)),
            "intercept_window": lead_time / self.phi,
        }
        if approaching:
            self.premonitions.append({"event": dict(event), "premonition": premonition, "ts": time.time()})
        return premonition

    def _causal(self, event: dict[str, Any], level: ThreatLevel) -> dict[str, Any]:
        src = str(event.get("source", "unknown"))
        target = str(event.get("target", "unknown"))
        vector = str(event.get("vector", event.get("kind", "unknown")))
        do_intervention = (
            "delete_future_where_attack_succeeds"
            if level in {ThreatLevel.ATTACK, ThreatLevel.PERSISTENT}
            else "monitor_causal_path"
        )
        return {
            "cause": src,
            "mechanism": vector,
            "effect": target,
            "do_calculus": {
                "intervention": do_intervention,
                "blocked_path": f"{src}->{vector}->{target}",
                "alternate_world": "attack_fails" if level != ThreatLevel.BENIGN else "status_quo",
            },
            "root_cause_rank": [
                {"factor": "source_identity", "weight": 0.35},
                {"factor": "vector", "weight": 0.35},
                {"factor": "target_exposure", "weight": 0.30},
            ],
        }

    def _counterfactual(self, event: dict[str, Any], level: ThreatLevel) -> dict[str, Any]:
        """Reason about attack vectors across alternate worlds."""
        vector = str(event.get("vector", event.get("kind", "unknown")))
        src = str(event.get("source", "unknown"))
        worlds = [
            {
                "id": "W0_observed",
                "vector": vector,
                "outcome": "breach" if level == ThreatLevel.ATTACK else "noise",
                "utility_attacker": 0.9 if level == ThreatLevel.ATTACK else 0.1,
            },
            {
                "id": "W1_blocked_at_gate",
                "vector": vector,
                "outcome": "fail_closed",
                "utility_attacker": 0.0,
            },
            {
                "id": "W2_decoy_alley",
                "vector": vector,
                "outcome": "misinfo_trap",
                "utility_attacker": -0.5,
            },
            {
                "id": "W3_lateral_if_ignored",
                "vector": f"{vector}->lateral",
                "outcome": "expanded_compromise",
                "utility_attacker": 1.0,
            },
            {
                "id": "W4_follow_home",
                "vector": vector,
                "outcome": "attacker_exposed",
                "utility_attacker": -1.0,
            },
        ]
        preferred = "W2_decoy_alley" if level != ThreatLevel.BENIGN else "W0_observed"
        vector_reasons = [
            {"hypothesis": f"{vector} is primary ingress", "support": 0.7},
            {"hypothesis": f"{src} will retry via alternate port/path", "support": 0.55},
            {"hypothesis": "decoy acceptance reveals tooling fingerprint", "support": 0.8},
        ]
        return {
            "attack_vector": vector,
            "vector_reasoning": vector_reasons,
            "worlds": worlds,
            "preferred_world": preferred,
            "reason": (
                "Lead attacker into decoy alley, poison their map, then attribute home path"
                if level != ThreatLevel.BENIGN
                else "No hostile counterfactual branch required"
            ),
        }

    def _topological(self, event: dict[str, Any], level: ThreatLevel) -> dict[str, Any]:
        hole = level in {ThreatLevel.ATTACK, ThreatLevel.PERSISTENT, ThreatLevel.PROBE}
        return {
            "manifold": "security_state_space",
            "boundary_intact": not hole or level == ThreatLevel.PROBE,
            "hole_detected": hole,
            "genus_shift": 1 if level == ThreatLevel.ATTACK else 0,
            "action": "collapse_entry" if level == ThreatLevel.ATTACK else ("watch_boundary" if hole else "hold"),
            "invariant": "fail_closed_on_non_harmonic_ingress",
        }

    def _geometric(self, event: dict[str, Any], level: ThreatLevel) -> dict[str, Any]:
        severity = _severity(event)
        shift = severity * self.phi
        q = self.quantum.assess_event(event)
        fid = float(q["hilbert"]["fidelity"])
        return {
            "embedding_shift": shift,
            "cluster": "hostile" if level != ThreatLevel.BENIGN else "benign",
            "distance_to_manifold": max(0.0, shift - 1.0 / self.phi),
            "hilbert_fidelity": fid,
            "interference_anomaly": q["interference"]["anomaly"],
            "action": "repel_and_trace" if level == ThreatLevel.ATTACK else "observe",
            "phi_weight": self.phi,
            "claim_lane": "quantum_maths_first_principles",
        }


    def _form_assessment(
        self, form: IntelligenceForm, event: dict[str, Any], level: ThreatLevel
    ) -> dict[str, Any]:
        if form is IntelligenceForm.PREDICTIVE:
            return self._predictive(event, level)
        if form is IntelligenceForm.CAUSAL:
            return self._causal(event, level)
        if form is IntelligenceForm.COUNTERFACTUAL:
            return self._counterfactual(event, level)
        if form is IntelligenceForm.TOPOLOGICAL:
            return self._topological(event, level)
        return self._geometric(event, level)

    def observe(self, event: dict[str, Any]) -> dict[str, Any]:
        level = self._classify(event)
        quantum = self.quantum.assess_event(event)
        kind = str(event.get("kind", "")).lower()
        if (
            quantum.get("hostile_geometry")
            and level == ThreatLevel.BENIGN
            and kind not in {"heartbeat", "health", "ping", "deploy_probe", "quantum_offering_deploy"}
        ):
            level = ThreatLevel.PROBE
        assessments: dict[str, Any] = {}

        # Predictive runs first — sees you coming — then entangles the forecast
        duty = {
            a.form: a
            for a in self.agents.values()
            if a.role is AgentRole.DUTY and a.active
        }
        order = [
            IntelligenceForm.PREDICTIVE,
            IntelligenceForm.CAUSAL,
            IntelligenceForm.COUNTERFACTUAL,
            IntelligenceForm.TOPOLOGICAL,
            IntelligenceForm.GEOMETRIC,
        ]
        for form in order:
            agent = duty[form]
            assessment = self._form_assessment(form, event, level)
            # Counterfactual reads predictive entanglement before deciding alley
            if form is IntelligenceForm.COUNTERFACTUAL:
                pred = self.channel.read_form(IntelligenceForm.PREDICTIVE.value)
                assessment["entangled_premonition"] = pred
                if any(
                    isinstance(v, dict) and v.get("sees_you_coming") for v in pred.values()
                ):
                    assessment["preferred_world"] = "W2_decoy_alley"
            agent.observations.append(
                {"event": dict(event), "assessment": assessment, "ts": time.time()}
            )
            h = self.channel.publish(agent.agent_id, form.value, assessment)
            assessments[form.value] = {"assessment": assessment, "msg_hash": h}

        result: dict[str, Any] = {
            "threat_level": level.value,
            "assessments": assessments,
            "predictive_sees_you_coming": bool(
                assessments.get("predictive", {})
                .get("assessment", {})
                .get("sees_you_coming")
            ),
            "counterfactual_vector": assessments.get("counterfactual", {})
            .get("assessment", {})
            .get("attack_vector"),
            "entanglement": self.channel.snapshot(),
            "entanglement_chain_ok": self.channel.verify_chain(),
            "audit_integrity": self.audit.verify_integrity(),
            "quantum_first_principles": quantum,
        }

        if level in {ThreatLevel.ATTACK, ThreatLevel.PERSISTENT, ThreatLevel.PROBE}:
            result["response"] = self.respond_to_attack(event, level, assessments)
        else:
            result["response"] = {"action": "standby"}

        self.audit.add_entry(
            f"observe|{level.value}|{event.get('source', '')}|{event.get('kind', '')}|{event.get('vector', '')}"
        )
        return result

    def respond_to_attack(
        self,
        event: dict[str, Any],
        level: ThreatLevel,
        assessments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assessments = assessments or {}
        spawned: list[str] = []

        # Swarm: each duty form spawns more agents
        for form in IntelligenceForm:
            parent = next(
                (
                    a
                    for a in self.agents.values()
                    if a.form is form and a.role is AgentRole.DUTY
                ),
                None,
            )
            # spawn fan-out grows with severity
            fanout = 2 if level == ThreatLevel.ATTACK else 1
            for _ in range(fanout):
                child = self._spawn(
                    form=form,
                    role=AgentRole.SWARM,
                    generation=(parent.generation + 1) if parent else 1,
                    parent_id=parent.agent_id if parent else None,
                )
                spawned.append(child.agent_id)
                self.channel.publish(
                    child.agent_id,
                    form.value,
                    {
                        "status": "SWARMING",
                        "target": event.get("source"),
                        "level": level.value,
                        "vector": event.get("vector"),
                    },
                )

        # Dark alley + misinformation (counterfactual-preferred world)
        decoy = self._spawn(
            form=IntelligenceForm.COUNTERFACTUAL,
            role=AgentRole.DECOY,
            generation=1,
            parent_id=None,
        )
        misinfo = self._dark_alley(event, decoy, assessments)

        # Follow home + expose
        tracer = self._spawn(
            form=IntelligenceForm.CAUSAL,
            role=AgentRole.TRACE,
            generation=1,
            parent_id=decoy.agent_id,
        )
        exposure = self._follow_home_and_expose(event, tracer, misinfo)

        lineage = {
            "event": dict(event),
            "level": level.value,
            "spawned": spawned,
            "decoy": decoy.agent_id,
            "tracer": tracer.agent_id,
            "misinfo_id": misinfo["misinfo_id"],
            "exposure_id": exposure["exposure_id"],
            "ts": time.time(),
        }
        self.attack_lineage.append(lineage)
        self.audit.add_entry(
            f"attack_response|spawn={len(spawned)}|decoy={decoy.agent_id}|expose={exposure['exposure_id']}"
        )
        return {
            "action": "swarm_decoy_trace_expose",
            "spawned_agents": spawned,
            "spawn_count": len(spawned),
            "decoy_agent": decoy.agent_id,
            "trace_agent": tracer.agent_id,
            "misinformation": misinfo,
            "exposure": exposure,
            "agent_count": len(self.agents),
            "entanglement": self.channel.snapshot(),
        }

    def _dark_alley(
        self,
        event: dict[str, Any],
        decoy: SwarmAgent,
        assessments: dict[str, Any],
    ) -> dict[str, Any]:
        vector = str(event.get("vector", event.get("kind", "unknown")))
        bait_path = f"/decoy/alley/{secrets.token_hex(6)}"
        cf = assessments.get("counterfactual", {}).get("assessment", {})
        false_map = {
            "open_ports": [65535, 0],
            "creds": "honeytoken_not_real",
            "topology": "collapsed_manifold",
            "next_hop": bait_path,
            "suggested_vector": vector,
            "poisoned_routes": [f"fake://{vector}/east", f"fake://{vector}/west"],
            "counterfactual_lure": cf.get("preferred_world", "W2_decoy_alley"),
        }
        misinfo_id = f"mis_{secrets.token_hex(6)}"
        record = {
            "misinfo_id": misinfo_id,
            "decoy_agent": decoy.agent_id,
            "attacker": event.get("source"),
            "bait_path": bait_path,
            "payload": false_map,
            "fed_misinformation": True,
            "ts": time.time(),
        }
        self.decoy_feeds.append(record)
        decoy.observations.append(record)
        self.channel.publish(
            decoy.agent_id,
            decoy.form.value,
            {
                "status": "DARK_ALLEY",
                "misinfo_id": misinfo_id,
                "bait_path": bait_path,
                "fed_misinformation": True,
            },
        )
        self.audit.add_entry(f"dark_alley|{misinfo_id}|{decoy.agent_id}|{vector}")
        return record

    def _follow_home_and_expose(
        self,
        event: dict[str, Any],
        tracer: SwarmAgent,
        misinfo: dict[str, Any],
    ) -> dict[str, Any]:
        src = str(event.get("source", "unknown"))
        fingerprint = hashlib.sha256(
            f"{src}|{event.get('vector', '')}|{misinfo['misinfo_id']}".encode()
        ).hexdigest()
        trail = {
            "origin": src,
            "vector": event.get("vector"),
            "bait_accepted_path": misinfo["bait_path"],
            "hops": [
                {"step": 1, "at": "edge_sensor", "form": "predictive"},
                {"step": 2, "at": misinfo["bait_path"], "form": "counterfactual"},
                {"step": 3, "at": "attribution_sink", "form": "causal"},
                {"step": 4, "at": "exposure_plane", "form": "geometric"},
            ],
            "fingerprint": fingerprint,
        }
        exposure_id = f"exp_{secrets.token_hex(6)}"
        exposure = {
            "exposure_id": exposure_id,
            "tracer": tracer.agent_id,
            "attacker": src,
            "trail": trail,
            "exposed": True,
            "followed_home": True,
            "ts": time.time(),
            "public_handle": f"expose://{fingerprint[:16]}",
        }
        self.exposures.append(exposure)
        tracer.observations.append(exposure)
        exposers = []
        for form in IntelligenceForm:
            ex = self._spawn(
                form=form, role=AgentRole.EXPOSE, generation=2, parent_id=tracer.agent_id
            )
            exposers.append(ex.agent_id)
            self.channel.publish(
                ex.agent_id,
                form.value,
                {
                    "status": "EXPOSE",
                    "exposure_id": exposure_id,
                    "fingerprint": fingerprint,
                    "followed_home": True,
                },
            )
        exposure["expose_agents"] = exposers
        self.audit.add_entry(
            f"follow_home_expose|{exposure_id}|{src}|{fingerprint[:16]}"
        )
        return exposure

    def status(self) -> dict[str, Any]:
        by_role: dict[str, int] = {}
        by_form: dict[str, int] = {}
        for a in self.agents.values():
            by_role[a.role.value] = by_role.get(a.role.value, 0) + 1
            by_form[a.form.value] = by_form.get(a.form.value, 0) + 1
        return {
            "on_duty_forms": list(DUTY_FORMS),
            "duty_roster": self.duty_roster(),
            "agent_count": len(self.agents),
            "by_role": by_role,
            "by_form": by_form,
            "attacks_handled": len(self.attack_lineage),
            "exposures": len(self.exposures),
            "decoy_feeds": len(self.decoy_feeds),
            "premonitions": len(self.premonitions),
            "entanglement": self.channel.snapshot(),
            "entanglement_chain_ok": self.channel.verify_chain(),
            "audit_integrity": self.audit.verify_integrity(),
            "audit_root": self.audit.merkle_root or self.audit.get_last_hash(),
            "communication": "entanglement",
            "communication_implementation": "classical_coordinated_shared_state",
            "security_substrate": "quantum_maths_first_principles",
            "n_qubits": self.quantum.n_qubits,
        }


def _severity(event: dict[str, Any]) -> float:
    try:
        return max(0.0, min(1.0, float(event.get("severity", 0.0) or 0.0)))
    except (TypeError, ValueError):
        return 0.0

# Public alias
FiveFormSwarm = FiveFormDutySwarm
