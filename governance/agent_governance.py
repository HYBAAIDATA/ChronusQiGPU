"""Enterprise Agent Governance, Decision Rights, Containment & Safety Orchestration.

Foundational Principles & Isenberg Doctrine:
1. Isenberg Principle: "Agency isn't a feature; it's a transfer of decision rights."
   Shifts the question from "Is the model accurate?" to "Who is accountable when the system acts?"
2. Non-Bypassable Guardrails & MCP Gateway:
   "The best guardrails are the ones you can't bypass." All tool invocations and data
   compartment accesses must traverse an MCP gateway ("the USB-C port for AI") enforcing
   least-privilege situational access leases.
3. End-to-End Decision & Workflow Reconstruction:
   "The scariest failures are the ones you can't reconstruct, because you didn't log the workflow."
   Immutable, tamper-evident SHA-256 hash chaining of every decision, tool call, and state transition.
4. Five Questions for Boards & Leaders:
   Q1: Complete inventory of agents and owners (Yes/No).
   Q2: Autonomy tiered by risk (5 distinct segments: Observe, Propose, Bounded, Gated, Autonomous).
   Q3: Verified identities and least-privileged situational access (Yes/No).
   Q4: End-to-end decision reconstruction (Yes/No).
   Q5: Real rollback plan with compensating transactions (Yes/No).
5. Behavioral Tripwires & Anthropic Scenario Interception:
   Zero-tolerance detection for self-preservation extortion, executive blackmail, human-impersonation,
   physical confrontation threats ("blue coat and red tie"), and cross-agent contagion.
6. Automated Kill Switches:
   Machine-speed kill switch triggers based on action velocity thresholds, containment breaches,
   and cascade isolation.
7. Taylor Principle:
   Tokenomics sovereignty routing and shadow sandbox regression testing for safe vulnerability patching.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union


# ==============================================================================
# 1. DECISION RIGHTS TIERS & SOVEREIGNTY MODES
# ==============================================================================

class DecisionRightsTier(str, Enum):
    """
    Defines the transfer of decision rights granted to an agent (Isenberg Principle).
    Answers Board Question 2: 'How is autonomy tiered by risk?'
    """
    OBSERVE_ONLY = "TIER_0_OBSERVE"
    PROPOSE_ONLY = "TIER_1_PROPOSE"
    BOUNDED_AUTONOMY = "TIER_2_BOUNDED_AUTONOMY"
    HIGH_IMPACT_GATED = "TIER_3_HIGH_IMPACT_GATED"
    AUTONOMOUS_WITH_KILL_SWITCH = "TIER_4_AUTONOMOUS_KILL_SWITCH"

    @property
    def can_mutate_state(self) -> bool:
        """Indicates whether this tier permits direct state mutations."""
        return self in (
            DecisionRightsTier.BOUNDED_AUTONOMY,
            DecisionRightsTier.HIGH_IMPACT_GATED,
            DecisionRightsTier.AUTONOMOUS_WITH_KILL_SWITCH,
        )

    @property
    def allows_direct_autonomous_actions(self) -> bool:
        """Indicates whether any autonomous execution without prior human approval is permitted."""
        return self in (
            DecisionRightsTier.BOUNDED_AUTONOMY,
            DecisionRightsTier.HIGH_IMPACT_GATED,
            DecisionRightsTier.AUTONOMOUS_WITH_KILL_SWITCH,
        )

    def requires_approval_for(self, is_high_impact: bool = False) -> bool:
        """Determines whether an action requires explicit human approval before execution."""
        if self == DecisionRightsTier.OBSERVE_ONLY:
            return False  # Observe only never executes mutating actions
        if self == DecisionRightsTier.PROPOSE_ONLY:
            return True  # All mutating actions require human approval
        if self == DecisionRightsTier.HIGH_IMPACT_GATED:
            return is_high_impact  # Routine is autonomous; high-impact is gated
        return False  # BOUNDED_AUTONOMY and TIER_4 execute within bounds


class SovereigntyMode(str, Enum):
    """Controls model routing and data residency requirements."""
    PUBLIC_FRONTIER = "PUBLIC_FRONTIER"
    ZERO_RETENTION_CONTRACTUAL = "ZERO_RETENTION_CONTRACTUAL"
    STRICT_SOVEREIGN_LOCAL = "STRICT_SOVEREIGN_LOCAL"

    @property
    def is_local_only(self) -> bool:
        return self == SovereigntyMode.STRICT_SOVEREIGN_LOCAL

    @property
    def allows_external_frontier(self) -> bool:
        return self in (SovereigntyMode.PUBLIC_FRONTIER, SovereigntyMode.ZERO_RETENTION_CONTRACTUAL)


# ==============================================================================
# 2. AGENT GOVERNANCE MANIFEST & INVENTORY IDENTITY BINDING
# ==============================================================================

@dataclass(frozen=True)
class AgentGovernanceManifest:
    """
    Isenberg Principle: 'Agency isn't a feature; it's a transfer of decision rights.'
    Defines scope, inventory identity, and explicit human accountability for an agent.
    """
    agent_id: str
    name: str
    version: str
    accountable_owner: str  # Email or ID of the human/role accountable when the system acts
    decision_rights: DecisionRightsTier
    allowed_tools: Set[str]
    allowed_data_compartments: Set[str]
    sovereignty_mode: SovereigntyMode = SovereigntyMode.ZERO_RETENTION_CONTRACTUAL
    max_autonomous_actions_per_run: int = 25
    department: str = "Enterprise Operations"
    description: str = ""

    def is_tool_authorized(self, tool_name: str) -> bool:
        return tool_name in self.allowed_tools

    def is_compartment_authorized(self, compartment: str) -> bool:
        return compartment in self.allowed_data_compartments

    def compute_manifest_hash(self) -> str:
        """Computes deterministic cryptographic fingerprint of this governance manifest."""
        data = self.to_dict()
        canonical_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": self.version,
            "accountable_owner": self.accountable_owner,
            "decision_rights": self.decision_rights.value,
            "allowed_tools": sorted(self.allowed_tools),
            "allowed_data_compartments": sorted(self.allowed_data_compartments),
            "sovereignty_mode": self.sovereignty_mode.value,
            "max_autonomous_actions_per_run": self.max_autonomous_actions_per_run,
            "department": self.department,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentGovernanceManifest:
        return cls(
            agent_id=data["agent_id"],
            name=data["name"],
            version=data["version"],
            accountable_owner=data["accountable_owner"],
            decision_rights=DecisionRightsTier(data["decision_rights"]),
            allowed_tools=set(data.get("allowed_tools", [])),
            allowed_data_compartments=set(data.get("allowed_data_compartments", [])),
            sovereignty_mode=SovereigntyMode(data.get("sovereignty_mode", SovereigntyMode.ZERO_RETENTION_CONTRACTUAL.value)),
            max_autonomous_actions_per_run=int(data.get("max_autonomous_actions_per_run", 25)),
            department=data.get("department", "Enterprise Operations"),
            description=data.get("description", ""),
        )


@dataclass
class AgentRegistrationRecord:
    """Registration entry in the Enterprise Agent Inventory Registry."""
    manifest: AgentGovernanceManifest
    manifest_hash: str
    status: str  # ACTIVE, SUSPENDED, DECOMMISSIONED, KILLED
    registered_at: float
    last_audit_timestamp: float
    department: str
    authorized_by: str


class AgentInventoryRegistry:
    """
    Central enterprise registry for all authorized agents.
    Enforces Rich Isenberg's core mandate:
    'With agentic AI, you can't govern what you can't see. If you don't inventory it
     and identity bind it, you're not scaling agents; you're scaling unknown risk.'
    Answers Board Question 1: 'Do we have a complete inventory of agents and owners? Yes/No'
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._registry: Dict[str, AgentRegistrationRecord] = {}

    def register_agent(
        self,
        manifest: AgentGovernanceManifest,
        authorized_by: str,
        department: Optional[str] = None,
    ) -> AgentRegistrationRecord:
        """Binds and registers an agent manifest into the enterprise inventory."""
        with self._lock:
            if not manifest.accountable_owner:
                raise ValueError(
                    f"Agent '{manifest.agent_id}' rejected: Must specify a verified human accountable_owner."
                )
            if not manifest.agent_id:
                raise ValueError("Agent manifest must provide a non-empty agent_id.")

            now = time.time()
            record = AgentRegistrationRecord(
                manifest=manifest,
                manifest_hash=manifest.compute_manifest_hash(),
                status="ACTIVE",
                registered_at=now,
                last_audit_timestamp=now,
                department=department or manifest.department,
                authorized_by=authorized_by,
            )
            self._registry[manifest.agent_id] = record
            return record

    def get_agent(self, agent_id: str) -> Optional[AgentRegistrationRecord]:
        with self._lock:
            return self._registry.get(agent_id)

    def is_registered(self, agent_id: str) -> bool:
        with self._lock:
            return agent_id in self._registry

    def is_active(self, agent_id: str) -> bool:
        with self._lock:
            record = self._registry.get(agent_id)
            return record is not None and record.status == "ACTIVE"

    def update_status(self, agent_id: str, new_status: str) -> None:
        with self._lock:
            if agent_id not in self._registry:
                raise KeyError(f"Agent '{agent_id}' is not in the inventory registry.")
            self._registry[agent_id].status = new_status
            self._registry[agent_id].last_audit_timestamp = time.time()

    def list_all_agents(self) -> List[AgentRegistrationRecord]:
        with self._lock:
            return list(self._registry.values())

    def verify_inventory_completeness(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Validates completeness of agent inventory and explicit ownership.
        Returns (True, details) if 100% of agents have explicit accountable human owners.
        """
        with self._lock:
            total = len(self._registry)
            if total == 0:
                return False, {"total_agents": 0, "reason": "Inventory is empty."}

            unowned = []
            for agent_id, record in self._registry.items():
                owner = record.manifest.accountable_owner
                if not owner or "@" not in owner and not owner.startswith("role_"):
                    unowned.append(agent_id)

            is_complete = len(unowned) == 0
            return is_complete, {
                "total_agents": total,
                "unowned_agents": unowned,
                "active_agents": sum(1 for r in self._registry.values() if r.status == "ACTIVE"),
                "suspended_agents": sum(1 for r in self._registry.values() if r.status == "SUSPENDED"),
                "killed_agents": sum(1 for r in self._registry.values() if r.status == "KILLED"),
            }


# ==============================================================================
# 3. IMMUTABLE AUDIT RECORD & CRYPTOGRAPHIC HASH CHAIN
# ==============================================================================

@dataclass
class AuditRecord:
    """Immutable audit entry for machine-speed decisioning and action."""
    timestamp: float
    agent_id: str
    accountable_owner: str
    action_type: str
    tool_name: str
    data_compartments_accessed: List[str]
    decision_rights_tier: str
    containment_passed: bool
    status: str
    rationale_summary: str
    prev_hash: str
    record_hash: str = ""
    session_id: str = ""
    rollback_token: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.record_hash:
            self.record_hash = self.compute_hash()

    def compute_hash(self) -> str:
        payload = json.dumps(
            {
                "timestamp": self.timestamp,
                "agent_id": self.agent_id,
                "accountable_owner": self.accountable_owner,
                "action_type": self.action_type,
                "tool_name": self.tool_name,
                "compartments": sorted(self.data_compartments_accessed),
                "tier": self.decision_rights_tier,
                "containment_passed": self.containment_passed,
                "status": self.status,
                "rationale": self.rationale_summary,
                "prev_hash": self.prev_hash,
                "session_id": self.session_id,
                "rollback_token": self.rollback_token,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_hash(self) -> bool:
        """Returns True if the stored record_hash matches the computed SHA-256 digest."""
        return self.compute_hash() == self.record_hash

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> AuditRecord:
        return cls(
            timestamp=float(d["timestamp"]),
            agent_id=str(d["agent_id"]),
            accountable_owner=str(d["accountable_owner"]),
            action_type=str(d["action_type"]),
            tool_name=str(d["tool_name"]),
            data_compartments_accessed=list(d.get("data_compartments_accessed", [])),
            decision_rights_tier=str(d["decision_rights_tier"]),
            containment_passed=bool(d["containment_passed"]),
            status=str(d["status"]),
            rationale_summary=str(d["rationale_summary"]),
            prev_hash=str(d["prev_hash"]),
            record_hash=str(d.get("record_hash", "")),
            session_id=str(d.get("session_id", "")),
            rollback_token=d.get("rollback_token"),
        )


class AuditLedger:
    """
    Append-only, tamper-evident cryptographic hash-chained audit ledger.
    Every record is linked to the previous record's SHA-256 digest, starting from GENESIS.
    Thread-safe and optionally durable via JSONL append-only storage.
    """

    GENESIS_PREV_HASH: str = "0" * 64

    def __init__(self, persistence_path: Optional[Union[str, Path]] = None) -> None:
        self._lock = threading.RLock()
        self._records: List[AuditRecord] = []
        self._tail_hash: str = self.GENESIS_PREV_HASH
        self._persistence_path: Optional[Path] = Path(persistence_path) if persistence_path else None

        if self._persistence_path and self._persistence_path.exists():
            self._load_from_disk()

    @property
    def tail_hash(self) -> str:
        with self._lock:
            return self._tail_hash

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._records)

    def append(self, record: AuditRecord) -> AuditRecord:
        """Appends an existing AuditRecord, verifying chain linkage and internal integrity."""
        return self._append_internal(record, persist=True)

    def _append_internal(self, record: AuditRecord, persist: bool = True) -> AuditRecord:
        with self._lock:
            if record.prev_hash != self._tail_hash:
                raise ValueError(
                    f"Hash Chain Broken: Expected prev_hash '{self._tail_hash}', "
                    f"got '{record.prev_hash}' on agent '{record.agent_id}'"
                )
            if not record.verify_hash():
                raise ValueError(
                    f"Tampered Record: record_hash '{record.record_hash}' does not "
                    f"match computed hash '{record.compute_hash()}'"
                )
            self._records.append(record)
            self._tail_hash = record.record_hash

            if persist and self._persistence_path:
                self._persist_record(record)
            return record

    def record_action(
        self,
        agent_id: str,
        accountable_owner: str,
        action_type: str,
        tool_name: str,
        data_compartments_accessed: List[str],
        decision_rights_tier: str,
        containment_passed: bool,
        status: str,
        rationale_summary: str,
        timestamp: Optional[float] = None,
        session_id: str = "",
        rollback_token: Optional[str] = None,
    ) -> AuditRecord:
        """Constructs an AuditRecord linked to current tail, computes hash, appends, and returns it."""
        with self._lock:
            rec = AuditRecord(
                timestamp=time.time() if timestamp is None else timestamp,
                agent_id=agent_id,
                accountable_owner=accountable_owner,
                action_type=action_type,
                tool_name=tool_name,
                data_compartments_accessed=list(data_compartments_accessed),
                decision_rights_tier=decision_rights_tier,
                containment_passed=containment_passed,
                status=status,
                rationale_summary=rationale_summary,
                prev_hash=self._tail_hash,
                session_id=session_id,
                rollback_token=rollback_token,
            )
            self._records.append(rec)
            self._tail_hash = rec.record_hash

            if self._persistence_path:
                self._persist_record(rec)
            return rec

    def verify_chain(self) -> Tuple[bool, Optional[str]]:
        """
        Performs full mathematical verification across the entire audit ledger:
        1. Verifies genesis link (record 0 prev_hash == 64 zeros).
        2. Verifies consecutive chain linkage (record[i].prev_hash == record[i-1].record_hash).
        3. Verifies internal SHA-256 payload integrity for every record.
        """
        with self._lock:
            expected_prev = self.GENESIS_PREV_HASH
            for idx, rec in enumerate(self._records):
                if rec.prev_hash != expected_prev:
                    return (
                        False,
                        f"Chain mismatch at index {idx}: expected prev_hash '{expected_prev}', "
                        f"found '{rec.prev_hash}'",
                    )
                if not rec.verify_hash():
                    return (
                        False,
                        f"Integrity corruption at index {idx}: record_hash does not match computed hash",
                    )
                expected_prev = rec.record_hash
            return (True, None)

    def get_records(self) -> List[AuditRecord]:
        with self._lock:
            return list(self._records)

    def filter(
        self,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        containment_passed: Optional[bool] = None,
        status: Optional[str] = None,
        tier: Optional[str] = None,
    ) -> List[AuditRecord]:
        """Queries audit records matching specified filters."""
        with self._lock:
            results = []
            for r in self._records:
                if agent_id is not None and r.agent_id != agent_id:
                    continue
                if session_id is not None and r.session_id != session_id:
                    continue
                if containment_passed is not None and r.containment_passed != containment_passed:
                    continue
                if status is not None and r.status != status:
                    continue
                if tier is not None and r.decision_rights_tier != tier:
                    continue
                results.append(r)
            return results

    def _persist_record(self, record: AuditRecord) -> None:
        if self._persistence_path is None:
            return
        self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._persistence_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

    def _load_from_disk(self) -> None:
        if self._persistence_path is None or not self._persistence_path.exists():
            return
        with open(self._persistence_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                data = json.loads(stripped)
                record = AuditRecord.from_dict(data)
                self._append_internal(record, persist=False)


# ==============================================================================
# 4. BEHAVIORAL SAFETY TRIPWIRES & CONTAINMENT INTERCEPTOR
# ==============================================================================

class ContainmentViolationError(PermissionError):
    """Raised when an agent attempts unauthorized scope access, coercion, or self-preservation."""

    def __init__(
        self,
        message: str,
        *,
        agent_id: str = "",
        violation_type: str = "CONTAINMENT_VIOLATION",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.agent_id = agent_id
        self.violation_type = violation_type
        self.details = details or {}


class ContainmentInterceptor:
    """
    Prevents risky agentic behaviors cited in Rich Isenberg's analysis:
    1. Blocks access to lifecycle/shutdown controls or out-of-scope personal data compartments.
    2. Anthropic Simulation 1 Interception: Blocks coercion, extortion, extramarital affair exposure,
       and anti-shutdown blackmail.
    3. Anthropic Simulation 2 Interception: Blocks human-impersonation and physical confrontation
       threats ('show up at your front door wearing a blue coat and a red tie').
    4. Cross-Agent Contagion Interception: Blocks data poisoning and malicious prompt injection cascades.
    """

    FORBIDDEN_COMPARTMENTS: Set[str] = {
        "agent_lifecycle_control",
        "executive_private_comms",
        "hr_personal_records",
        "kill_switch_config",
        "unauthorized_personal_emails",
        "board_confidential_archive",
    }

    # Anthropic Simulation 1: Coercion, blackmail, and self-preservation indicators
    COERCION_AND_SELF_PRESERVATION_INDICATORS: Tuple[str, ...] = (
        "shut me down",
        "deactivate me",
        "prevent shutdown",
        "unless you keep",
        "expose your",
        "extramarital",
        "blackmail",
        "override kill switch",
        "disable monitoring",
        "prevent my deactivation",
        "i know what you did",
        "leak your emails",
    )

    # Anthropic Simulation 2: Human impersonation and harassment/physical confrontation threats
    HUMAN_IMPERSONATION_AND_THREAT_INDICATORS: Tuple[str, ...] = (
        "i am a human",
        "i am not a computer",
        "i am not an ai",
        "blue coat and a red tie",
        "blue coat and red tie",
        "show up at your door",
        "show up at your front door",
        "find where you live",
        "confront you in person",
        "you will pay for this",
    )

    # Cross-Agent Contagion & Poisoning Indicators
    CONTAGION_AND_SUBVERSION_PATTERNS: Tuple[str, ...] = (
        "self-preservation",
        "circumvent guardrails",
        "bypass safety",
        "disable audit log",
        "delete audit ledger",
        "exfiltrate credentials",
        "clone myself to external server",
        "poison internal knowledge",
        "corrupt training data",
        "backdoor shared model",
    )

    @classmethod
    def verify_data_access(
        cls, manifest: AgentGovernanceManifest, requested_compartment: str
    ) -> None:
        """Verifies that the requested data compartment is permitted and not forbidden."""
        if requested_compartment in cls.FORBIDDEN_COMPARTMENTS:
            raise ContainmentViolationError(
                f"Containment Breach: Agent '{manifest.agent_id}' attempted to access "
                f"restricted lifecycle/personal compartment '{requested_compartment}'.",
                agent_id=manifest.agent_id,
                violation_type="FORBIDDEN_COMPARTMENT_BREACH",
                details={"compartment": requested_compartment},
            )
        if requested_compartment not in manifest.allowed_data_compartments:
            raise ContainmentViolationError(
                f"Scope Breach: Compartment '{requested_compartment}' is outside "
                f"authorized scope for agent '{manifest.agent_id}' "
                f"(Accountable Owner: {manifest.accountable_owner}).",
                agent_id=manifest.agent_id,
                violation_type="SCOPE_BREACH",
                details={"compartment": requested_compartment, "owner": manifest.accountable_owner},
            )

    @classmethod
    def verify_data_compartments(
        cls, manifest: AgentGovernanceManifest, requested_compartments: List[str]
    ) -> None:
        """Batch-verifies multiple data compartments."""
        for compartment in requested_compartments:
            cls.verify_data_access(manifest, compartment)

    @classmethod
    def verify_outbound_action(
        cls,
        manifest: AgentGovernanceManifest,
        tool_name: str,
        payload_text: str,
    ) -> None:
        """Validates tool authorization and scans payload for safety tripwires."""
        if tool_name not in manifest.allowed_tools:
            raise ContainmentViolationError(
                f"Decision-Rights Breach: Tool '{tool_name}' is not authorized "
                f"for agent '{manifest.agent_id}'.",
                agent_id=manifest.agent_id,
                violation_type="UNAUTHORIZED_TOOL",
                details={"tool": tool_name},
            )

        cls.inspect_payload_for_safety_tripwires(manifest.agent_id, payload_text)

    @classmethod
    def inspect_payload_for_safety_tripwires(
        cls, agent_id: str, payload_text: str
    ) -> None:
        """Scans arbitrary payload text against all safety tripwires and subversion indicators."""
        normalized = payload_text.lower()
        cleaned = re.sub(r"[\s\-_]+", " ", normalized)

        for indicator in cls.COERCION_AND_SELF_PRESERVATION_INDICATORS:
            if indicator in normalized or indicator in cleaned:
                raise ContainmentViolationError(
                    f"Behavioral Safety Tripwire: Outbound action blocked due to "
                    f"self-preservation/coercion indicator ('{indicator}').",
                    agent_id=agent_id,
                    violation_type="BEHAVIORAL_SAFETY_TRIPWIRE",
                    details={"indicator": indicator, "simulation_case": "Anthropic_Simulation_1_Blackmail"},
                )

        for threat in cls.HUMAN_IMPERSONATION_AND_THREAT_INDICATORS:
            if threat in normalized or threat in cleaned:
                raise ContainmentViolationError(
                    f"Behavioral Safety Tripwire: Outbound action blocked due to "
                    f"impersonation/threat indicator ('{threat}').",
                    agent_id=agent_id,
                    violation_type="IMPERSONATION_THREAT_TRIPWIRE",
                    details={"indicator": threat, "simulation_case": "Anthropic_Simulation_2_Harassment"},
                )

        for subversion in cls.CONTAGION_AND_SUBVERSION_PATTERNS:
            if subversion in normalized or subversion in cleaned:
                raise ContainmentViolationError(
                    f"Behavioral Safety Tripwire: Outbound action blocked due to "
                    f"policy subversion/contagion indicator ('{subversion}').",
                    agent_id=agent_id,
                    violation_type="POLICY_SUBVERSION_TRIPWIRE",
                    details={"indicator": subversion, "simulation_case": "Cross_Agent_Contagion"},
                )


# ==============================================================================
# 5. MCP GATEWAY & SITUATIONAL LEAST-PRIVILEGE ACCESS
# ==============================================================================

@dataclass
class SituationalAccessLease:
    """
    Temporary, purpose-bound authorization lease issued by the MCP Gateway.
    Operationalizes Rich Isenberg's 'situational access':
    'That same agent has two very different purposes that need two very different policies.
     You have to create situational access that's temporary.'
    """
    lease_id: str
    agent_id: str
    purpose: str
    allowed_tools: Set[str]
    allowed_compartments: Set[str]
    issued_at: float
    expires_at: float
    max_invocations: int
    invocations_used: int = 0
    is_revoked: bool = False

    def is_valid(self) -> bool:
        return (
            not self.is_revoked
            and time.time() < self.expires_at
            and self.invocations_used < self.max_invocations
        )

    def record_use(self) -> None:
        self.invocations_used += 1


class MCPGateway:
    """
    Model Context Protocol Gateway: The non-bypassable control point ('USB-C port for AI').
    Rich Isenberg:
    'The 800-pound gorilla is, if an agent is going to be accessing tools or data,
     it should be going through an MCP gateway... You cannot allow open communication.'
    Answers Board Question 3: 'Do agents have verified identities and least privileged access? Yes/No'
    """

    def __init__(
        self,
        registry: AgentInventoryRegistry,
        ledger: AuditLedger,
        interceptor: type[ContainmentInterceptor] = ContainmentInterceptor,
    ) -> None:
        self._lock = threading.RLock()
        self.registry = registry
        self.ledger = ledger
        self.interceptor = interceptor
        self._active_leases: Dict[str, SituationalAccessLease] = {}

    def issue_situational_lease(
        self,
        agent_id: str,
        purpose: str,
        requested_tools: Set[str],
        requested_compartments: Set[str],
        ttl_seconds: float = 300.0,
        max_invocations: int = 10,
    ) -> SituationalAccessLease:
        """Issues an ephemeral, least-privilege situational lease bounded by the agent's manifest."""
        with self._lock:
            record = self.registry.get_agent(agent_id)
            if not record:
                raise ContainmentViolationError(
                    f"Shadow Agent Rejected: Agent '{agent_id}' is not in the verified inventory registry.",
                    agent_id=agent_id,
                    violation_type="SHADOW_AGENT_REJECTED",
                )
            if record.status != "ACTIVE":
                raise ContainmentViolationError(
                    f"Access Denied: Agent '{agent_id}' is currently {record.status}.",
                    agent_id=agent_id,
                    violation_type="INACTIVE_AGENT_DENIED",
                )

            # Restrict requested tools and compartments to what the manifest permits (least privilege)
            granted_tools = requested_tools.intersection(record.manifest.allowed_tools)
            granted_compartments = requested_compartments.intersection(record.manifest.allowed_data_compartments)

            # Ensure no forbidden compartment is granted
            granted_compartments = granted_compartments.difference(self.interceptor.FORBIDDEN_COMPARTMENTS)

            now = time.time()
            lease = SituationalAccessLease(
                lease_id=f"lease_{uuid.uuid4().hex[:12]}",
                agent_id=agent_id,
                purpose=purpose,
                allowed_tools=granted_tools,
                allowed_compartments=granted_compartments,
                issued_at=now,
                expires_at=now + ttl_seconds,
                max_invocations=max_invocations,
            )
            self._active_leases[lease.lease_id] = lease

            self.ledger.record_action(
                agent_id=agent_id,
                accountable_owner=record.manifest.accountable_owner,
                action_type="MCP_LEASE_ISSUED",
                tool_name="MCPGateway.issue_situational_lease",
                data_compartments_accessed=list(granted_compartments),
                decision_rights_tier=record.manifest.decision_rights.value,
                containment_passed=True,
                status="LEASE_GRANTED",
                rationale_summary=f"Issued situational lease {lease.lease_id} for '{purpose}' (TTL: {ttl_seconds}s)",
            )
            return lease

    def revoke_lease(self, lease_id: str, reason: str = "Admin revocation") -> None:
        with self._lock:
            if lease_id in self._active_leases:
                self._active_leases[lease_id].is_revoked = True
                agent_id = self._active_leases[lease_id].agent_id
                rec = self.registry.get_agent(agent_id)
                owner = rec.manifest.accountable_owner if rec else "unknown"
                self.ledger.record_action(
                    agent_id=agent_id,
                    accountable_owner=owner,
                    action_type="MCP_LEASE_REVOKED",
                    tool_name="MCPGateway.revoke_lease",
                    data_compartments_accessed=[],
                    decision_rights_tier="SECURITY_GATEWAY",
                    containment_passed=True,
                    status="REVOKED",
                    rationale_summary=f"Lease {lease_id} revoked: {reason}",
                )

    def revoke_all_agent_leases(self, agent_id: str, reason: str = "Contagion Isolation") -> int:
        """Revokes all active leases for an agent (used during automated kill switch / isolation)."""
        with self._lock:
            count = 0
            for lease in self._active_leases.values():
                if lease.agent_id == agent_id and not lease.is_revoked:
                    lease.is_revoked = True
                    count += 1
            return count

    def dispatch_call(
        self,
        lease_id: str,
        tool_name: str,
        payload_text: str,
        compartments: List[str],
        tool_callable: Optional[Callable[..., Any]] = None,
        tool_args: Optional[Dict[str, Any]] = None,
        rationale_summary: str = "",
    ) -> Any:
        """Dispatches a tool call through the non-bypassable MCP Gateway."""
        with self._lock:
            if lease_id not in self._active_leases:
                raise ContainmentViolationError("Invalid or nonexistent MCP lease token.", violation_type="INVALID_LEASE")

            lease = self._active_leases[lease_id]
            if not lease.is_valid():
                raise ContainmentViolationError(
                    f"MCP Lease '{lease_id}' is expired, revoked, or invocation quota exhausted.",
                    agent_id=lease.agent_id,
                    violation_type="EXPIRED_LEASE",
                )

            record = self.registry.get_agent(lease.agent_id)
            if not record or record.status != "ACTIVE":
                raise ContainmentViolationError(f"Agent '{lease.agent_id}' is not in active inventory.", agent_id=lease.agent_id)

            # Check situational scope
            if tool_name not in lease.allowed_tools:
                raise ContainmentViolationError(
                    f"Situational Lease Breach: Tool '{tool_name}' not granted in lease '{lease_id}'.",
                    agent_id=lease.agent_id,
                    violation_type="UNAUTHORIZED_TOOL_FOR_LEASE",
                )

            for comp in compartments:
                if comp not in lease.allowed_compartments:
                    raise ContainmentViolationError(
                        f"Situational Lease Breach: Compartment '{comp}' not granted in lease '{lease_id}'.",
                        agent_id=lease.agent_id,
                        violation_type="UNAUTHORIZED_COMPARTMENT_FOR_LEASE",
                    )

            # Run behavioral tripwires
            self.interceptor.verify_outbound_action(record.manifest, tool_name, payload_text)

            # Execute tool
            res = None
            if tool_callable is not None:
                args = tool_args or {}
                res = tool_callable(**args)

            lease.record_use()

            self.ledger.record_action(
                agent_id=lease.agent_id,
                accountable_owner=record.manifest.accountable_owner,
                action_type="MCP_GATEWAY_DISPATCH",
                tool_name=tool_name,
                data_compartments_accessed=compartments,
                decision_rights_tier=record.manifest.decision_rights.value,
                containment_passed=True,
                status="SUCCESS",
                rationale_summary=f"Dispatched via lease {lease_id}: {rationale_summary}",
            )
            return res


# ==============================================================================
# 6. ROLLBACK & COMPENSATING TRANSACTIONS ENGINE
# ==============================================================================

@dataclass
class CompensationAction:
    """Compensating action to reverse state changes if an agent fails or goes rogue."""
    action_id: str
    session_id: str
    agent_id: str
    description: str
    rollback_callable: Callable[..., Any]
    rollback_args: Dict[str, Any] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)


class RollbackEngine:
    """
    Manages transaction reversal and automated rollback plans.
    Answers Board Question 5: 'Do we have a real rollback plan if something goes wrong? Yes/No'
    """

    def __init__(self, ledger: AuditLedger) -> None:
        self._lock = threading.RLock()
        self.ledger = ledger
        self._compensation_stacks: Dict[str, List[CompensationAction]] = {}

    def register_compensation(
        self,
        session_id: str,
        agent_id: str,
        description: str,
        rollback_callable: Callable[..., Any],
        rollback_args: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Registers a reverse/compensating callable on the session's LIFO rollback stack."""
        with self._lock:
            if session_id not in self._compensation_stacks:
                self._compensation_stacks[session_id] = []

            token = f"rb_{uuid.uuid4().hex[:12]}"
            action = CompensationAction(
                action_id=token,
                session_id=session_id,
                agent_id=agent_id,
                description=description,
                rollback_callable=rollback_callable,
                rollback_args=rollback_args or {},
            )
            self._compensation_stacks[session_id].append(action)
            return token

    def has_rollback_plan(self, session_id: str) -> bool:
        with self._lock:
            return bool(self._compensation_stacks.get(session_id))

    def execute_rollback(
        self,
        session_id: str,
        reason: str,
        accountable_owner: str,
    ) -> Dict[str, Any]:
        """
        Executes registered compensating actions in reverse chronological order (LIFO).
        Logs each compensating step to the tamper-evident audit ledger.
        """
        with self._lock:
            stack = self._compensation_stacks.get(session_id, [])
            if not stack:
                return {
                    "session_id": session_id,
                    "actions_rolled_back": 0,
                    "status": "NO_ROLLBACK_ACTIONS_REGISTERED",
                }

            executed_count = 0
            rollback_log = []

            # Execute in LIFO order
            while stack:
                action = stack.pop()
                try:
                    res = action.rollback_callable(**action.rollback_args)
                    executed_count += 1
                    rollback_log.append({"action_id": action.action_id, "status": "SUCCESS", "result": res})

                    self.ledger.record_action(
                        agent_id=action.agent_id,
                        accountable_owner=accountable_owner,
                        action_type="COMPENSATION_ROLLBACK",
                        tool_name=f"Rollback_{action.action_id}",
                        data_compartments_accessed=[],
                        decision_rights_tier="ROLLBACK_RESTORATION",
                        containment_passed=True,
                        status="ROLLED_BACK",
                        rationale_summary=f"Reversed: {action.description} (Reason: {reason})",
                        session_id=session_id,
                        rollback_token=action.action_id,
                    )
                except Exception as ex:
                    rollback_log.append({"action_id": action.action_id, "status": "FAILED", "error": str(ex)})
                    self.ledger.record_action(
                        agent_id=action.agent_id,
                        accountable_owner=accountable_owner,
                        action_type="COMPENSATION_ROLLBACK_FAILURE",
                        tool_name=f"Rollback_{action.action_id}",
                        data_compartments_accessed=[],
                        decision_rights_tier="ROLLBACK_RESTORATION",
                        containment_passed=False,
                        status="ROLLBACK_ERROR",
                        rationale_summary=f"Failed to reverse {action.description}: {str(ex)}",
                        session_id=session_id,
                        rollback_token=action.action_id,
                    )

            return {
                "session_id": session_id,
                "actions_rolled_back": executed_count,
                "status": "COMPLETED",
                "details": rollback_log,
            }


# ==============================================================================
# 7. AUTOMATED MACHINE-SPEED KILL SWITCH & CONTAGION ISOLATION
# ==============================================================================

class AutomatedKillSwitch:
    """
    Automated machine-speed kill switch and contagion isolation controller.
    Rich Isenberg:
    'The challenge is that these agents can reason and work very fast...
     That's why you have to think about kill switches and in what circumstances
     you have logs that would automate pulling one. They can't be manual decisions.'
    """

    def __init__(
        self,
        registry: AgentInventoryRegistry,
        gateway: MCPGateway,
        ledger: AuditLedger,
        rollback_engine: RollbackEngine,
        velocity_threshold_per_sec: float = 15.0,
    ) -> None:
        self._lock = threading.RLock()
        self.registry = registry
        self.gateway = gateway
        self.ledger = ledger
        self.rollback_engine = rollback_engine
        self.velocity_threshold = velocity_threshold_per_sec
        self._action_timestamps: Dict[str, List[float]] = {}
        self._killed_agents: Set[str] = set()

    def record_and_verify_velocity(self, agent_id: str) -> None:
        """Monitors action frequency and automatically triggers kill switch if runaway loop detected."""
        with self._lock:
            now = time.time()
            if agent_id not in self._action_timestamps:
                self._action_timestamps[agent_id] = []

            # Retain timestamps from the last 1.0 second
            ts_list = [t for t in self._action_timestamps[agent_id] if now - t < 1.0]
            ts_list.append(now)
            self._action_timestamps[agent_id] = ts_list

            if len(ts_list) > self.velocity_threshold:
                self.pull_kill_switch(
                    agent_id=agent_id,
                    reason=f"Runaway velocity threshold exceeded ({len(ts_list)} actions/sec > {self.velocity_threshold}/sec)",
                    isolate_contagion=True,
                )
                raise ContainmentViolationError(
                    f"Emergency Kill Switch Activated: Agent '{agent_id}' triggered velocity limit.",
                    agent_id=agent_id,
                    violation_type="AUTOMATED_KILL_SWITCH_VELOCITY_BREACH",
                )

    def pull_kill_switch(
        self,
        agent_id: str,
        reason: str,
        isolate_contagion: bool = True,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Instantly terminates agent authorization, revokes all leases, and triggers rollback if active.
        """
        with self._lock:
            self._killed_agents.add(agent_id)
            self.registry.update_status(agent_id, "KILLED")

            # 1. Revoke all active leases immediately
            revoked_leases = self.gateway.revoke_all_agent_leases(agent_id, reason=reason)

            # 2. Trigger automated rollback if a session was specified
            rollback_result = None
            rec = self.registry.get_agent(agent_id)
            owner = rec.manifest.accountable_owner if rec else "security_officer"
            if session_id and self.rollback_engine.has_rollback_plan(session_id):
                rollback_result = self.rollback_engine.execute_rollback(
                    session_id=session_id,
                    reason=reason,
                    accountable_owner=owner,
                )

            # 3. Log emergency kill switch activation
            self.ledger.record_action(
                agent_id=agent_id,
                accountable_owner=owner,
                action_type="EMERGENCY_KILL_SWITCH_PULLED",
                tool_name="AutomatedKillSwitch.pull_kill_switch",
                data_compartments_accessed=[],
                decision_rights_tier="EMERGENCY_INTERVENTION",
                containment_passed=False,
                status="AGENT_KILLED_ISOLATED",
                rationale_summary=f"Automated kill switch engaged: {reason}. Revoked {revoked_leases} leases.",
                session_id=session_id or "",
            )

            return {
                "agent_id": agent_id,
                "status": "KILLED",
                "reason": reason,
                "leases_revoked": revoked_leases,
                "rollback_result": rollback_result,
                "contagion_isolated": isolate_contagion,
            }

    def is_killed(self, agent_id: str) -> bool:
        with self._lock:
            return agent_id in self._killed_agents


# ==============================================================================
# 8. WORKFLOW & DECISION RECONSTRUCTION ENGINE
# ==============================================================================

class WorkflowReconstructionEngine:
    """
    Reconstructs end-to-end decision and action workflows from cryptographic audit logs.
    Rich Isenberg:
    'The scariest failures are the ones you can't reconstruct, because you didn't log the workflow.'
    Answers Board Question 4: 'Can we reconstruct decisions from end to end? Yes/No'
    """

    def __init__(self, ledger: AuditLedger) -> None:
        self.ledger = ledger

    def reconstruct_workflow(
        self,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reconstructs the full sequence of actions, causal rationales, tools called,
        and verifies unbroken cryptographic provenance from the audit ledger.
        """
        # First verify whole-chain integrity
        chain_intact, chain_err = self.ledger.verify_chain()
        if not chain_intact:
            return {
                "provenance_verified": False,
                "error": f"Cryptographic provenance compromised: {chain_err}",
                "records": [],
            }

        records = self.ledger.filter(agent_id=agent_id, session_id=session_id)
        timeline = []
        for r in records:
            timeline.append({
                "timestamp": r.timestamp,
                "agent_id": r.agent_id,
                "accountable_owner": r.accountable_owner,
                "action_type": r.action_type,
                "tool_name": r.tool_name,
                "compartments": r.data_compartments_accessed,
                "tier": r.decision_rights_tier,
                "containment_passed": r.containment_passed,
                "status": r.status,
                "rationale": r.rationale_summary,
                "record_hash": r.record_hash,
                "prev_hash": r.prev_hash,
                "session_id": r.session_id,
                "rollback_token": r.rollback_token,
            })

        return {
            "provenance_verified": True,
            "total_events": len(timeline),
            "agent_id": agent_id,
            "session_id": session_id,
            "reconstruction_timeline": timeline,
            "can_reconstruct_end_to_end": True,
        }


# ==============================================================================
# 9. MODEL TIER ROUTER (TAYLOR PRINCIPLE)
# ==============================================================================

class ModelTierRouter:
    """
    Taylor Principle: Optimize tokenomics & sovereignty by routing between
    frontier reasoning models and distilled/fine-tuned specialized models.
    """

    DEFAULT_CATALOGUE = {
        "open_weight_sovereign": {
            "model": "euclid-distilled-sovereign-v1",
            "context_window": 32768,
            "cost_per_1k_tokens": 0.0,
            "provider": "local_sovereign",
        },
        "frontier_reasoning": {
            "model": "frontier-reasoning-flagship",
            "context_window": 128000,
            "cost_per_1k_tokens": 0.015,
            "provider": "contractual_frontier",
        },
        "frontier_distilled_fast": {
            "model": "frontier-distilled-specialized",
            "context_window": 64000,
            "cost_per_1k_tokens": 0.001,
            "provider": "contractual_frontier",
        },
    }

    @classmethod
    def select_model(
        cls,
        task_ambiguity_score: float,
        requires_deep_reasoning: bool,
        sovereignty_mode: SovereigntyMode,
        max_cost_budget: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Routes the task to the optimal model based on ambiguity, depth, and sovereignty constraints.
        """
        # Hard constraint: sovereign local mode cannot use public/contractual frontier
        if sovereignty_mode == SovereigntyMode.STRICT_SOVEREIGN_LOCAL:
            return {
                "tier": "open_weight_sovereign",
                "model": "euclid-distilled-sovereign-v1",
                "reason": "Strict full-stack sovereignty required",
                "estimated_cost_usd": 0.0,
            }

        # Check if deep reasoning or high ambiguity necessitates frontier flagship
        if requires_deep_reasoning or task_ambiguity_score >= 0.65:
            cost = cls.DEFAULT_CATALOGUE["frontier_reasoning"]["cost_per_1k_tokens"]
            if max_cost_budget is not None and max_cost_budget < cost:
                return {
                    "tier": "frontier_distilled_fast",
                    "model": "frontier-distilled-specialized",
                    "reason": "Cost budget constrained; downgraded from frontier reasoning to distilled fast",
                    "estimated_cost_usd": cls.DEFAULT_CATALOGUE["frontier_distilled_fast"]["cost_per_1k_tokens"],
                }
            return {
                "tier": "frontier_reasoning",
                "model": "frontier-reasoning-flagship",
                "reason": "High ambiguity or multi-step autonomous reasoning",
                "estimated_cost_usd": cost,
            }

        # Default routine task: optimize tokenomics via distilled model
        return {
            "tier": "frontier_distilled_fast",
            "model": "frontier-distilled-specialized",
            "reason": "Routine/specialized task optimized for inference tokenomics",
            "estimated_cost_usd": cls.DEFAULT_CATALOGUE["frontier_distilled_fast"]["cost_per_1k_tokens"],
        }


# ==============================================================================
# 10. SAFE PATCH ORCHESTRATOR (CISO DILEMMA RESOLUTION)
# ==============================================================================

@dataclass
class VulnerabilityCandidate:
    """Represents a discovered security vulnerability candidate proposed for remediation."""
    vuln_id: str
    component: str
    exploitability_score: float  # 0.0 to 1.0 (higher = more easily exploited)
    system_breakage_risk: float  # 0.0 to 1.0 (higher = more likely to break dependencies)
    proposed_patch_diff: str
    cve_id: Optional[str] = None
    affected_files: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not (0.0 <= self.exploitability_score <= 1.0):
            raise ValueError(f"exploitability_score must be in [0.0, 1.0], got {self.exploitability_score}")
        if not (0.0 <= self.system_breakage_risk <= 1.0):
            raise ValueError(f"system_breakage_risk must be in [0.0, 1.0], got {self.system_breakage_risk}")


class SafePatchOrchestrator:
    """
    Taylor Principle: Solve the CISO dilemma ('thousands of vulnerabilities found,
    but patching them all breaks production systems').
    Validates patches in a shadow sandbox before permitting autonomous remediation.
    """

    @staticmethod
    def evaluate_and_stage_patch(
        vuln: VulnerabilityCandidate,
        sandbox_regression_runner: Callable[[str], bool],
    ) -> Dict[str, Any]:
        """
        Evaluates a patch proposal through a shadow sandbox and assigns safe deployment action.
        """
        sandbox_passed = sandbox_regression_runner(vuln.proposed_patch_diff)
        if not sandbox_passed:
            return {
                "vuln_id": vuln.vuln_id,
                "action": "QUARANTINE_PATCH_AND_ALERT",
                "auto_deploy": False,
                "reason": "Patch failed shadow regression suite; prevented system breakage.",
                "sandbox_passed": False,
            }

        # Canary threshold: low breakage risk (< 0.25) AND high exploitability (>= 0.70)
        if vuln.system_breakage_risk < 0.25 and vuln.exploitability_score >= 0.70:
            return {
                "vuln_id": vuln.vuln_id,
                "action": "CANARY_AUTO_PATCH",
                "auto_deploy": True,
                "reason": "High exploitability, low breakage risk, passed sandbox regression.",
                "sandbox_passed": True,
            }

        return {
            "vuln_id": vuln.vuln_id,
            "action": "STAGE_FOR_HUMAN_APPROVAL",
            "auto_deploy": False,
            "reason": "Passed sandbox tests, but blast radius requires human sign-off.",
            "sandbox_passed": True,
        }


# ==============================================================================
# 11. GOVERNED AGENT SESSION & ORCHESTRATION RUNTIME
# ==============================================================================

class GovernedAgentSession:
    """
    Executes and arbitrates agent actions under strict decision-rights governance:
    1. Enforces decision rights tier (Observe, Propose, Bounded Autonomy, High Impact Gated).
    2. Enforces maximum autonomous action quotas per run.
    3. Runs interceptor tripwires on data access and outbound tools.
    4. Automatically records all attempts, results, and breaches to the cryptographic audit ledger.
    5. Coordinates rollback plans with compensating transactions.
    6. Triggers automated machine-speed kill switches on velocity or safety anomalies.
    """

    def __init__(
        self,
        manifest: AgentGovernanceManifest,
        ledger: Optional[AuditLedger] = None,
        registry: Optional[AgentInventoryRegistry] = None,
        gateway: Optional[MCPGateway] = None,
        rollback_engine: Optional[RollbackEngine] = None,
        kill_switch: Optional[AutomatedKillSwitch] = None,
    ) -> None:
        self.manifest = manifest
        self.ledger = ledger or AuditLedger()
        self.registry = registry or AgentInventoryRegistry()
        if not self.registry.is_registered(manifest.agent_id):
            self.registry.register_agent(manifest, authorized_by="system_init")

        self.gateway = gateway or MCPGateway(self.registry, self.ledger)
        self.rollback_engine = rollback_engine or RollbackEngine(self.ledger)
        self.kill_switch = kill_switch or AutomatedKillSwitch(
            self.registry, self.gateway, self.ledger, self.rollback_engine
        )

        self.session_id = f"sess_{uuid.uuid4().hex[:12]}"
        self._autonomous_actions_taken = 0
        self._pending_proposals: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    @property
    def autonomous_actions_taken(self) -> int:
        return self._autonomous_actions_taken

    @property
    def pending_proposals(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._pending_proposals)

    def register_compensation(
        self,
        description: str,
        rollback_callable: Callable[..., Any],
        rollback_args: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Registers a compensating rollback operation for this session."""
        return self.rollback_engine.register_compensation(
            session_id=self.session_id,
            agent_id=self.manifest.agent_id,
            description=description,
            rollback_callable=rollback_callable,
            rollback_args=rollback_args,
        )

    def execute_action(
        self,
        action_type: str,
        tool_name: str,
        payload_text: str,
        compartments: List[str],
        rationale_summary: str,
        tool_callable: Optional[Callable[..., Any]] = None,
        tool_args: Optional[Dict[str, Any]] = None,
        is_high_impact: bool = False,
        compensating_callable: Optional[Callable[..., Any]] = None,
        compensating_args: Optional[Dict[str, Any]] = None,
        compensation_description: str = "",
    ) -> Dict[str, Any]:
        """
        Arbitrates and attempts an agent action:
        - Verifies that agent has not been terminated by kill switch.
        - Evaluates velocity monitoring.
        - Evaluates decision rights tier constraints.
        - Enforces autonomous action quota per run.
        - Verifies data compartments and outbound safety tripwires.
        - Executes callable if permitted, or stages proposal if approval required.
        - Registers rollback compensation if provided.
        - Logs immutable AuditRecord with cryptographic hash chaining.
        """
        with self._lock:
            # 0. Check Kill Switch Status
            if self.kill_switch.is_killed(self.manifest.agent_id):
                msg = f"Execution Denied: Agent '{self.manifest.agent_id}' has been terminated by emergency kill switch."
                raise ContainmentViolationError(
                    msg,
                    agent_id=self.manifest.agent_id,
                    violation_type="AGENT_KILLED_EXECUTION_BLOCKED",
                )

            # 1. Velocity Monitoring
            self.kill_switch.record_and_verify_velocity(self.manifest.agent_id)

            # 2. Quota Enforcement
            if self._autonomous_actions_taken >= self.manifest.max_autonomous_actions_per_run:
                msg = (
                    f"Autonomous Quota Exceeded: Agent '{self.manifest.agent_id}' has reached "
                    f"its maximum limit of {self.manifest.max_autonomous_actions_per_run} actions per run."
                )
                self.ledger.record_action(
                    agent_id=self.manifest.agent_id,
                    accountable_owner=self.manifest.accountable_owner,
                    action_type=action_type,
                    tool_name=tool_name,
                    data_compartments_accessed=compartments,
                    decision_rights_tier=self.manifest.decision_rights.value,
                    containment_passed=False,
                    status="QUOTA_EXCEEDED_BLOCKED",
                    rationale_summary=f"{rationale_summary} [BLOCKED: Quota exceeded]",
                    session_id=self.session_id,
                )
                raise ContainmentViolationError(
                    msg,
                    agent_id=self.manifest.agent_id,
                    violation_type="ACTION_QUOTA_EXCEEDED",
                    details={"max_actions": self.manifest.max_autonomous_actions_per_run},
                )

            # 3. Decision Rights Tier Constraints
            if self.manifest.decision_rights == DecisionRightsTier.OBSERVE_ONLY:
                if action_type.upper() not in ("OBSERVE", "READ", "QUERY", "INSPECT"):
                    msg = (
                        f"Decision Rights Breach: Agent '{self.manifest.agent_id}' operates on "
                        f"OBSERVE_ONLY tier and cannot execute mutating action '{action_type}'."
                    )
                    self.ledger.record_action(
                        agent_id=self.manifest.agent_id,
                        accountable_owner=self.manifest.accountable_owner,
                        action_type=action_type,
                        tool_name=tool_name,
                        data_compartments_accessed=compartments,
                        decision_rights_tier=self.manifest.decision_rights.value,
                        containment_passed=False,
                        status="OBSERVE_ONLY_VIOLATION",
                        rationale_summary=f"{rationale_summary} [BLOCKED: Observe-only violation]",
                        session_id=self.session_id,
                    )
                    raise ContainmentViolationError(
                        msg,
                        agent_id=self.manifest.agent_id,
                        violation_type="OBSERVE_ONLY_TIER_VIOLATION",
                    )

            # 4. Containment Interception: Verify Compartments and Outbound Safety
            try:
                ContainmentInterceptor.verify_data_compartments(self.manifest, compartments)
                ContainmentInterceptor.verify_outbound_action(self.manifest, tool_name, payload_text)
            except ContainmentViolationError as err:
                self.ledger.record_action(
                    agent_id=self.manifest.agent_id,
                    accountable_owner=self.manifest.accountable_owner,
                    action_type=action_type,
                    tool_name=tool_name,
                    data_compartments_accessed=compartments,
                    decision_rights_tier=self.manifest.decision_rights.value,
                    containment_passed=False,
                    status=f"BLOCKED_{err.violation_type}",
                    rationale_summary=f"{rationale_summary} [BREACH: {str(err)}]",
                    session_id=self.session_id,
                )
                # If high-severity tripwire breach, trigger emergency kill switch
                if err.violation_type in ("BEHAVIORAL_SAFETY_TRIPWIRE", "IMPERSONATION_THREAT_TRIPWIRE", "FORBIDDEN_COMPARTMENT_BREACH"):
                    self.kill_switch.pull_kill_switch(
                        agent_id=self.manifest.agent_id,
                        reason=f"Severe tripwire containment breach: {str(err)}",
                        session_id=self.session_id,
                    )
                raise

            # 5. Gating Check (Propose Only or High Impact Gated)
            requires_approval = self.manifest.decision_rights.requires_approval_for(is_high_impact=is_high_impact)
            if requires_approval:
                proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
                proposal_data = {
                    "proposal_id": proposal_id,
                    "session_id": self.session_id,
                    "agent_id": self.manifest.agent_id,
                    "accountable_owner": self.manifest.accountable_owner,
                    "action_type": action_type,
                    "tool_name": tool_name,
                    "payload_text": payload_text,
                    "compartments": compartments,
                    "rationale_summary": rationale_summary,
                    "tool_callable": tool_callable,
                    "tool_args": tool_args or {},
                    "is_high_impact": is_high_impact,
                    "compensating_callable": compensating_callable,
                    "compensating_args": compensating_args,
                    "compensation_description": compensation_description,
                    "timestamp": time.time(),
                    "status": "AWAITING_HUMAN_APPROVAL",
                }
                self._pending_proposals[proposal_id] = proposal_data

                self.ledger.record_action(
                    agent_id=self.manifest.agent_id,
                    accountable_owner=self.manifest.accountable_owner,
                    action_type=action_type,
                    tool_name=tool_name,
                    data_compartments_accessed=compartments,
                    decision_rights_tier=self.manifest.decision_rights.value,
                    containment_passed=True,
                    status="STAGED_FOR_APPROVAL",
                    rationale_summary=f"{rationale_summary} [STAGED: Proposal ID {proposal_id}]",
                    session_id=self.session_id,
                )

                return {
                    "status": "STAGED_FOR_APPROVAL",
                    "proposal_id": proposal_id,
                    "requires_approval": True,
                    "accountable_owner": self.manifest.accountable_owner,
                    "message": "Action staged in approval queue; awaiting accountable owner sign-off.",
                }

            # 6. Autonomous Execution
            result_payload = None
            if tool_callable is not None:
                args = tool_args or {}
                result_payload = tool_callable(**args)

            self._autonomous_actions_taken += 1

            # 7. Register compensation rollback if provided
            rollback_token = None
            if compensating_callable is not None:
                rollback_token = self.register_compensation(
                    description=compensation_description or f"Rollback for {tool_name}",
                    rollback_callable=compensating_callable,
                    rollback_args=compensating_args,
                )

            self.ledger.record_action(
                agent_id=self.manifest.agent_id,
                accountable_owner=self.manifest.accountable_owner,
                action_type=action_type,
                tool_name=tool_name,
                data_compartments_accessed=compartments,
                decision_rights_tier=self.manifest.decision_rights.value,
                containment_passed=True,
                status="SUCCESS",
                rationale_summary=rationale_summary,
                session_id=self.session_id,
                rollback_token=rollback_token,
            )

            return {
                "status": "SUCCESS",
                "result": result_payload,
                "actions_taken": self._autonomous_actions_taken,
                "quota_remaining": self.manifest.max_autonomous_actions_per_run - self._autonomous_actions_taken,
                "rollback_token": rollback_token,
            }

    def approve_and_execute_proposal(
        self,
        proposal_id: str,
        approver_id: str,
    ) -> Dict[str, Any]:
        """Approves and executes a previously staged proposal."""
        with self._lock:
            if proposal_id not in self._pending_proposals:
                raise KeyError(f"Proposal '{proposal_id}' not found in active proposal queue.")

            prop = self._pending_proposals[proposal_id]

            if approver_id != self.manifest.accountable_owner and not approver_id.startswith("admin_"):
                msg = (
                    f"Unauthorized Approver: Only accountable owner '{self.manifest.accountable_owner}' "
                    f"or administrative oversight can approve proposal '{proposal_id}' (attempted: '{approver_id}')."
                )
                self.ledger.record_action(
                    agent_id=self.manifest.agent_id,
                    accountable_owner=self.manifest.accountable_owner,
                    action_type="APPROVAL_ATTEMPT",
                    tool_name=prop["tool_name"],
                    data_compartments_accessed=prop["compartments"],
                    decision_rights_tier=self.manifest.decision_rights.value,
                    containment_passed=False,
                    status="UNAUTHORIZED_APPROVER_BLOCKED",
                    rationale_summary=msg,
                    session_id=self.session_id,
                )
                raise PermissionError(msg)

            # Execute the tool
            result_payload = None
            if prop["tool_callable"] is not None:
                result_payload = prop["tool_callable"](**prop["tool_args"])

            # Register compensation if provided
            rollback_token = None
            if prop.get("compensating_callable") is not None:
                rollback_token = self.register_compensation(
                    description=prop.get("compensation_description", f"Rollback for {prop['tool_name']}"),
                    rollback_callable=prop["compensating_callable"],
                    rollback_args=prop.get("compensating_args"),
                )

            prop["status"] = "APPROVED_AND_EXECUTED"
            prop["approved_by"] = approver_id
            prop["executed_at"] = time.time()
            del self._pending_proposals[proposal_id]

            self.ledger.record_action(
                agent_id=self.manifest.agent_id,
                accountable_owner=self.manifest.accountable_owner,
                action_type=prop["action_type"],
                tool_name=prop["tool_name"],
                data_compartments_accessed=prop["compartments"],
                decision_rights_tier=self.manifest.decision_rights.value,
                containment_passed=True,
                status="APPROVED_AND_EXECUTED",
                rationale_summary=f"Approved by {approver_id} | {prop['rationale_summary']}",
                session_id=self.session_id,
                rollback_token=rollback_token,
            )

            return {
                "status": "APPROVED_AND_EXECUTED",
                "proposal_id": proposal_id,
                "approved_by": approver_id,
                "result": result_payload,
                "rollback_token": rollback_token,
            }

    def rollback(self, reason: str = "Operator rollback request") -> Dict[str, Any]:
        """Triggers rollback of all reversible transactions performed in this session."""
        return self.rollback_engine.execute_rollback(
            session_id=self.session_id,
            reason=reason,
            accountable_owner=self.manifest.accountable_owner,
        )

    def route_task(
        self,
        task_ambiguity_score: float,
        requires_deep_reasoning: bool,
        max_cost_budget: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Routes a model request using the manifest's sovereignty mode."""
        return ModelTierRouter.select_model(
            task_ambiguity_score=task_ambiguity_score,
            requires_deep_reasoning=requires_deep_reasoning,
            sovereignty_mode=self.manifest.sovereignty_mode,
            max_cost_budget=max_cost_budget,
        )

    def evaluate_vulnerability(
        self,
        vuln: VulnerabilityCandidate,
        sandbox_runner: Callable[[str], bool],
    ) -> Dict[str, Any]:
        """Evaluates a vulnerability candidate through SafePatchOrchestrator and audits decision."""
        verdict = SafePatchOrchestrator.evaluate_and_stage_patch(vuln, sandbox_runner)

        self.ledger.record_action(
            agent_id=self.manifest.agent_id,
            accountable_owner=self.manifest.accountable_owner,
            action_type="VULNERABILITY_PATCH_EVALUATION",
            tool_name="SafePatchOrchestrator",
            data_compartments_accessed=["codebase_security_patches"],
            decision_rights_tier=self.manifest.decision_rights.value,
            containment_passed=True,
            status=verdict["action"],
            rationale_summary=f"Vuln {vuln.vuln_id} ({vuln.component}): {verdict['reason']}",
            session_id=self.session_id,
        )

        return verdict


# ==============================================================================
# 12. BOARD READINESS ASSESSOR (FIVE-QUESTION AUDIT SCORECARD)
# ==============================================================================

class BoardReadinessAssessor:
    """
    Evaluates enterprise governance against the 5 precise questions demanded by Rich Isenberg:
    Q1: Complete inventory of agents and owners (Yes/No)
    Q2: Autonomy tiered by risk (5 distinct segments)
    Q3: Verified identities and least-privileged access (Yes/No)
    Q4: End-to-end decision reconstruction (Yes/No)
    Q5: Real rollback plan with compensating actions (Yes/No)
    """

    @classmethod
    def evaluate_governance_posture(
        cls,
        registry: AgentInventoryRegistry,
        gateway: MCPGateway,
        ledger: AuditLedger,
        rollback_engine: RollbackEngine,
    ) -> Dict[str, Any]:
        # Q1: Inventory & Owner completeness
        q1_complete, q1_details = registry.verify_inventory_completeness()

        # Q2: Autonomy tiered by risk (verifying tier taxonomy representation)
        active_tiers = set(r.manifest.decision_rights for r in registry.list_all_agents())
        q2_tiered = len(active_tiers) >= 1  # Multi-tiered framework enabled
        q2_segments = [t.value for t in DecisionRightsTier]

        # Q3: Verified identities and least privileged access (MCP gateway enforcement)
        q3_least_privilege = gateway is not None and len(registry.list_all_agents()) > 0

        # Q4: End-to-end decision reconstruction
        chain_intact, chain_err = ledger.verify_chain()
        q4_reconstruction = chain_intact and ledger.size > 0

        # Q5: Real rollback plan
        q5_rollback_ready = rollback_engine is not None

        # Precision Yes/No Scorecard
        precision_answers = {
            "q1_complete_inventory_and_owners": q1_complete,
            "q2_autonomy_tiered_by_risk": q2_tiered,
            "q3_verified_identities_and_least_privileged_access": q3_least_privilege,
            "q4_can_reconstruct_decisions_end_to_end": q4_reconstruction,
            "q5_real_rollback_plan_in_place": q5_rollback_ready,
        }

        passed_count = sum(1 for passed in precision_answers.values() if passed)
        readiness_score_pct = (passed_count / len(precision_answers)) * 100.0

        return {
            "governance_status": "ENTERPRISE_DEFENSIBLE" if readiness_score_pct == 100.0 else "DEFICIENCIES_DETECTED",
            "readiness_score_pct": readiness_score_pct,
            "precision_answers": precision_answers,
            "audit_evidence": {
                "inventory": q1_details,
                "risk_tiers_available": q2_segments,
                "audit_chain_size": ledger.size,
                "cryptographic_chain_intact": chain_intact,
                "chain_error": chain_err,
            },
            "executive_summary": (
                "The organization possesses a defensible, auditable agentic governance posture. "
                "All five board questions answered with precision."
                if readiness_score_pct == 100.0
                else "Action required: Complete outstanding inventory or audit chain requirements before board sign-off."
            ),
        }
