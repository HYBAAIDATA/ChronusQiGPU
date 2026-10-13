"""SDK client for EUCLID/PYTHIA MCP sessions.

Skeleton: enforces lifecycle, mandatory skills, evidence packs.
Fill transport and Notion connector in later phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import json
import hashlib
import time


@dataclass
class Session:
    session_id: str
    started_at: float = field(default_factory=time.time)
    skills_invoked: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    theorem_proven: bool = False


class EuclidMCPClient:
    def __init__(self, config_path: Optional[str] = None):
        self.config = {}
        if config_path:
            with open(config_path) as f:
                self.config = json.load(f)
        self.session: Optional[Session] = None

    def start_session(self) -> Session:
        sid = hashlib.sha256(f"{time.time()}".encode()).hexdigest()[:16]
        self.session = Session(session_id=sid)
        # Mandatory: load EUCLID aptitude / skills
        self.session.skills_invoked.append("euclid-cognition-aptitude")
        return self.session

    def invoke_skill(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if not self.session:
            raise RuntimeError("No active session")
        self.session.skills_invoked.append(name)
        # Stub: actual skill execution via MCP tool call in later phase
        return {"skill": name, "status": "stub", "theorem_proven": False}

    def produce_pack(self) -> dict[str, Any]:
        if not self.session:
            raise RuntimeError("No active session")
        pack = {
            "session_id": self.session.session_id,
            "skills": self.session.skills_invoked,
            "evidence_count": len(self.session.evidence),
            "theorem_proven": False,
            "timestamp": time.time(),
        }
        digest = hashlib.sha256(json.dumps(pack, sort_keys=True).encode()).hexdigest()
        pack["digest"] = digest
        return pack

    def require_owner_approval(self) -> bool:
        # Stub: always False until explicit owner signoff recorded
        return False

    def end_session(self) -> dict[str, Any]:
        pack = self.produce_pack()
        self.session = None
        return pack
