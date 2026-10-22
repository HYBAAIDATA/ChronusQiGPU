"""
HYBA_DATA Audit & Forensics Implementation

Immutable audit trail with blockchain-backed chain of custody.
Every event is cryptographically linked to the previous event using SHA3-256.

Author: Andre Taylor-Morris — HYBA Software Ltd
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AuditEvent:
    """Immutable audit event with tamper-evident hash chain."""
    id: str
    timestamp: float
    event_type: str
    actor: str
    action: str
    resource: str
    data: Dict[str, Any]
    previous_hash: str
    hash: str = field(init=False)

    def __post_init__(self):
        content = (
            f"{self.id}{self.timestamp}{self.event_type}{self.actor}"
            f"{self.action}{self.resource}{json.dumps(self.data, sort_keys=True, default=str)}"
            f"{self.previous_hash}"
        )
        self.hash = hashlib.sha3_256(content.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "data": self.data,
            "hash": self.hash,
            "previous_hash": self.previous_hash,
        }


@dataclass
class ForensicsReport:
    """Digital forensics report for incident response."""
    trail_name: str
    total_events: int
    chain_verified: bool
    broken_at: Optional[int]
    events_by_type: Dict[str, int]
    events_by_actor: Dict[str, int]
    time_range: Dict[str, float]
    suspicious_events: List[Dict[str, Any]]

    def to_dict(self) -> dict:
        return {
            "trail_name": self.trail_name,
            "total_events": self.total_events,
            "chain_verified": self.chain_verified,
            "broken_at": self.broken_at,
            "events_by_type": self.events_by_type,
            "events_by_actor": self.events_by_actor,
            "time_range": self.time_range,
            "suspicious_events": self.suspicious_events,
        }


class AuditTrail:
    """
    Immutable audit trail with blockchain-backed chain of custody.
    Every event is cryptographically linked to the previous event.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self.chain: List[AuditEvent] = []
        self.genesis_hash = hashlib.sha3_256(
            f"Genesis:{name}:{time.time()}".encode()
        ).hexdigest()
        self.last_hash = self.genesis_hash
        self.index = 0

    def log(self, event_type: str, actor: str, action: str,
            resource: str, data: Dict[str, Any] = None) -> AuditEvent:
        """Log an event to the audit trail."""
        event = AuditEvent(
            id=f"{self.name}:{self.index}",
            timestamp=time.time(),
            event_type=event_type,
            actor=actor,
            action=action,
            resource=resource,
            data=data or {},
            previous_hash=self.last_hash,
        )
        self.chain.append(event)
        self.last_hash = event.hash
        self.index += 1
        return event

    def verify_chain(self) -> Dict[str, Any]:
        """Verify the entire audit chain for tampering."""
        if not self.chain:
            return {"verified": True, "message": "Empty chain", "length": 0}

        current_hash = self.genesis_hash
        for i, event in enumerate(self.chain):
            if event.previous_hash != current_hash:
                return {
                    "verified": False,
                    "broken_at": i,
                    "expected": current_hash,
                    "found": event.previous_hash,
                    "length": len(self.chain),
                }
            # Recompute hash to check tampering
            content = (
                f"{event.id}{event.timestamp}{event.event_type}{event.actor}"
                f"{event.action}{event.resource}"
                f"{json.dumps(event.data, sort_keys=True, default=str)}"
                f"{event.previous_hash}"
            )
            expected_hash = hashlib.sha3_256(content.encode()).hexdigest()
            if event.hash != expected_hash:
                return {
                    "verified": False,
                    "broken_at": i,
                    "reason": "hash_mismatch",
                    "length": len(self.chain),
                }
            current_hash = event.hash

        return {
            "verified": True,
            "length": len(self.chain),
            "last_hash": current_hash,
        }

    def search(self, actor: str = None, event_type: str = None,
               start_time: float = None, end_time: float = None,
               resource: str = None) -> List[AuditEvent]:
        """Search audit trail with filters."""
        results = self.chain
        if actor:
            results = [e for e in results if e.actor == actor]
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if start_time:
            results = [e for e in results if e.timestamp >= start_time]
        if end_time:
            results = [e for e in results if e.timestamp <= end_time]
        if resource:
            results = [e for e in results if e.resource == resource]
        return results

    def export(self, format: str = "json") -> str:
        """Export audit trail for forensic analysis."""
        if format == "json":
            return json.dumps(
                [e.to_dict() for e in self.chain],
                indent=2, default=str,
            )
        return str(self.chain)

    def generate_forensics_report(self) -> ForensicsReport:
        """Generate a digital forensics report."""
        verification = self.verify_chain()

        events_by_type: Dict[str, int] = {}
        events_by_actor: Dict[str, int] = {}
        for event in self.chain:
            events_by_type[event.event_type] = events_by_type.get(event.event_type, 0) + 1
            events_by_actor[event.actor] = events_by_actor.get(event.actor, 0) + 1

        time_range = {}
        if self.chain:
            time_range = {
                "start": self.chain[0].timestamp,
                "end": self.chain[-1].timestamp,
                "duration": self.chain[-1].timestamp - self.chain[0].timestamp,
            }

        # Detect suspicious events (rapid sequences, denied accesses, etc.)
        suspicious = []
        for i, event in enumerate(self.chain):
            if event.event_type in ("auth_failed", "access_denied", "rate_limited"):
                suspicious.append(event.to_dict())
            # Detect rapid repeated actions (potential brute force)
            if i > 0 and event.actor == self.chain[i - 1].actor:
                if event.timestamp - self.chain[i - 1].timestamp < 0.1:
                    suspicious.append({
                        "event_id": event.id,
                        "reason": "rapid_repeated_action",
                        "timestamp": event.timestamp,
                    })

        return ForensicsReport(
            trail_name=self.name,
            total_events=len(self.chain),
            chain_verified=verification["verified"],
            broken_at=verification.get("broken_at"),
            events_by_type=events_by_type,
            events_by_actor=events_by_actor,
            time_range=time_range,
            suspicious_events=suspicious,
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get audit trail statistics."""
        return {
            "name": self.name,
            "total_events": len(self.chain),
            "chain_verified": self.verify_chain()["verified"],
            "genesis_hash": self.genesis_hash[:16] + "...",
            "last_hash": self.last_hash[:16] + "...",
        }
