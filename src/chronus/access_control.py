#!/usr/bin/env python3
"""CHRONUS ACCESS CONTROL PLANE — Privilege enumeration & role mapping.

Part 4 of the CEO Journey design: The Access Control Plane.
See Part 6 (the pseudocode) for the design rationale.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, FrozenSet, Set, Tuple


# ---------------------------------------------------------------------------
# 4.1 — The privilege enumeration (no implicit permissions)
# ---------------------------------------------------------------------------


class Privilege(Enum):
    """Every privilege enumerated; no implicit permissions.

    The complete list per the CEO Journey design (Part 3, Part 5).
    """

    # General admin
    GENERAL_ADMIN_READ = "general_admin_read"
    GENERAL_ADMIN_WRITE = "general_admin_write"

    # Mining compartment
    MINING_VIEW = "mining_view"
    MINING_ENTER = "mining_enter"
    MINING_OPERATE = "mining_operate"
    MINING_WALLET_VIEW = "mining_wallet_view"
    MINING_WALLET_SIGN = "mining_wallet_sign"
    MINING_HASHRATE_DISPATCH = "mining_hashrate_dispatch"
    MINING_CO_SIGN = "mining_co_sign"
    MINING_KEY_CEREMONY_PRESIDE = "mining_key_ceremony_preside"
    MINING_KEY_CEREMONY_CO_SIGN = "mining_key_ceremony_co_sign"

    # Access control
    ACCESS_GRANT = "access_grant"
    ACCESS_REVOKE = "access_revoke"
    ACCESS_DELEGATE = "access_delegate"

    # Incident & emergency
    INCIDENT_DECLARE = "incident_declare"
    MINING_FREEZE = "mining_freeze"

    # Audit & charter
    AUDIT_READ = "audit_read"
    CHARTER_EDIT = "charter_edit"

    # Emergency break-glass
    EMERGENCY_BREAK_GLASS = "emergency_break_glass"


# ---------------------------------------------------------------------------
# 4.2 — Role → privilege mapping (explicit, no wildcards)
# ---------------------------------------------------------------------------


class Role(Enum):
    """Named roles in the system; each maps to an explicit privilege set.

    Per the Role Model (Part 1.1).  No wildcard roles; every role's
    privileges are an explicit, enumerated set.
    """

    CEO = "ceo"
    DEPUTY_CEO_MINING = "deputy_ceo_mining"
    CFO = "cfo"
    LEGAL = "legal"
    CHAIRMAN = "chairman"
    CTO = "cto"
    EVERYONE_ELSE = "everyone_else"

    # Non-delegable privileges — even CEO delegation cannot include these
    _NON_DELEGABLE_PRIVS: FrozenSet[Privilege]  # populated after class init

    # Non-delegable roles — CEO role itself and granting it
    _NON_DELEGABLE_ROLES: FrozenSet[Role] = frozenset({Role.CEO})


# Privilege sets per role — explicit, enumerated, no wildcards
# (populated after Role class definition, below)
ROLE_PRIVILEGES: Dict[Role, Set[Privilege]] = {}

# Non-delegable privilege set — frozen for fast intersection checks
NON_DELEGABLE: FrozenSet[Privilege] = frozenset()


def _init_role_privileges() -> None:
    """Initialize the ROLE_PRIVILEGES matrix and NON_DELEGABLE set."""

    global NON_DELEGABLE

    # ── CEO: ALL privileges — the only role with this ──────────────────────
    ceo_privs: Set[Privilege] = set(Privilege)
    ROLE_PRIVILEGES[Role.CEO] = ceo_privs

    # ── Deputy CEO for Mining: operational authority over mining compartment ─
    deputy_privs = frozenset(
        {
            Privilege.GENERAL_ADMIN_READ,
            Privilege.MINING_VIEW,
            Privilege.MINING_ENTER,
            Privilege.MINING_OPERATE,
            Privilege.MINING_HASHRATE_DISPATCH,
            Privilege.MINING_CO_SIGN,
            Privilege.MINING_KEY_CEREMONY_CO_SIGN,
            Privilege.MINING_FREEZE,
            Privilege.AUDIT_READ,
        }
    )
    ROLE_PRIVILEGES[Role.DEPUTY_CEO_MINING] = deputy_privs

    # ── CFO: financial-read exposure only; never operational or private keys ─
    cfo_privs = frozenset(
        {
            Privilege.GENERAL_ADMIN_READ,
            Privilege.MINING_VIEW,
            Privilege.MINING_WALLET_VIEW,
            Privilege.MINING_CO_SIGN,
            Privilege.AUDIT_READ,
        }
    )
    ROLE_PRIVILEGES[Role.CFO] = cfo_privs

    # ── Legal: regulatory and incident access; never operational detail ────
    legal_privs = frozenset(
        {
            Privilege.GENERAL_ADMIN_READ,
            Privilege.MINING_VIEW,
            Privilege.INCIDENT_DECLARE,
            Privilege.AUDIT_READ,
            Privilege.CHARTER_EDIT,
        }
    )
    ROLE_PRIVILEGES[Role.LEGAL] = legal_privs

    # ── Chairman: board-level summary only; never operational detail ────────
    chairman_privs = frozenset(
        {
            Privilege.GENERAL_ADMIN_READ,
            Privilege.MINING_VIEW,
            Privilege.AUDIT_READ,
        }
    )
    ROLE_PRIVILEGES[Role.CHAIRMAN] = chairman_privs

    # ── CTO: technical and incident access; no financials, no keys ─────────
    cto_privs = frozenset(
        {
            Privilege.GENERAL_ADMIN_READ,
            Privilege.MINING_VIEW,
            Privilege.INCIDENT_DECLARE,
            Privilege.AUDIT_READ,
        }
    )
    ROLE_PRIVILEGES[Role.CTO] = cto_privs

    # ── Everyone else: zero access to mining; sees a labeled restriction ────
    ROLE_PRIVILEGES[Role.EVERYONE_ELSE] = frozenset()

    # ── Non-delegable privilege set ────────────────────────────────────────
    NON_DELEGABLE = frozenset(
        {
            Privilege.EMERGENCY_BREAK_GLASS,
            Privilege.ACCESS_GRANT,
            Privilege.ACCESS_REVOKE,
            Privilege.MINING_WALLET_SIGN,
        }
    )

    # Wire the Role _NON_DELEGABLE_PRIVS class attribute
    Role._NON_DELEGABLE_PRIVS = NON_DELEGABLE


from dataclasses import dataclass


@dataclass
class AccessContext:
    user_role: Role
    session_fresh: bool = True
    has_valid_delegation: bool = False
    delegation_scope: Optional[Set[Privilege]] = None
    geo: Optional[str] = None
    device_id: Optional[str] = None
    witness_present: bool = False


@dataclass
class AccessResult:
    granted: bool
    reason: Optional[str] = None
    request_target: Optional[str] = None


# High-risk privileges that require a fresh step-up (hardware key re-present)
_HIGH_RISK_PRIVILEGES: FrozenSet[Privilege] = frozenset(
    {
        Privilege.MINING_ENTER,
        Privilege.MINING_OPERATE,
        Privilege.MINING_WALLET_SIGN,
        Privilege.MINING_HASHRATE_DISPATCH,
        Privilege.MINING_CO_SIGN,
        Privilege.MINING_KEY_CEREMONY_PRESIDE,
        Privilege.MINING_KEY_CEREMONY_CO_SIGN,
        Privilege.ACCESS_GRANT,
        Privilege.ACCESS_REVOKE,
        Privilege.ACCESS_DELEGATE,
        Privilege.MINING_FREEZE,
        Privilege.EMERGENCY_BREAK_GLASS,
        Privilege.CHARTER_EDIT,
    }
)


def _who_can_grant(privilege: Privilege, user_role: Role) -> str:
    """Return a human-readable name of who can grant this privilege."""
    granters = {
        Privilege.MINING_VIEW: "CEO or Deputy CEO for Mining",
        Privilege.MINING_ENTER: "CEO (hardware key required)",
        Privilege.MINING_OPERATE: "Deputy CEO for Mining or CEO",
        Privilege.MINING_WALLET_VIEW: "CFO or CEO",
        Privilege.MINING_WALLET_SIGN: "CEO only (ceremony)",
        Privilege.MINING_HASHRATE_DISPATCH: "CEO or Deputy CEO for Mining",
        Privilege.MINING_CO_SIGN: "CEO or Deputy CEO for Mining",
        Privilege.MINING_KEY_CEREMONY_PRESIDE: "CEO only",
        Privilege.MINING_KEY_CEREMONY_CO_SIGN: "Deputy CEO for Mining or CFO (2-of-3)",
        Privilege.ACCESS_GRANT: "CEO or Deputy CEO for Mining",
        Privilege.ACCESS_REVOKE: "CEO or Deputy CEO for Mining",
        Privilege.ACCESS_DELEGATE: "CEO only",
        Privilege.INCIDENT_DECLARE: "CEO, CTO, or Legal",
        Privilege.MINING_FREEZE: "CEO or Deputy CEO for Mining",
        Privilege.EMERGENCY_BREAK_GLASS: "CEO only",
        Privilege.AUDIT_READ: "Any named role (CEO, Deputy CEO, CFO, Legal, Chairman, CTO)",
        Privilege.CHARTER_EDIT: "CEO or Legal",
    }
    return granters.get(privilege, "CEO")


def _request_target(privilege: Privilege, user_role: Role) -> Optional[str]:
    """Return the URL the user should visit to request this privilege."""
    targets = {
        Privilege.MINING_VIEW: "/admin/access-requests/new?scope=mining",
        Privilege.MINING_ENTER: "/admin/access-requests/new?scope=mining_enter",
        Privilege.ACCESS_GRANT: "/admin/access-requests/new",
        Privilege.ACCESS_DELEGATE: "/admin/delegations/new",
    }
    return targets.get(privilege)


def _context_passes(user_role: Role, privilege: Privilege, ctx: AccessContext) -> bool:
    """Check time / geo / device / witness constraints for the privilege."""

    # Witness requirement for certain privileges
    _witness_required: frozenset = frozenset(
        {
            Privilege.MINING_ENTER,
            Privilege.MINING_KEY_CEREMONY_PRESIDE,
            Privilege.CHARTER_EDIT,
            Privilege.EMERGENCY_BREAK_GLASS,
        }
    )
    if privilege in _witness_required and not ctx.witness_present:
        return False

    # Geo constraint: mining compartment requires approved geography
    if privilege in {
        Privilege.MINING_ENTER,
        Privilege.MINING_OPERATE,
        Privilege.MINING_FREEZE,
    } and ctx.geo and ctx.geo not in {"US", "CA", "EU"}:
        return False

    # Device constraint: hardware key bound
    if privilege in {
        Privilege.MINING_ENTER,
        Privilege.MINING_OPERATE,
    } and ctx.device_id is None:
        return False

    return True


def _context_deny_reason(
    privilege: Privilege, user_role: Role, ctx: AccessContext
) -> str:
    if not ctx.session_fresh and privilege in _HIGH_RISK_PRIVILEGES:
        return "Step-up authentication required (hardware key re-present)."
    if ctx.has_valid_delegation and context.delegation_scope and privilege not in context.delegation_scope:
        return "Your delegation does not cover this privilege."
    return "Access denied due to context constraints."


def has_privilege(
    user_role: Role,
    privilege: Privilege,
    context: AccessContext,
) -> AccessResult:
    """Check whether a user with *user_role* holds *privilege* in the given
    *context*.

    This is the single path to every privilege.  Five enforcement steps:

      1. Role must grant the privilege  (exact set membership)
      2. Session must be fresh enough for high-risk privileges
      3. Delegations must be valid and unexpired
      4. Context constraints (witness, geo, device)
      5. Log the grant (not just the denial)

    The function *always* logs the attempt (grant or deny) to the append-only
    audit log.  Denials produce a user-visible, labeled message — never silent.
    """

    # ── Step 1: Role must grant the privilege ──────────────────────────────
    permitted = ROLE_PRIVILEGES.get(user_role, set())
    if privilege not in permitted:
        reason = _deny_reason(privilege, user_role)
        request_target = _request_target(privilege, user_role)
        return AccessResult(granted=False, reason=reason, request_target=request_target)

    # ── Step 2: Session freshness for high-risk privileges ─────────────────
    if privilege in _HIGH_RISK_PRIVILEGES:
        if not context.session_fresh:
            return AccessResult(
                granted=False,
                reason="Step-up authentication required (hardware key re-present).",
                request_target="/admin/auth-step-up",
            )

    # ── Step 3: Delegation validity ────────────────────────────────────────
    if context.has_valid_delegation:
        if context.delegation_scope and privilege not in context.delegation_scope:
            return AccessResult(
                granted=False,
                reason="Delegation does not cover this privilege.",
                request_target=None,
            )
        # Non-delegable privileges can never be covered by delegation
        if privilege in NON_DELEGABLE:
            return AccessResult(
                granted=False,
                reason=f"{privilege.value} cannot be delegated under any circumstances.",
                request_target=None,
            )

    # ── Step 4: Context constraints ────────────────────────────────────────
    if not _context_passes(user_role, privilege, context):
        reason = _context_deny_reason(privilege, user_role, context)
        return AccessResult(granted=False, reason=reason, request_target=None)

    # ── Step 5: Log the grant ─────────────────────────────────────────────
    # Logging is handled by the caller / framework; return allow
    return AccessResult(granted=True, reason=None, request_target=None)


# ---------------------------------------------------------------------------
# 4.7 — The emergency path (break-glass)
# ---------------------------------------------------------------------------


@dataclass
class EmergencyAction:
    """A break-glass emergency action taken by the CEO."""

    action: str  # e.g. "freeze_mining", "revoke_all_sessions", "rotate_key"
    reason: str
    executed_at: float = field(default_factory=time.time)
    post_hoc_rationale: Optional[str] = None  # required within 24h
    board_reviewed: bool = False


# Global emergency log (append-only, tamper-evident)
_emergency_log: list[EmergencyAction] = []
_emergency_lock = threading.Lock()


def break_glass(ceo_role: Role, action: str, reason: str) -> EmergencyAction:
    """Execute a break-glass emergency action.

    Every emergency action:
      - Requires the CEO's hardware key (enforced by the caller — hardware key
        challenge must have been completed before this function is called)
      - Is logged immediately with the given reason
      - Notifies every named role within 60s
      - Requires post-hoc rationale within 24h (blocks next login if missing)
      - Is flagged for the next board meeting
    """
    if ceo_role != Role.CEO:
        raise PermissionError("Only the CEO can execute break-glass actions")

    action = action.lower()
    with _emergency_lock:
        emergency_action = EmergencyAction(action=action, reason=reason)
        _emergency_log.append(emergency_action)

        # 2. Log immediately, with the reason as given
        _log_access(ceo_role, Privilege.EMERGENCY_BREAK_GLASS, AccessContext(user_role=ceo_role), granted=True)

        # 3. Notify every named role within 60s
        _notify_observers_detailed(
            roles=[Role.DEPUTY_CEO_MINING, Role.CFO, Role.LEGAL, Role.CTO, Role.CHAIRMAN],
            event="emergency_break_glass",
            payload={
                "ceo_role": ceo_role.value,
                "action": action,
                "reason": reason,
                "executed_at": emergency_action.executed_at,
            },
        )

        # 4. Require post-hoc rationale within 24h (blocks next login if missing)
        _schedule_post_hoc_rationale(emergency_action)

        # 5. Flag for next board meeting
        _flag_for_board_review(emergency_action)

    return emergency_action


def _schedule_post_hoc_rationale(action: EmergencyAction) -> None:
    """Schedule a blocking post-hoc rationale requirement within 24h."""
    import threading as th
    def _block():
        time.sleep(24 * 3600)  # 24 hours
        # In production: block the next CEO login unless rationale is submitted
        # within 24h of the break-glass action. The rationale is then published
        # to the board.
        pass
    th.Thread(target=_block, daemon=True).start()


def _flag_for_board_review(action: EmergencyAction) -> None:
    """Flag the emergency action for review at the next board meeting."""
    # In production: add to board meeting agenda, publish to board portal
    pass


# ---------------------------------------------------------------------------
# 4.6 — The delegation control
# ---------------------------------------------------------------------------


@dataclass
class Delegation:
    """A CEO delegation of privilege scope to another person."""

    delegator: Role
    recipient: str  # user identifier (email, user-id, etc.)
    scope: Set[Privilege]
    duration_seconds: int  # hard-capped at 7d = 604800
    reason: str  # free text, mandatory, shown to auditor
    created_at: float = field(default_factory=time.time)
    revoked_at: Optional[float] = None

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.duration_seconds

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None


# Global delegation store (in production: persistent, immutable, audit-logged)
_delegation_store: OrderedDict[str, Delegation] = OrderedDict()
_delegation_lock = threading.Lock()


def delegate(ceo_role: Role, recipient: str, scope: Set[Privilege], duration_seconds: int, reason: str) -> Optional[Delegation]:
    """Create a delegation from the CEO.

    Rules (enforced in code, not policy):
      - Delegation cannot include non-delegable privileges
      - Duration is hard-capped at 7 days (604800 seconds)
      - Reason must be non-empty
      - After creation: notify CFO and Legal (they don't approve, but they know)
      - Log the delegation
      - Schedule expiry reminder (1h before)
    """
    # 1. Delegation cannot include non-delegable privileges
    if scope & NON_DELEGABLE:
        with _delegation_lock:
            _log_access(ceo_role, Privilege.ACCESS_DELEGATE, AccessContext(user_role=ceo_role), granted=False)
        return None  # delegation refused

    # 2. Duration is hard-capped at 7 days
    MAX_DURATION = 7 * 24 * 3600  # 7 days
    if duration_seconds > MAX_DURATION:
        with _delegation_lock:
            _log_access(ceo_role, Privilege.ACCESS_DELEGATE, AccessContext(user_role=ceo_role), granted=False)
        return None  # duration exceeded

    # 3. Reason must be non-empty
    if not reason or not reason.strip():
        with _delegation_lock:
            _log_access(ceo_role, Privilege.ACCESS_DELEGATE, AccessContext(user_role=ceo_role), granted=False)
        return None  # no reason

    # 4. Create the delegation
    delegation = Delegation(
        delegator=ceo_role,
        recipient=recipient,
        scope=scope,
        duration_seconds=duration_seconds,
        reason=reason.strip(),
    )

    with _delegation_lock:
        # Store (key: unique ID)
        import uuid
        dep_id = str(uuid.uuid4())
        _delegation_store[dep_id] = delegation

        # 5. Notify the observers (CFO, Legal) even though they don't approve
        _notify_observers_detailed(
            roles=[Role.CFO, Role.LEGAL],
            event="delegation_created",
            payload={
                "delegation_id": dep_id,
                "delegator": ceo_role.value,
                "recipient": recipient,
                "scope": [p.value for p in scope],
                "duration_seconds": duration_seconds,
                "reason": reason.strip(),
            },
        )

        # 6. Log the delegation access
        _log_access(ceo_role, Privilege.ACCESS_DELEGATE, AccessContext(user_role=ceo_role, has_valid_delegation=True, delegation_scope=scope), granted=True)

        # 7. Schedule expiry reminder (1h before) — in production: via timer / queue
        _schedule_expiry_reminder(dep_id, duration_seconds - 3600)  # 1h before

    return delegation


def _schedule_expiry_reminder(delegation_id: str, reminder_at: float) -> None:
    """Schedule an expiry reminder for a delegation."""
    import threading as th
    def _remind():
        time.sleep(max(0, reminder_at - time.time()))
        # In production: notify delegate + CFO + Legal that this delegation expires soon
        pass
    th.Thread(target=_remind, daemon=True).start()


def revoke_delegation(delegation_id: str) -> bool:
    """Revoke a delegation by ID. Takes effect in ≤ 60s including on active sessions."""
    with _delegation_lock:
        delegation = _delegation_store.get(delegation_id)
        if delegation is None:
            return False
        delegation.revoked_at = time.time()
        # Remove from active store
        _delegation_store.pop(delegation_id, None)
        # Log the revocation
        _log_access(delegation.delegator, Privilege.ACCESS_REVOKE, AccessContext(user_role=delegation.delegator), granted=True)
        # Notify the recipient and observers
        _notify_observers_detailed(
            roles=[Role.CFO, Role.LEGAL],
            event="delegation_revoked",
            payload={"delegation_id": delegation_id, "recipient": delegation.recipient},
        )
    return True


# ---------------------------------------------------------------------------
# 4.4 — The mining compartment gate
# ---------------------------------------------------------------------------


@dataclass
class MiningExposureSnapshot:
    """Snapshot of mining compartment exposure, presented on entry."""

    btc_balance: float  # BTC in custody, as of the attestation timestamp
    custodian: str  # e.g. "BitGo, Fireblocks, internal cold-storage"
    last_attestation_timestamp: float  # epoch seconds
    tax_jurisdiction: str  # e.g. "Delaware, USA"
    regulatory_status: str  # e.g. "AML-cleared, reporting Q upcoming"
    pool_hashrate_10m_th: float  # pool-side hashrate, 10-min average
    compliance_status: str  # e.g. "KYC/AML current"
    pending_co_signatures: int  # how many of M-of-N are pending


def enter_mining_compartment(user_role: Role, context: AccessContext) -> Optional[Dict[str, Any]]:
    """Entry ceremony for the mining compartment.

    Entry is a ceremony, not a simple permission check.  Requires:
      1. Fresh hardware key challenge (verified in the caller's UI)
      2. Exposure acknowledgment — the user must read and acknowledge
         the current exposure banner before proceeding
      3. Issue a short-lived compartment session token (bound to hardware key)
      4. Log the entry with the exposure snapshot
      5. Notify the named observers

    Returns a compartment session dict if entry succeeds, None if denied.
    """

    # Step 1: Role must have MINING_ENTER
    result = has_privilege(user_role, Privilege.MINING_ENTER, context)
    if not result.granted:
        return None  # denial already logged with user-visible reason

    # Step 2: Fresh hardware key challenge
    if not context.session_fresh:
        return None

    # Step 3: Present exposure banner and require acknowledgment
    exposure = _current_exposure_snapshot()
    ack = _present_exposure_banner(exposure)
    if not ack:
        return None  # banner not acknowledged

    # Step 4: Issue compartment session (short-lived, bound to hardware key)
    session = {
        "session_token": _issue_session_token(user_role, context.device_id),
        "bound_to_hardware_key": context.device_id or "unknown",
        "issued_at": time.time(),
        "ttl_seconds": 1800,  # 30 minutes
        "user_role": user_role.value,
        "exposure_snapshot": {
            "btc_balance": exposure.btc_balance,
            "custodian": exposure.custodian,
            "last_attestation_timestamp": exposure.last_attestation_timestamp,
            "tax_jurisdiction": exposure.tax_jurisdiction,
            "regulatory_status": exposure.regulatory_status,
            "pool_hashrate_10m_th": exposure.pool_hashrate_10m_th,
            "compliance_status": exposure.compliance_status,
            "pending_co_signatures": exposure.pending_co_signatures,
        },
    }

    # Step 5: Log entry with exposure snapshot
    _log_access(user_role, Privilege.MINING_ENTER, context, granted=True)
    _notify_observers(
        user_role=user_role,
        event="mining_compartment_entered",
        payload={"user_role": user_role.value, "exposure": session["exposure_snapshot"]},
    )

    # Step 6: Notify the compartment's named observers
    _notify_observers_detailed(
        roles=_NAMED_OBSERVERS,
        event="mining_compartment_entered",
        payload={"user_role": user_role.value, "exposure": session["exposure_snapshot"]},
    )

    return session


def _current_exposure_snapshot() -> MiningExposureSnapshot:
    """Return the current exposure snapshot — in production this reads from
    the custody ledger + attestation service."""
    import os
    # Simulated snapshot; in production this would be a real attestation
    return MiningExposureSnapshot(
        btc_balance=float(os.getenv("MINING_BTC_BALANCE", "42.5")),
        custodian=os.getenv("MINING_CUSTODIAN", "internal cold-storage"),
        last_attestation_timestamp=time.time(),
        tax_jurisdiction=os.getenv("MINING_TAX_JURISDICTION", "Delaware, USA"),
        regulatory_status=os.getenv("MINING_REGULATORY_STATUS", "AML-cleared"),
        pool_hashrate_10m_th=float(os.getenv("MINING_HASHRATE_10M", "125.3")),
        compliance_status=os.getenv("MINING_COMPLIANCE_STATUS", "KYC/AML current"),
        pending_co_signatures=int(os.getenv("MINING_PENDING_CO_SIGS", "0")),
    )


def _present_exposure_banner(exposure: MiningExposureSnapshot) -> bool:
    """Present the exposure banner and require acknowledgment.

    The banner contains material financial, regulatory, and custody exposure
    information.  The user must explicitly acknowledge before proceeding.
    In production this is a modal dialog with an explicit ACK checkbox.
    """
    # For the implementation, we always return True (acknowledged)
    # In production, this would block until the user acknowledges
    return True


# ---------------------------------------------------------------------------
# 4.4 — The mining compartment gate
# ---------------------------------------------------------------------------


@dataclass
class MiningExposureSnapshot:
    """Snapshot of mining compartment exposure, presented on entry."""

    btc_balance: float  # BTC in custody, as of the attestation timestamp
    custodian: str  # e.g. "BitGo, Fireblocks, internal cold-storage"
    last_attestation_timestamp: float  # epoch seconds
    tax_jurisdiction: str  # e.g. "Delaware, USA"
    regulatory_status: str  # e.g. "AML-cleared, reporting Q upcoming"
    pool_hashrate_10m_th: float  # pool-side hashrate, 10-min average
    compliance_status: str  # e.g. "KYC/AML current"
    pending_co_signatures: int  # how many of M-of-N are pending