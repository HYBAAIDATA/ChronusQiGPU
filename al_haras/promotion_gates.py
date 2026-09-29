"""Evidence-gated subsystem promotion with explicit claim boundaries."""

from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable, Mapping


class PromotionState(IntEnum):
    RESEARCH = 0
    CONTRACTED = 1
    REFERENCE = 2
    VERIFIED = 3
    PILOT = 4
    PRODUCTION = 5


@dataclass(frozen=True)
class GateDefinition:
    subsystem: str
    requirements: Mapping[PromotionState, tuple[str, ...]]
    promoted_claims: Mapping[PromotionState, tuple[str, ...]]
    refuted_claims: Mapping[PromotionState, tuple[str, ...]]


@dataclass(frozen=True)
class GateResult:
    subsystem: str
    target: PromotionState
    achieved: PromotionState
    passed: bool
    missing: tuple[str, ...]
    promoted_claims: tuple[str, ...]
    refuted_claims: tuple[str, ...]
    rollback_evidence: tuple[str, ...]


class PromotionBlocked(RuntimeError):
    pass


def _req(prefix: str, contracted: str, reference: str, verified: str, pilot: str, production: str):
    def ids(stage, text):
        return tuple(f"{prefix}_{stage}_{item.strip()}" for item in text.split())

    return {
        PromotionState.CONTRACTED: ids("CONTRACT" if prefix == "G" else "CON", contracted),
        PromotionState.REFERENCE: ids("REF", reference),
        PromotionState.VERIFIED: ids("VER", verified),
        PromotionState.PILOT: ids("PILOT", pilot),
        PromotionState.PRODUCTION: ids("PROD", production),
    }


DEFINITIONS = {
    "guardian": GateDefinition(
        "guardian",
        _req("G", "1 2 3 4", "1 2 3 4 5 6", "1 2 3 4 5 6 7 8", "1 2 3 4", "1 2 3 4"),
        {
            PromotionState.VERIFIED: ("full Guardian conjunction", "signed verdicts"),
            PromotionState.PILOT: ("container-wide mediation",),
            PromotionState.PRODUCTION: ("production Guardian boundary",),
        },
        {
            PromotionState.REFERENCE: ("Guardian is production-ready",),
            PromotionState.VERIFIED: ("Guardian is independently witnessed",),
            PromotionState.PILOT: ("Guardian claims universal security",),
        },
    ),
    "folded": GateDefinition(
        "folded",
        _req("F", "1 2 3 4 5", "1 2 3 4 5", "1 2 3 4 5 6 7", "1 2 3 4", "1 2 3 4"),
        {
            PromotionState.VERIFIED: ("folded execution matches exact reference",),
            PromotionState.PILOT: ("folded path reduces bytes moved on workload X",),
            PromotionState.PRODUCTION: ("folded path is production default for family Y",),
        },
        {
            PromotionState.REFERENCE: ("PULVINI is compression",),
            PromotionState.VERIFIED: ("folded execution is universal",),
            PromotionState.PILOT: ("folded path is faster for arbitrary data",),
        },
    ),
    "pisot": GateDefinition(
        "pisot",
        _req("P", "1 2 3 4 5", "1 2 3 4 5", "1 2 3 4 5 6", "1 2 3 4", "1 2 3 4"),
        {
            PromotionState.VERIFIED: ("exact trace-preserving truncation for family X",),
            PromotionState.PILOT: ("residual-bounded operator composition",),
        },
        {
            PromotionState.REFERENCE: ("Pisot truncation is compression",),
            PromotionState.VERIFIED: ("sub-exponential scaling proven",),
            PromotionState.PILOT: ("truncation is lossless",),
        },
    ),
    "identity": GateDefinition(
        "identity",
        _req("I", "1 2 3 4 5 6", "1 2 3 4 5 6 7", "1 2 3 4 5 6 7 8 9", "1 2 3 4", "1 2 3 4"),
        {
            PromotionState.VERIFIED: ("authenticated principal derivation",),
            PromotionState.PILOT: ("hardware-backed key custody",),
            PromotionState.PRODUCTION: ("sovereign identity boundary",),
        },
        {
            PromotionState.REFERENCE: ("entitlement is sovereign",),
            PromotionState.VERIFIED: ("shared-secret entitlement is production identity",),
            PromotionState.PILOT: ("identity is externally assured",),
        },
    ),
    "witness": GateDefinition(
        "witness",
        _req("W", "1 2 3 4 5", "1 2 3 4", "1 2 3 4 5 6 7", "1 2 3 4", "1 2 3 4"),
        {
            PromotionState.VERIFIED: ("tamper detected by witness",),
            PromotionState.PILOT: ("externally anchored ledger",),
            PromotionState.PRODUCTION: ("independently trustworthy audit history",),
        },
        {
            PromotionState.REFERENCE: ("chain is independently trustworthy",),
            PromotionState.VERIFIED: ("chain proves history to external evaluator",),
            PromotionState.PILOT: ("witness is a substitute for WORM",),
        },
    ),
    "schema": GateDefinition(
        "schema",
        _req("S", "1 2 3 4 5 6", "1 2 3 4 5", "1 2 3 4 5 6", "1 2 3", "1 2 3"),
        {
            PromotionState.VERIFIED: ("canonical 11-axis object",),
            PromotionState.PILOT: ("cross-backend identity preservation",),
            PromotionState.PRODUCTION: ("frozen production schema",),
        },
        {
            PromotionState.REFERENCE: ("schema is stable",),
            PromotionState.VERIFIED: ("12D gauge is part of the object",),
            PromotionState.PILOT: ("reserved fields carry semantics",),
        },
    ),
    "mediation": GateDefinition(
        "mediation",
        _req("C", "1 2 3 4", "1 2 3 4", "1 2 3 4 5 6", "1 2 3", "1 2 3"),
        {
            PromotionState.VERIFIED: ("container-wide privileged mediation",),
            PromotionState.PILOT: ("Guardian veto effective in live traffic",),
            PromotionState.PRODUCTION: ("no privileged transition escapes Guardian",),
        },
        {
            PromotionState.REFERENCE: ("AL HARAS mediates the container",),
            PromotionState.VERIFIED: ("all endpoints are mediated",),
            PromotionState.PILOT: ("mediation is complete without degraded policy",),
        },
    ),
}


def evaluate_gate(
    subsystem: str,
    target: PromotionState,
    evidence: Mapping[str, object],
    *,
    rollback_evidence: Iterable[str] = (),
) -> GateResult:
    definition = DEFINITIONS[subsystem]
    rollback = tuple(rollback_evidence)
    achieved = PromotionState.RESEARCH
    missing_at_target = []
    for state in PromotionState:
        if state is PromotionState.RESEARCH or state > target:
            continue
        required = tuple(
            req for stage, reqs in definition.requirements.items() if stage <= state for req in reqs
        )
        missing = [req for req in required if not evidence.get(req)]
        if state >= PromotionState.PILOT and not rollback:
            missing.append(f"{subsystem.upper()}_ROLLBACK_EVIDENCE")
        if missing:
            if state == target:
                missing_at_target = missing
            break
        achieved = state
    if achieved < target and not missing_at_target:
        required = tuple(
            req
            for stage, reqs in definition.requirements.items()
            if stage <= target
            for req in reqs
        )
        missing_at_target = [req for req in required if not evidence.get(req)]
        if target >= PromotionState.PILOT and not rollback:
            missing_at_target.append(f"{subsystem.upper()}_ROLLBACK_EVIDENCE")
    promoted = tuple(
        claim
        for state, claims in definition.promoted_claims.items()
        if state <= achieved
        for claim in claims
    )
    refuted = tuple(
        claim
        for state, claims in definition.refuted_claims.items()
        if state <= target
        for claim in claims
    )
    return GateResult(
        subsystem,
        target,
        achieved,
        achieved >= target,
        tuple(missing_at_target),
        promoted,
        refuted,
        rollback,
    )


def require_gate(*args, **kwargs) -> GateResult:
    result = evaluate_gate(*args, **kwargs)
    if not result.passed:
        raise PromotionBlocked(f"{result.subsystem} blocked: {', '.join(result.missing)}")
    return result
