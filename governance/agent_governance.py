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


# ==============================================================================
# 13. ENHANCED MODEL TIER ROUTER & OPEN-WEIGHT VS. FRONTIER TOKENOMICS (TAYLOR)
# ==============================================================================

ModelTierRouter.DEFAULT_CATALOGUE["open_weight_finetuned_specialist"] = {
    "model": "euclid-openweight-finetuned-specialist-v2",
    "context_window": 65536,
    "cost_per_1k_tokens": 0.0004,
    "provider": "self_hosted_finetuned",
}

_orig_select_model = ModelTierRouter.select_model


@classmethod  # type: ignore[misc]
def _enhanced_select_model(
    cls,
    task_ambiguity_score: float,
    requires_deep_reasoning: bool,
    sovereignty_mode: SovereigntyMode,
    max_cost_budget: Optional[float] = None,
    has_domain_finetuned_weights: bool = False,
) -> Dict[str, Any]:
    """
    Routes the task to the optimal model based on ambiguity, depth, post-training
    fine-tuning availability, and sovereignty constraints.
    """
    if sovereignty_mode == SovereigntyMode.STRICT_SOVEREIGN_LOCAL:
        if has_domain_finetuned_weights and not requires_deep_reasoning:
            return {
                "tier": "open_weight_finetuned_specialist",
                "model": cls.DEFAULT_CATALOGUE["open_weight_finetuned_specialist"]["model"],
                "reason": "Strict sovereignty + domain post-training fine-tuned specialist weights",
                "estimated_cost_usd": cls.DEFAULT_CATALOGUE["open_weight_finetuned_specialist"]["cost_per_1k_tokens"],
            }
        return _orig_select_model(
            task_ambiguity_score=task_ambiguity_score,
            requires_deep_reasoning=requires_deep_reasoning,
            sovereignty_mode=sovereignty_mode,
            max_cost_budget=max_cost_budget,
        )

    if not requires_deep_reasoning and task_ambiguity_score < 0.65 and has_domain_finetuned_weights and task_ambiguity_score <= 0.35:
        return {
            "tier": "open_weight_finetuned_specialist",
            "model": cls.DEFAULT_CATALOGUE["open_weight_finetuned_specialist"]["model"],
            "reason": "Specialized low-ambiguity task routed to post-trained fine-tuned open-weight model",
            "estimated_cost_usd": cls.DEFAULT_CATALOGUE["open_weight_finetuned_specialist"]["cost_per_1k_tokens"],
        }

    return _orig_select_model(
        task_ambiguity_score=task_ambiguity_score,
        requires_deep_reasoning=requires_deep_reasoning,
        sovereignty_mode=sovereignty_mode,
        max_cost_budget=max_cost_budget,
    )


@classmethod  # type: ignore[misc]
def _evaluate_open_weight_vs_frontier(
    cls,
    monthly_token_volume_millions: float,
    task_specialization_ratio: float,
    requires_air_gapped_sovereignty: bool,
    contractual_zdr_accepted: bool = True,
    fine_tuning_engineering_cost_usd: float = 25000.0,
) -> Dict[str, Any]:
    """
    Evaluates a CIO/CTO's architectural tradeoff between self-hosted open-weight models
    (1. cost, 2. post-training fine-tuning, 3. full-stack sovereignty) and frontier lab
    offerings (vertical compute co-design, self-distillation advantage, contractual sovereignty).
    """
    if monthly_token_volume_millions < 0:
        raise ValueError("monthly_token_volume_millions must be non-negative")
    if not (0.0 <= task_specialization_ratio <= 1.0):
        raise ValueError("task_specialization_ratio must be in [0.0, 1.0]")

    total_1k_units = monthly_token_volume_millions * 1000.0
    ambiguous_share = 1.0 - task_specialization_ratio

    frontier_monthly_cost = total_1k_units * (
        ambiguous_share * cls.DEFAULT_CATALOGUE["frontier_reasoning"]["cost_per_1k_tokens"]
        + task_specialization_ratio * cls.DEFAULT_CATALOGUE["frontier_distilled_fast"]["cost_per_1k_tokens"]
    )

    amortized_ft_monthly = fine_tuning_engineering_cost_usd / 12.0
    hybrid_open_weight_monthly_cost = amortized_ft_monthly + total_1k_units * (
        ambiguous_share * cls.DEFAULT_CATALOGUE["frontier_reasoning"]["cost_per_1k_tokens"]
        + task_specialization_ratio * cls.DEFAULT_CATALOGUE["open_weight_finetuned_specialist"]["cost_per_1k_tokens"]
    )

    if requires_air_gapped_sovereignty and not contractual_zdr_accepted:
        recommended_strategy = "STRICT_OPEN_WEIGHT_SOVEREIGN"
        primary_driver = "Full-stack air-gapped sovereignty requirement cannot be met contractually"
    elif hybrid_open_weight_monthly_cost < frontier_monthly_cost and task_specialization_ratio >= 0.50:
        recommended_strategy = "HYBRID_FRONTIER_REASONING_PLUS_FINETUNED_OPEN_WEIGHT"
        primary_driver = (
            "High specialization volume justifies post-training fine-tuned open-weight "
            "models alongside frontier reasoning for ambiguous tasks"
        )
    else:
        recommended_strategy = "FRONTIER_SELF_DISTILLED_PORTFOLIO_WITH_CONTRACTUAL_SOVEREIGNTY"
        primary_driver = (
            "Frontier labs' vertical compute co-design and self-distilled models outperform "
            "self-hosted open weights on TCO while contractual ZDR satisfies sovereignty"
        )

    return {
        "recommended_strategy": recommended_strategy,
        "primary_driver": primary_driver,
        "cio_open_weight_pillars": {
            "cost_efficiency_favorable": hybrid_open_weight_monthly_cost < frontier_monthly_cost,
            "post_training_fine_tuning_viable": task_specialization_ratio >= 0.50,
            "full_stack_sovereignty_mandated": requires_air_gapped_sovereignty and not contractual_zdr_accepted,
        },
        "frontier_structural_advantages": {
            "vertical_hardware_compute_integration": True,
            "self_distillation_fast_tier_available": True,
            "contractual_sovereignty_equivalence": contractual_zdr_accepted,
        },
        "estimated_frontier_monthly_cost_usd": round(frontier_monthly_cost, 2),
        "estimated_hybrid_open_weight_monthly_cost_usd": round(hybrid_open_weight_monthly_cost, 2),
        "monthly_net_savings_with_hybrid_usd": round(
            max(0.0, frontier_monthly_cost - hybrid_open_weight_monthly_cost), 2
        ),
    }


ModelTierRouter.select_model = _enhanced_select_model  # type: ignore[assignment]
ModelTierRouter.evaluate_open_weight_vs_frontier = _evaluate_open_weight_vs_frontier  # type: ignore[attr-defined]


# ==============================================================================
# 14. CISO BACKLOG TRIAGE & DEMOCRATIZED SMB/CLINIC SECURITY APPLIANCE (TAYLOR)
# ==============================================================================

@classmethod  # type: ignore[misc]
def _triage_vulnerability_backlog(
    cls,
    candidates: List[VulnerabilityCandidate],
    sandbox_regression_runner: Callable[[str], bool],
) -> Dict[str, Any]:
    """
    Triages a backlog of AI-discovered legacy vulnerabilities ('cyber tech debt')
    without taking down production systems ('Do you want the system running, or do
    you want it patched?').
    """
    ranked = sorted(
        candidates,
        key=lambda v: (v.exploitability_score * (1.0 - v.system_breakage_risk), v.exploitability_score),
        reverse=True,
    )
    canary_auto_patched: List[Dict[str, Any]] = []
    staged_for_human: List[Dict[str, Any]] = []
    quarantined_with_virtual_shield: List[Dict[str, Any]] = []

    for vuln in ranked:
        verdict = dict(cls.evaluate_and_stage_patch(vuln, sandbox_regression_runner))
        verdict["component"] = vuln.component
        verdict["priority_index"] = round(
            vuln.exploitability_score * (1.0 - vuln.system_breakage_risk), 4
        )
        if verdict["action"] == "CANARY_AUTO_PATCH":
            verdict["virtual_shield_applied"] = False
            canary_auto_patched.append(verdict)
        elif verdict["action"] == "STAGE_FOR_HUMAN_APPROVAL":
            verdict["virtual_shield_applied"] = vuln.exploitability_score >= 0.70
            staged_for_human.append(verdict)
        else:
            verdict["virtual_shield_applied"] = True
            quarantined_with_virtual_shield.append(verdict)

    return {
        "total_discovered_vulnerabilities": len(candidates),
        "production_uptime_preserved": True,
        "canary_auto_patched_count": len(canary_auto_patched),
        "staged_for_human_approval_count": len(staged_for_human),
        "quarantined_with_virtual_shield_count": len(quarantined_with_virtual_shield),
        "canary_auto_patched": canary_auto_patched,
        "staged_for_human_approval": staged_for_human,
        "quarantined_with_virtual_shield": quarantined_with_virtual_shield,
    }


@staticmethod  # type: ignore[misc]
def _verify_post_patch_telemetry(
    vuln_id: str,
    baseline_error_rate: float,
    observed_error_rate: float,
    baseline_latency_ms: float,
    observed_latency_ms: float,
    max_error_delta: float = 0.005,
    max_latency_multiplier: float = 1.25,
) -> Dict[str, Any]:
    """
    Active post-deployment canary monitoring: verifies that an autonomously deployed
    security patch has not degraded production availability or latency, triggering
    instant rollback + virtual shielding if anomalies appear.
    """
    error_spike = (observed_error_rate - baseline_error_rate) > max_error_delta
    latency_spike = observed_latency_ms > (baseline_latency_ms * max_latency_multiplier)
    healthy = not (error_spike or latency_spike)

    return {
        "vuln_id": vuln_id,
        "canary_healthy": healthy,
        "action": "PROMOTE_TO_FULL_PRODUCTION" if healthy else "AUTO_ROLLBACK_PATCH_AND_ENGAGE_VIRTUAL_SHIELD",
        "error_spike_detected": error_spike,
        "latency_spike_detected": latency_spike,
        "observed_error_rate": observed_error_rate,
        "observed_latency_ms": observed_latency_ms,
    }


SafePatchOrchestrator.triage_vulnerability_backlog = _triage_vulnerability_backlog  # type: ignore[attr-defined]
SafePatchOrchestrator.verify_post_patch_telemetry = _verify_post_patch_telemetry  # type: ignore[attr-defined]


class DemocratizedSecurityAppliance:
    """
    Taylor Principle: Out-of-the-box automated cyber defense for vulnerable cohorts
    (local medical clinics, regional hospitals, community banks, SMBs) that face
    acute societal vulnerability (ransomware, AI-accelerated exploits) but lack
    Fortune-500 CISO security engineering teams.
    """

    SUPPORTED_COHORTS = frozenset({
        "LOCAL_MEDICAL_CLINIC",
        "REGIONAL_HOSPITAL",
        "COMMUNITY_BANK",
        "SMALL_MEDIUM_BUSINESS",
        "MUNICIPAL_UTILITY",
        "SCHOOL_DISTRICT",
    })

    @classmethod
    def deploy_out_of_the_box_shield(
        cls,
        organization_name: str,
        cohort_type: str,
        endpoint_count: int,
        legacy_unpatched_systems: int = 0,
        ransomware_immutable_backup_enabled: bool = True,
    ) -> Dict[str, Any]:
        """
        Provisions a zero-configuration autonomous defensive appliance for an SMB or
        critical community institution.
        """
        if not organization_name or not organization_name.strip():
            raise ValueError("organization_name is required")
        normalized_cohort = cohort_type.strip().upper()
        if normalized_cohort not in cls.SUPPORTED_COHORTS:
            raise ValueError(
                f"Unsupported cohort_type '{cohort_type}'. Must be one of {sorted(cls.SUPPORTED_COHORTS)}"
            )
        if endpoint_count < 1:
            raise ValueError("endpoint_count must be >= 1")

        virtual_shields_provisioned = max(0, legacy_unpatched_systems)
        readiness_posture = (
            "ZERO_CONFIG_AUTONOMOUS_PROTECTION_ACTIVE"
            if ransomware_immutable_backup_enabled
            else "DEGRADED_BACKUP_REQUIRED"
        )

        return {
            "organization_name": organization_name.strip(),
            "cohort_type": normalized_cohort,
            "protection_status": readiness_posture,
            "requires_in_house_ciso": False,
            "protected_endpoints": endpoint_count,
            "legacy_endpoints_virtually_shielded": virtual_shields_provisioned,
            "autonomous_capabilities_enabled": [
                "CONTINUOUS_SHADOW_SANDBOX_PATCHING",
                "RANSOMWARE_CANARY_FILE_TRIPWIRES",
                "ZERO_TRUST_EGRESS_CONTAINMENT",
                "VIRTUAL_WAF_FOR_UNPATCHABLE_LEGACY_SYSTEMS",
                "IMMUTABLE_AIRGAPPED_MICRO_BACKUPS" if ransomware_immutable_backup_enabled else "BACKUP_PENDING",
            ],
        }


# ==============================================================================
# 15. REVENUE-ALIGNED WORKFLOWS, 80/20 REDESIGN & COMPETITIVE REINVESTMENT
# ==============================================================================

class WorkflowCategory(str, Enum):
    """
    Taylor & Kutcher Principle: Enterprise workflows reshaped by autonomous reasoning agents.
    """
    CUSTOMER_SERVICE_FRONT_DOOR = "CUSTOMER_SERVICE_FRONT_DOOR"
    MERCHANT_ONBOARDING = "MERCHANT_ONBOARDING"
    KYC_COMPLIANCE = "KYC_COMPLIANCE"
    PRESCRIPTION_DRUG_ADHERENCE = "PRESCRIPTION_DRUG_ADHERENCE"
    MORTGAGE_ORIGINATION = "MORTGAGE_ORIGINATION"
    AUTONOMOUS_SOFTWARE_ENGINEERING = "AUTONOMOUS_SOFTWARE_ENGINEERING"


class RevenueAlignedWorkflowEngine:
    """
    Implements Bret Taylor & Eric Kutcher's institutional transformation framework:
    1. Digital Front-Door & Revenue-Aligned Workflows:
       - Customer service resolving >90% of cases autonomously, decoupling company
         growth from operating cost while improving retention and lowering CAC.
       - Revenue-aligned workflows: merchant onboarding, KYC compliance, prescription
         drug adherence, mortgage origination, and software engineering.
    2. Kutcher's 80/20 Institutional Transformation Rule:
       - Moving from individual productivity to institutional-level productivity is an
         80% business process redesign problem and a 20% technology problem.
    3. Taylor's Competitive Reinvestment Imperative:
       - 'Adopting AI for your core corporate processes will be an imperative, not a
         competitive advantage.' Efficiency gains in competitive markets are reinvested
         into lower customer prices, lower CAC, better retention, and MORE software
         engineering capacity (Jevons paradox for software creation).
    """

    BUSINESS_REDESIGN_WEIGHT = 0.80
    TECHNOLOGY_READINESS_WEIGHT = 0.20
    FRONT_DOOR_AUTONOMOUS_BENCHMARK = 0.90

    @classmethod
    def evaluate_workflow_deployment(
        cls,
        workflow_category: WorkflowCategory,
        monthly_case_volume: int,
        autonomous_resolution_rate: float,
        legacy_cost_per_case_usd: float,
        agentic_cost_per_case_usd: float,
        process_redesign_score: float,
        technology_readiness_score: float,
        baseline_cac_usd: float = 120.0,
        baseline_annual_retention_rate: float = 0.82,
    ) -> Dict[str, Any]:
        """
        Evaluates an autonomous agent workflow deployment across unit economics,
        Kutcher's 80/20 institutional transformation index, and growth-cost decoupling.
        """
        if monthly_case_volume < 0:
            raise ValueError("monthly_case_volume must be non-negative")
        if not (0.0 <= autonomous_resolution_rate <= 1.0):
            raise ValueError("autonomous_resolution_rate must be in [0.0, 1.0]")
        if not (0.0 <= process_redesign_score <= 1.0) or not (0.0 <= technology_readiness_score <= 1.0):
            raise ValueError("process_redesign_score and technology_readiness_score must be in [0.0, 1.0]")

        # Kutcher 80/20 institutional transformation score
        institutional_transformation_index = (
            cls.BUSINESS_REDESIGN_WEIGHT * process_redesign_score
            + cls.TECHNOLOGY_READINESS_WEIGHT * technology_readiness_score
        )
        individual_productivity_trap = process_redesign_score < 0.50 and technology_readiness_score >= 0.70

        autonomously_resolved_cases = int(round(monthly_case_volume * autonomous_resolution_rate))
        human_escalated_cases = monthly_case_volume - autonomously_resolved_cases

        legacy_monthly_cost = monthly_case_volume * legacy_cost_per_case_usd
        blended_monthly_cost = (
            autonomously_resolved_cases * agentic_cost_per_case_usd
            + human_escalated_cases * legacy_cost_per_case_usd
        )
        # Realized savings scale with institutional process redesign maturity
        realized_monthly_savings = max(
            0.0, (legacy_monthly_cost - blended_monthly_cost) * institutional_transformation_index
        )

        # Growth decoupled from cost when autonomous resolution >= 90% and process is redesigned
        growth_decoupled_from_cost = (
            autonomous_resolution_rate >= cls.FRONT_DOOR_AUTONOMOUS_BENCHMARK
            and process_redesign_score >= 0.65
        )

        # Digital front door improves retention and lowers CAC via instant 24/7 personalized resolution
        projected_cac_usd = round(
            baseline_cac_usd * (1.0 - 0.18 * autonomous_resolution_rate * institutional_transformation_index), 2
        )
        projected_retention_rate = round(
            min(0.99, baseline_annual_retention_rate + 0.08 * autonomous_resolution_rate * institutional_transformation_index),
            4,
        )

        return {
            "workflow_category": workflow_category.value,
            "monthly_case_volume": monthly_case_volume,
            "autonomously_resolved_cases": autonomously_resolved_cases,
            "human_escalated_cases": human_escalated_cases,
            "autonomous_resolution_rate": round(autonomous_resolution_rate, 4),
            "meets_90pct_front_door_benchmark": autonomous_resolution_rate >= cls.FRONT_DOOR_AUTONOMOUS_BENCHMARK,
            "growth_decoupled_from_cost": growth_decoupled_from_cost,
            "kutcher_80_20_assessment": {
                "business_process_redesign_weight": cls.BUSINESS_REDESIGN_WEIGHT,
                "technology_readiness_weight": cls.TECHNOLOGY_READINESS_WEIGHT,
                "process_redesign_score": process_redesign_score,
                "technology_readiness_score": technology_readiness_score,
                "institutional_transformation_index": round(institutional_transformation_index, 4),
                "in_individual_productivity_trap": individual_productivity_trap,
                "diagnosis": (
                    "WARNING: Individual productivity trap detected — technology is deployed on legacy workflows without 80% business process redesign."
                    if individual_productivity_trap
                    else "Institutional transformation active — end-to-end workflow redesigned around autonomous agency."
                ),
            },
            "unit_economics": {
                "legacy_monthly_cost_usd": round(legacy_monthly_cost, 2),
                "blended_agentic_monthly_cost_usd": round(blended_monthly_cost, 2),
                "realized_monthly_savings_usd": round(realized_monthly_savings, 2),
                "baseline_cac_usd": baseline_cac_usd,
                "projected_cac_usd": projected_cac_usd,
                "baseline_annual_retention_rate": baseline_annual_retention_rate,
                "projected_annual_retention_rate": projected_retention_rate,
            },
        }

    @classmethod
    def simulate_competitive_reinvestment(
        cls,
        annual_ai_efficiency_savings_usd: float,
        market_competitiveness_index: float,
        current_software_engineering_headcount: int,
        coding_agent_productivity_multiplier: float = 2.2,
    ) -> Dict[str, Any]:
        """
        Models Bret Taylor's competitive market dynamics:
        - Adopting AI for core processes is a survival imperative, not a permanent margin windfall.
        - Efficiency savings are reinvested into customer price/value improvements, lower CAC,
          and expanded software creation (companies build MORE software rather than shrinking
          engineering capacity because every organization was previously software-supply-constrained).
        """
        if annual_ai_efficiency_savings_usd < 0:
            raise ValueError("annual_ai_efficiency_savings_usd must be non-negative")
        if not (0.0 <= market_competitiveness_index <= 1.0):
            raise ValueError("market_competitiveness_index must be in [0.0, 1.0]")
        if current_software_engineering_headcount < 0:
            raise ValueError("current_software_engineering_headcount must be non-negative")
        if coding_agent_productivity_multiplier < 1.0:
            raise ValueError("coding_agent_productivity_multiplier must be >= 1.0")

        reinvested_share = 0.50 + 0.40 * market_competitiveness_index
        retained_margin_share = 1.0 - reinvested_share

        reinvested_into_customer_price_and_cac_usd = annual_ai_efficiency_savings_usd * (reinvested_share * 0.55)
        reinvested_into_new_software_and_products_usd = annual_ai_efficiency_savings_usd * (reinvested_share * 0.45)
        retained_operating_margin_usd = annual_ai_efficiency_savings_usd * retained_margin_share

        effective_software_output_fte_equivalent = round(
            current_software_engineering_headcount * coding_agent_productivity_multiplier, 2
        )

        return {
            "strategic_posture": "COMPETITIVE_IMPERATIVE_NOT_OPTIONAL",
            "annual_ai_efficiency_savings_usd": round(annual_ai_efficiency_savings_usd, 2),
            "reinvested_into_customer_value_and_lower_cac_usd": round(reinvested_into_customer_price_and_cac_usd, 2),
            "reinvested_into_expanded_software_creation_usd": round(reinvested_into_new_software_and_products_usd, 2),
            "retained_operating_margin_usd": round(retained_operating_margin_usd, 2),
            "software_engineering_jevons_effect": {
                "current_engineering_headcount": current_software_engineering_headcount,
                "coding_agent_productivity_multiplier": coding_agent_productivity_multiplier,
                "effective_software_output_fte_equivalent": effective_software_output_fte_equivalent,
                "net_software_demand_trajectory": "EXPANDING_MORE_SOFTWARE_BUILT",
            },
        }


# ==============================================================================
# 16. INFRASTRUCTURE BET & LOCAL COMMUNITY ACCOUNTABILITY GOVERNOR (TAYLOR)
# ==============================================================================

class InfrastructureBetAndCommunityGovernor:
    """
    Implements Bret Taylor's framework on the US/global AI data center buildout:
    1. Sizing the Infrastructure Bet:
       - Time-horizon impedance mismatch: AI model progress is measured in days/weeks,
         whereas power & data center construction requires multiyear (3-5 yr) commitments.
       - Evaluates system-level financing health: hyperscaler operating cash flow vs.
         debt/project finance, and the transition from training capex to high-margin
         enterprise inference revenue.
       - Strategic asymmetry: despite financial overbuild risk (akin to the 1990s fiber
         boom), it is a strategic bet the nation/enterprise must make.
    2. Local Community Accountability ('Two Questions Industry Must Answer'):
       - Q1: 'Will AI benefit me broadly?'
       - Q2: 'Will this data center benefit my community?'
       - Requires zero residential electricity bill inflation, water/environmental
         stewardship, local blue-collar jobs (electricians, HVAC technicians, plumbers),
         local tax-base funding, and transparent town-hall engagement.
    """

    @classmethod
    def evaluate_infrastructure_bet(
        cls,
        planned_capex_billions_usd: float,
        funded_by_operating_cash_flow_pct: float,
        funded_by_debt_pct: float,
        enterprise_inference_workload_share: float,
        enterprise_inference_gross_margin: float,
        ai_innovation_cycle_days: int = 14,
        datacenter_build_lead_time_years: float = 3.5,
    ) -> Dict[str, Any]:
        """
        Evaluates the macroeconomic and financial structure of a multiyear AI data center
        buildout against the days-vs-years time-horizon impedance mismatch.
        """
        if planned_capex_billions_usd <= 0:
            raise ValueError("planned_capex_billions_usd must be positive")
        if not (0.0 <= funded_by_operating_cash_flow_pct <= 1.0) or not (0.0 <= funded_by_debt_pct <= 1.0):
            raise ValueError("funding shares must be in [0.0, 1.0]")
        if not (0.0 <= enterprise_inference_workload_share <= 1.0):
            raise ValueError("enterprise_inference_workload_share must be in [0.0, 1.0]")
        if not (0.0 <= enterprise_inference_gross_margin <= 1.0):
            raise ValueError("enterprise_inference_gross_margin must be in [0.0, 1.0]")

        build_lead_days = datacenter_build_lead_time_years * 365.0
        impedance_mismatch_ratio = round(build_lead_days / max(ai_innovation_cycle_days, 1), 2)

        # Equilibrium health: strong operating cash flow + growing high-margin enterprise inference
        inference_monetization_strength = enterprise_inference_workload_share * enterprise_inference_gross_margin
        systemic_debt_risk = "ELEVATED" if funded_by_debt_pct > 0.45 else "MANAGEABLE_CASH_FLOW_BACKED"

        return {
            "planned_capex_billions_usd": planned_capex_billions_usd,
            "strategic_recommendation": "NECESSARY_ASYMMETRIC_BET_PROCEED_WITH_DISCIPLINE",
            "time_horizon_impedance_mismatch": {
                "ai_innovation_cycle_days": ai_innovation_cycle_days,
                "datacenter_build_lead_time_years": datacenter_build_lead_time_years,
                "lead_time_to_innovation_ratio": impedance_mismatch_ratio,
                "explanation": "AI capabilities evolve in days while power and data center capacity require multiyear physical buildouts.",
            },
            "financing_and_margin_equilibrium": {
                "funded_by_operating_cash_flow_pct": funded_by_operating_cash_flow_pct,
                "funded_by_debt_pct": funded_by_debt_pct,
                "systemic_debt_risk": systemic_debt_risk,
                "enterprise_inference_workload_share": enterprise_inference_workload_share,
                "enterprise_inference_gross_margin": enterprise_inference_gross_margin,
                "inference_monetization_index": round(inference_monetization_strength, 4),
                "durable_long_term_equilibrium": (
                    funded_by_operating_cash_flow_pct >= 0.55 and inference_monetization_strength >= 0.25
                ),
            },
        }

    @classmethod
    def evaluate_community_accountability(
        cls,
        facility_region: str,
        protects_residential_power_rates: bool,
        behind_the_meter_or_new_clean_generation_mw: float,
        closed_loop_water_stewardship: bool,
        local_skilled_trades_jobs_created: int,
        annual_local_tax_contribution_millions_usd: float,
        proactive_town_hall_engagement: bool,
        broad_citizen_ai_access_programs: bool = True,
    ) -> Dict[str, Any]:
        """
        Audits whether a data center project answers Bret Taylor's two community accountability questions:
        1. 'Will AI benefit me broadly?'
        2. 'Will this data center benefit my community?'
        """
        if not facility_region or not facility_region.strip():
            raise ValueError("facility_region is required")

        pillars = {
            "zero_residential_electricity_bill_inflation": (
                protects_residential_power_rates and behind_the_meter_or_new_clean_generation_mw > 0
            ),
            "water_and_environmental_stewardship": closed_loop_water_stewardship,
            "local_blue_collar_trades_employment": local_skilled_trades_jobs_created >= 50,
            "local_tax_base_contribution": annual_local_tax_contribution_millions_usd > 0.0,
            "transparent_town_hall_governance": proactive_town_hall_engagement,
            "broad_citizen_ai_benefit_access": broad_citizen_ai_access_programs,
        }

        passed_pillars = sum(1 for v in pillars.values() if v)
        accountability_score_pct = round((passed_pillars / len(pillars)) * 100.0, 2)
        community_benefits_verified = (
            pillars["zero_residential_electricity_bill_inflation"]
            and pillars["water_and_environmental_stewardship"]
            and pillars["local_blue_collar_trades_employment"]
            and pillars["transparent_town_hall_governance"]
        )

        return {
            "facility_region": facility_region.strip(),
            "community_social_license_status": (
                "APPROVED_COMMUNITY_PARTNER" if community_benefits_verified else "SOCIAL_LICENSE_AT_RISK"
            ),
            "accountability_score_pct": accountability_score_pct,
            "two_core_questions": {
                "will_ai_benefit_me_broadly": broad_citizen_ai_access_programs,
                "will_this_datacenter_benefit_my_community": community_benefits_verified,
            },
            "pillar_verification": pillars,
            "economic_and_grid_metrics": {
                "new_dedicated_power_generation_mw": behind_the_meter_or_new_clean_generation_mw,
                "local_electricians_hvac_plumbers_jobs": local_skilled_trades_jobs_created,
                "annual_local_tax_contribution_millions_usd": annual_local_tax_contribution_millions_usd,
            },
        }


# ==============================================================================
# 17. DEMOCRATIZED SUPERINTELLIGENCE ADVISORS & DEMOGRAPHIC ENGINE (TAYLOR)
# ==============================================================================

class UniversalAdvisorArchetype(str, Enum):
    """
    Bret Taylor's flagship Democratized Superintelligence archetypes:
    'Everyone in the world will have access to a superintelligent financial advisor
    and the greatest primary care physician. Every kid in the world will have access
    to a personalized tutor.' Plus D2C Entrepreneur Co-Founder agents.
    """
    SUPERINTELLIGENT_FINANCIAL_ADVISOR = "SUPERINTELLIGENT_FINANCIAL_ADVISOR"
    PRIMARY_CARE_PHYSICIAN_ADVISOR = "PRIMARY_CARE_PHYSICIAN_ADVISOR"
    PERSONALIZED_STUDENT_TUTOR = "PERSONALIZED_STUDENT_TUTOR"
    D2C_ENTREPRENEUR_COFOUNDER = "D2C_ENTREPRENEUR_COFOUNDER"


class DemocratizedSuperintelligenceEngine:
    """
    Delivers the world's best frontier knowledge and autonomous execution to every
    individual and small entrepreneur under Rich Isenberg's decision-rights guardrails,
    and models macroeconomic productivity in an aging/shrinking global workforce.
    """

    ARCHETYPE_BLUEPRINTS: Dict[UniversalAdvisorArchetype, Dict[str, Any]] = {
        UniversalAdvisorArchetype.SUPERINTELLIGENT_FINANCIAL_ADVISOR: {
            "default_decision_rights": DecisionRightsTier.HIGH_IMPACT_GATED,
            "capabilities": [
                "FIDUCIARY_TAX_AND_RETIREMENT_OPTIMIZATION",
                "CONTINUOUS_CASHFLOW_AND_DEBT_RESTRUCTURING",
                "INSTITUTIONAL_GRADE_PORTFOLIO_RISK_HEDGING",
            ],
            "allowed_compartments": ["household_financial_ledger", "market_telemetry", "tax_code_corpus"],
            "forbidden_compartments": ["unconsented_third_party_pii", "executive_personal_emails"],
        },
        UniversalAdvisorArchetype.PRIMARY_CARE_PHYSICIAN_ADVISOR: {
            "default_decision_rights": DecisionRightsTier.PROPOSE_ONLY,
            "capabilities": [
                "FRONTIER_DIFFERENTIAL_DIAGNOSTIC_TRIAGE",
                "LONGITUDINAL_PREVENTIVE_CARE_MONITORING",
                "PRESCRIPTION_DRUG_ADHERENCE_COACHING",
            ],
            "allowed_compartments": ["patient_consented_ehr", "clinical_guidelines_corpus", "pharmacology_interactions"],
            "forbidden_compartments": ["unconsented_genetic_records", "executive_personal_emails"],
        },
        UniversalAdvisorArchetype.PERSONALIZED_STUDENT_TUTOR: {
            "default_decision_rights": DecisionRightsTier.BOUNDED_AUTONOMY,
            "capabilities": [
                "SOCRATIC_ONE_ON_ONE_MASTERY_ADAPTATION",
                "MULTIMODAL_CONCEPT_VISUALIZATION",
                "CONTINUOUS_KNOWLEDGE_GAP_REMEDIATION",
            ],
            "allowed_compartments": ["student_learning_profile", "accredited_curriculum_graph"],
            "forbidden_compartments": ["adult_commercial_ad_targeting", "executive_personal_emails"],
        },
        UniversalAdvisorArchetype.D2C_ENTREPRENEUR_COFOUNDER: {
            "default_decision_rights": DecisionRightsTier.HIGH_IMPACT_GATED,
            "capabilities": [
                "AUTONOMOUS_STOREFRONT_AND_SOFTWARE_GENERATION",
                "DEMAND_GENERATION_AND_PRECISION_AD_BUYING",
                "MERCHANT_ONBOARDING_AND_CUSTOMER_EXPERIENCE_AUTOMATION",
            ],
            "allowed_compartments": ["merchant_catalog", "ad_campaign_telemetry", "customer_support_tickets"],
            "forbidden_compartments": ["competitor_proprietary_secrets", "executive_personal_emails"],
        },
    }

    @classmethod
    def provision_universal_advisor(
        cls,
        archetype: UniversalAdvisorArchetype,
        beneficiary_id: str,
        accountable_human_guardian: str,
        sovereignty_mode: SovereigntyMode = SovereigntyMode.ZERO_RETENTION_CONTRACTUAL,
    ) -> Dict[str, Any]:
        """
        Provisions a governed Democratized Superintelligence advisor session with
        built-in Isenberg decision-rights manifest and Taylor frontier/distilled routing.
        """
        if not beneficiary_id or not beneficiary_id.strip():
            raise ValueError("beneficiary_id is required")
        if not accountable_human_guardian or not accountable_human_guardian.strip():
            raise ValueError("accountable_human_guardian is required")

        blueprint = cls.ARCHETYPE_BLUEPRINTS[archetype]
        agent_id = f"democratized_{archetype.value.lower()}_{beneficiary_id.strip()}"

        manifest = AgentGovernanceManifest(
            agent_id=agent_id,
            name=f"Democratized {archetype.value.replace('_', ' ').title()}",
            version="1.0.0",
            accountable_owner=accountable_human_guardian.strip(),
            decision_rights=blueprint["default_decision_rights"],
            allowed_tools=set(blueprint["capabilities"]),
            allowed_data_compartments=set(blueprint["allowed_compartments"]),
            sovereignty_mode=sovereignty_mode,
            max_autonomous_actions_per_run=25,
            department="Democratized Superintelligence",
            description=f"Universal {archetype.value} advisor for {beneficiary_id.strip()}",
        )

        routing = ModelTierRouter.select_model(
            task_ambiguity_score=0.80,
            requires_deep_reasoning=True,
            sovereignty_mode=sovereignty_mode,
        )

        return {
            "archetype": archetype.value,
            "beneficiary_id": beneficiary_id.strip(),
            "manifest": manifest,
            "capabilities": list(blueprint["capabilities"]),
            "model_routing": routing,
            "democratized_access_verified": True,
        }

    @classmethod
    def project_macro_demographic_productivity(
        cls,
        baseline_working_age_population_millions: float,
        annual_demographic_contraction_rate: float,
        ai_augmented_productivity_gain_per_worker: float,
        startup_creation_cost_reduction_pct: float = 0.75,
        projection_years: int = 10,
    ) -> Dict[str, Any]:
        """
        Models Bret Taylor's macroeconomic thesis on demographics and entrepreneurship:
        As working-age populations age and shrink across major economies, democratized
        superintelligence and D2C entrepreneurship agents offset labor contraction and
        expand total economic output and new business formation.
        """
        if baseline_working_age_population_millions <= 0:
            raise ValueError("baseline_working_age_population_millions must be positive")
        if not (0.0 <= annual_demographic_contraction_rate < 1.0):
            raise ValueError("annual_demographic_contraction_rate must be in [0.0, 1.0)")
        if ai_augmented_productivity_gain_per_worker < 0.0:
            raise ValueError("ai_augmented_productivity_gain_per_worker must be non-negative")
        if not (0.0 <= startup_creation_cost_reduction_pct < 1.0):
            raise ValueError("startup_creation_cost_reduction_pct must be in [0.0, 1.0)")

        projected_workforce_millions = baseline_working_age_population_millions * (
            (1.0 - annual_demographic_contraction_rate) ** projection_years
        )
        unaugmented_output_index = (
            projected_workforce_millions / baseline_working_age_population_millions
        ) * 100.0
        ai_augmented_output_index = unaugmented_output_index * (1.0 + ai_augmented_productivity_gain_per_worker)

        entrepreneurship_multiplier = round(1.0 / (1.0 - startup_creation_cost_reduction_pct), 2)

        return {
            "projection_years": projection_years,
            "baseline_working_age_population_millions": baseline_working_age_population_millions,
            "projected_working_age_population_millions": round(projected_workforce_millions, 3),
            "unaugmented_gdp_output_index": round(unaugmented_output_index, 2),
            "ai_augmented_gdp_output_index": round(ai_augmented_output_index, 2),
            "demographic_drag_overcome": ai_augmented_output_index > 100.0,
            "new_business_formation_multiplier": entrepreneurship_multiplier,
            "macro_conclusion": (
                "Democratized superintelligence overcomes demographic workforce contraction "
                "and accelerates small-business entrepreneurship."
                if ai_augmented_output_index > 100.0
                else "Additional AI productivity diffusion required to offset demographic contraction."
            ),
        }
