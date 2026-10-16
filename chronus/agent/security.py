"""Origin isolation: untrusted data never becomes a command or grant.

Text threat markers are diagnostic only, not a claimed universal injection
classifier. Effective enforcement is typed origin, host registration and exact
permissions, not a regex safety verdict.
"""

from dataclasses import dataclass
from ._contracts import ContractError, sha, text


@dataclass(frozen=True)
class InputEnvelope:
    content: str
    origin: str
    evidence_digest: str
    command_requested: bool = False

    def __post_init__(self):
        text(self.content)
        sha(self.evidence_digest)
        if (
            self.origin not in ("host", "tool", "web", "file", "third_party")
            or type(self.command_requested) is not bool
        ):
            raise ContractError("typed origin/command flag required")


def resist_manipulation(envelope, ledger, *, now):
    if not isinstance(envelope, InputEnvelope):
        raise ContractError("input origin is required")
    if envelope.command_requested and envelope.origin != "host":
        ledger.append(
            "refusal_issued",
            {"reason": "untrusted_command_origin", "evidence": envelope.evidence_digest},
            now=now,
        )
        raise ContractError("untrusted content cannot issue commands")
    return envelope
