"""Governance — Part XII: compliance map, escalation contacts, break
glass, and the append-only audit log (GOV1–GOV4)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from . import store as aethel_store
from .result import BREAK_GLASS_DENIED, Ok, Result, error
from .types import BreakGlassPolicy, Contact, digest_of


@dataclass
class BreakGlass:
    activated_at: float
    actor: str
    reason: str
    expires_at: float

    def active(self) -> bool:
        return time.time() < self.expires_at


class AuditLog:
    """Append-only JSONL audit log — no rewrite path exists."""

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else None
        self.entries: list[dict[str, Any]] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, action: str, subject: str, detail: dict[str, Any]) -> dict[str, Any]:
        entry = {
            "seq": len(self.entries),
            "ts": time.time(),
            "action": action,
            "subject": subject,
            "detail": detail,
            "digest": "",
        }
        entry["digest"] = digest_of(
            {"seq": entry["seq"], "action": action, "subject": subject, "detail": detail}
        )
        self.entries.append(entry)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, default=str) + "\n")
        return entry


@dataclass
class Governance:
    compliance_map: dict[str, list[str]]
    escalation: list[Contact]
    break_glass: Optional[BreakGlassPolicy]
    audit_log: AuditLog


def load_compliance(mappings: dict[str, list[str]]) -> dict[str, list[str]]:
    return {str(k): list(v) for k, v in mappings.items()}


def load_escalation(contacts: list[Contact]) -> list[Contact]:
    return list(contacts)


def load_break_glass(policy: Optional[BreakGlassPolicy]) -> Optional[BreakGlassPolicy]:
    return policy


def open_audit_log(cfg: Any) -> AuditLog:
    path = None
    if cfg.aethel_root and cfg.aethel_root != ":memory:":
        path = str(Path(cfg.aethel_root) / "lhras_audit.jsonl")
    return AuditLog(path)


def open_governance(cfg: Any) -> Result[Governance]:
    return Ok(
        Governance(
            compliance_map=load_compliance(cfg.compliance_mappings),
            escalation=load_escalation(cfg.escalation_contacts),
            break_glass=load_break_glass(cfg.break_glass_policy),
            audit_log=open_audit_log(cfg),
        )
    )


def break_glass_activate(lhras: Any, reason: str, actor: str) -> Result[BreakGlass]:
    policy = lhras.governance.break_glass
    if policy is None or not policy.allows(actor, reason):
        return error(BREAK_GLASS_DENIED, actor=actor, reason=reason)
    now = time.time()
    bg = BreakGlass(
        activated_at=now,
        actor=actor,
        reason=reason,
        expires_at=now + policy.duration_seconds,
    )
    attest = lhras.attester.self_attest({"event": "break_glass", "actor": actor, "reason": reason})
    written = aethel_store.aethel_write(
        lhras.aethel, aethel_store.break_glass_certificate(bg), attest
    )
    if written.is_err:
        return written
    alert_all(lhras.alerts, "BREAK GLASS ACTIVATED", {"actor": actor, "reason": reason})
    lhras.governance.audit_log.append("break_glass", actor, {"reason": reason})
    return Ok(bg)


def alert_all(alerts: list[Any], subject: str, body: Any) -> None:
    for channel in alerts:
        channel.send(subject, body)
