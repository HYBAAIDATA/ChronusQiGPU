"""Capability contracts bind real host adapters; registration is not competence."""

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol
from ._contracts import ContractError, digest, integer, text


class RiskTier(IntEnum):
    T0_SANDBOX = 0
    T1_INTERNAL_REVERSIBLE = 1
    T2_INTERNAL_CONSEQUENTIAL = 2
    T3_EXTERNAL_REVERSIBLE = 3
    T4_EXTERNAL_CONSEQUENTIAL = 4
    T5_IRREVERSIBLE_OR_SAFETY_CRITICAL = 5


@dataclass(frozen=True)
class TaskClass:
    domain: str
    workflow: str
    environment: str
    horizon_ns: int
    risk_tier: RiskTier
    reversibility: str
    data_sensitivity: str
    external_effects: bool
    jurisdiction: str

    def __post_init__(self):
        for value in (
            self.domain,
            self.workflow,
            self.environment,
            self.reversibility,
            self.data_sensitivity,
            self.jurisdiction,
        ):
            text(value)
        integer(self.horizon_ns, minimum=1)
        if type(self.risk_tier) is not RiskTier or type(self.external_effects) is not bool:
            raise ContractError("typed risk and external-effects flag required")

    @property
    def key(self):
        return digest(self)


@dataclass(frozen=True)
class Capability:
    name: str
    input_contract: str
    output_contract: str
    evaluation_suite: str
    failure_modes: tuple[str, ...]
    required_evidence: tuple[str, ...]

    def __post_init__(self):
        for value in (self.name, self.input_contract, self.output_contract, self.evaluation_suite):
            text(value)
        for values in (self.failure_modes, self.required_evidence):
            if type(values) is not tuple or not values:
                raise ContractError("explicit failures/evidence required")


class ActionAdapter(Protocol):
    """Host owns isolation, deadline enforcement, cancellation and authorization.

    observe must be independent of execute's claimed return status. rollback
    must restore a checkpoint without acquiring new task authority.
    """

    def checkpoint(self): ...
    def execute(self, request, *, deadline_ns: int): ...
    def observe(self): ...
    def rollback(self, checkpoint): ...


class CapabilitySet:
    def __init__(self):
        self._entries = {}
        self._task_bindings = {}

    def register(self, contract: Capability, adapter: ActionAdapter, *, task_key=None):
        if not isinstance(contract, Capability) or contract.name in self._entries:
            raise ContractError("duplicate or invalid capability")
        if not all(
            callable(getattr(adapter, name, None))
            for name in ("checkpoint", "execute", "observe", "rollback")
        ):
            raise ContractError("complete host adapter required")
        self._entries[contract.name] = (contract, adapter)
        self._task_bindings[contract.name] = task_key

    def get(self, name, *, task_key=None):
        if name not in self._entries:
            raise ContractError("capability unavailable; no implicit fallback")
        if self._task_bindings[name] is not None and self._task_bindings[name] != task_key:
            raise ContractError("capability not qualified for this task scope")
        return self._entries[name]

    def manifest(self):
        return tuple(
            {"contract": c, "adapter_registered": True, "demonstrated_reliability": None}
            for c, _ in self._entries.values()
        )

    def unregister(self, name):
        if name not in self._entries:
            raise ContractError("unknown capability")
        del self._entries[name]
        self._task_bindings.pop(name, None)
