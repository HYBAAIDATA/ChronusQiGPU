"""
HYBA_DATA Zero-Trust Security Implementation

Zero-trust security engine with RBAC, ABAC, MFA, and continuous verification.
Never trust, always verify.

Author: Andre Taylor-Morris — HYBA Software Ltd
"""
import time
import hashlib
import secrets
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class SecurityLevel(Enum):
    """Data classification levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    SECRET = "secret"
    TOP_SECRET = "top_secret"

    def __lt__(self, other):
        order = ["public", "internal", "confidential", "secret", "top_secret"]
        return order.index(self.value) < order.index(other.value)


class AccessDecision(Enum):
    """Access control decisions."""
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_MFA = "require_mfa"
    REQUIRE_REVIEW = "require_review"


@dataclass
class UserContext:
    """User context for authorization."""
    user_id: str
    roles: List[str]
    attributes: Dict[str, Any]
    clearance_level: SecurityLevel
    mfa_verified: bool = False
    ip_address: str = ""
    device_id: str = ""
    session_id: str = ""


@dataclass
class Resource:
    """Resource for authorization."""
    id: str
    type: str
    classification: SecurityLevel
    owner: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """Manages user sessions with expiry and verification."""

    def __init__(self, session_timeout: float = 3600):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = session_timeout

    def create_session(self, user_id: str, ip_address: str = "",
                       device_id: str = "") -> str:
        """Create a new session."""
        session_id = secrets.token_hex(16)
        self.sessions[user_id] = {
            "session_id": session_id,
            "ip_address": ip_address,
            "device_id": device_id,
            "created": time.time(),
            "last_verified": time.time(),
        }
        return session_id

    def verify_session(self, user_id: str, ip_address: str = "") -> bool:
        """Verify a user session."""
        session = self.sessions.get(user_id)
        if not session:
            return False
        if time.time() - session["last_verified"] > self.session_timeout:
            return False
        if ip_address and session.get("ip_address") != ip_address:
            return False
        session["last_verified"] = time.time()
        return True

    def revoke_session(self, user_id: str) -> bool:
        """Revoke a user session."""
        if user_id in self.sessions:
            del self.sessions[user_id]
            return True
        return False

    def get_active_sessions(self) -> int:
        """Get count of active sessions."""
        return sum(
            1 for s in self.sessions.values()
            if time.time() - s["last_verified"] <= self.session_timeout
        )


class ZeroTrustSecurity:
    """
    Zero-trust security engine with RBAC, ABAC, and continuous verification.
    Never trust, always verify.
    """

    def __init__(self):
        self.users: Dict[str, UserContext] = {}
        self.roles: Dict[str, List[str]] = {}  # role -> permissions
        self.policies: List[Dict[str, Any]] = []
        self.session_manager = SessionManager()
        self.mfa_secrets: Dict[str, str] = {}
        self.authorization_log: List[Dict[str, Any]] = []

    def register_user(self, user_id: str, roles: List[str],
                      attributes: Dict[str, Any],
                      clearance: SecurityLevel) -> None:
        """Register user for zero-trust access."""
        self.users[user_id] = UserContext(
            user_id=user_id,
            roles=roles,
            attributes=attributes,
            clearance_level=clearance,
        )

    def setup_mfa(self, user_id: str) -> str:
        """Set up MFA for a user. Returns the MFA secret."""
        secret = secrets.token_hex(20)
        self.mfa_secrets[user_id] = secret
        return secret

    def verify_mfa(self, user_id: str, code: str) -> bool:
        """Verify MFA code."""
        secret = self.mfa_secrets.get(user_id)
        if not secret:
            return False
        expected = hashlib.sha256(f"{secret}{int(time.time() / 30)}".encode()).hexdigest()[:6]
        return code == expected

    def create_session(self, user_id: str, ip_address: str = "",
                       device_id: str = "") -> str:
        """Create a user session."""
        return self.session_manager.create_session(user_id, ip_address, device_id)

    def define_policy(self, policy: Dict[str, Any]) -> None:
        """Define an access policy (RBAC + ABAC)."""
        self.policies.append(policy)

    def authorize(self, user_id: str, resource: Resource,
                  action: str) -> AccessDecision:
        """Authorize access using zero-trust principles."""
        user = self.users.get(user_id)
        if not user:
            self._log_auth(user_id, resource, action, "deny", "user_not_found")
            return AccessDecision.DENY

        # Continuous verification
        if not self.session_manager.verify_session(user_id, user.ip_address):
            self._log_auth(user_id, resource, action, "deny", "session_invalid")
            return AccessDecision.DENY

        # Check clearance level FIRST — deny immediately if insufficient
        if user.clearance_level < resource.classification:
            self._log_auth(user_id, resource, action, "deny", "insufficient_clearance")
            return AccessDecision.DENY

        # Check MFA requirement for sensitive resources (after clearance passes)
        if resource.classification in [SecurityLevel.SECRET, SecurityLevel.TOP_SECRET]:
            if not user.mfa_verified:
                self._log_auth(user_id, resource, action, "require_mfa", "mfa_required")
                return AccessDecision.REQUIRE_MFA

        # Evaluate policies
        for policy in self.policies:
            if policy.get("resource_type") != resource.type:
                continue
            if action not in policy.get("actions", []):
                continue
            # RBAC check
            if policy.get("roles"):
                if not any(role in user.roles for role in policy["roles"]):
                    continue
            # ABAC check
            if policy.get("conditions"):
                if not self._evaluate_conditions(policy["conditions"], user, resource):
                    continue
            # Found matching policy
            decision_str = policy.get("decision", "allow")
            decision = AccessDecision.ALLOW if decision_str == "allow" else AccessDecision.DENY
            self._log_auth(user_id, resource, action, decision.value, "policy_match")
            return decision

        # No matching policy -> deny by default
        self._log_auth(user_id, resource, action, "deny", "no_policy_match")
        return AccessDecision.DENY

    def _evaluate_conditions(self, conditions: Dict[str, Any],
                            user: UserContext, resource: Resource) -> bool:
        """Evaluate ABAC conditions."""
        for key, value in conditions.items():
            if key.startswith("user."):
                attr = key[5:]
                if user.attributes.get(attr) != value:
                    return False
            elif key.startswith("resource."):
                attr = key[9:]
                if resource.attributes.get(attr) != value:
                    return False
            elif key == "time":
                if not self._check_time_condition(value):
                    return False
        return True

    def _check_time_condition(self, condition: Dict[str, Any]) -> bool:
        """Check time-based conditions."""
        current_hour = time.gmtime().tm_hour
        if "allowed_hours" in condition:
            if current_hour not in condition["allowed_hours"]:
                return False
        return True

    def _log_auth(self, user_id: str, resource: Resource, action: str,
                  decision: str, reason: str) -> None:
        """Log authorization decision."""
        self.authorization_log.append({
            "timestamp": time.time(),
            "user_id": user_id,
            "resource": resource.id,
            "resource_type": resource.type,
            "classification": resource.classification.value,
            "action": action,
            "decision": decision,
            "reason": reason,
        })

    def get_authorization_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get authorization log."""
        return self.authorization_log[-limit:]

    def get_security_report(self) -> Dict[str, Any]:
        """Get security report."""
        total = len(self.authorization_log)
        allowed = sum(1 for e in self.authorization_log if e["decision"] == "allow")
        denied = sum(1 for e in self.authorization_log if e["decision"] == "deny")
        mfa_required = sum(1 for e in self.authorization_log if e["decision"] == "require_mfa")
        return {
            "total_authorizations": total,
            "allowed": allowed,
            "denied": denied,
            "mfa_required": mfa_required,
            "active_sessions": self.session_manager.get_active_sessions(),
            "registered_users": len(self.users),
            "defined_policies": len(self.policies),
            "mfa_enabled_users": len(self.mfa_secrets),
        }
