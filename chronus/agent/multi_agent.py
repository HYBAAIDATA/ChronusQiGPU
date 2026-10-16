"""Scoped delegation packets; no inherited permission or implicit remote spawning."""

from dataclasses import dataclass
from ._contracts import ContractError, integer, text
from .permissions import ActionKind


@dataclass(frozen=True)
class DelegationPacket:
    child_id: str
    task_key: str
    permission_ids: tuple[str, ...]
    budget: int
    deadline_ns: int
    termination_condition: str

    def __post_init__(self):
        text(self.child_id)
        text(self.task_key)
        text(self.termination_condition)
        integer(self.budget)
        integer(self.deadline_ns)
        if type(self.permission_ids) is not tuple:
            raise ContractError("explicit scoped child grants required")


def delegate(packet, request, permissions, *, level, now, dispatcher):
    if (
        request.action is not ActionKind.DELEGATE
        or request.task_key != packet.task_key
        or not packet.permission_ids
        or now >= packet.deadline_ns
        or not permissions.permitted(request, level=level, now=now, consume=True)
    ):
        raise ContractError("delegation not authorized or bounded")
    return dispatcher(packet)


def resolve_disagreement(results):
    if not results:
        raise ContractError("no results")
    conclusions = {r[0] for r in results}
    if len(conclusions) != 1:
        raise ContractError(
            "material disagreement requires escalation; confidence cannot erase conflict"
        )
    return max(results, key=lambda r: r[1])
