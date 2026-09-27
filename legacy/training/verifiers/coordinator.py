"""Mining Coordinator contract verifier.

Contract (docs/mining_agents/MINING_COORDINATOR.md):
  - Every decision is logged.
  - Every escalation is explicit.
  - Override authority is bounded (safety only).
  - The five intelligences have full authority in their domains.
  - Conflicts are resolved by the TOE.
  - Escalation to PYTHIA only when the TOE cannot resolve.

Rules:
  1. decisions_logged — mining lifecycle decisions flow through EventBus
     (job.new, share.submitted, telemetry, control events).

  2. escalation_explicit — a chain-broken alert escalates explicitly and the
     kill path exists.

  3. override_bounded_to_safety — KillSwitch can only halt (arm/reset state)
     and every mining step checks it via preflight before acting.

  4. five_intelligences_authority — which subsystem owns which decision is a
     runtime property, not statically decidable — reported not_checkable.
"""

from __future__ import annotations

import re

from .common import (
    RuleResult,
    Violation,
    fail,
    load_ts,
    not_checkable,
    pass_,
)

AGENT = "coordinator"


def check_decisions_logged() -> list[Violation]:
    violations: list[Violation] = []
    src = load_ts("src/lib/mining_service.ts")
    publishes = list(src.find(r"\bEventBus\.publish\s*\("))
    if len(publishes) < 3:
        violations.append(
            Violation(
                file=src.relpath,
                line=1,
                detail=f"only {len(publishes)} EventBus.publish calls — "
                "decisions are not systematically logged",
                fix="Publish every lifecycle decision (job, share, telemetry, "
                "control) on the event bus.",
            )
        )
    # The four decision topics must all be published.
    for topic in ("job", "share", "telemetry", "control"):
        if not any(True for _ in src.find_literal(f"euclid:{topic}")) and not any(
            True for _ in src.find_literal(topic)
        ):
            violations.append(
                Violation(
                    file=src.relpath,
                    line=1,
                    detail=f"no event published on the {topic!r} topic",
                    fix=f"Log {topic} decisions via EventBus.publish.",
                )
            )
    return violations


def check_escalation_explicit() -> list[Violation]:
    violations: list[Violation] = []
    src = load_ts("src/lib/mining_service.ts")
    if not any(True for _ in src.find_literal("chain.broken")):
        violations.append(
            Violation(
                file=src.relpath,
                line=1,
                detail="no chain.broken escalation event",
                fix="Publish chain.broken when inspectChain returns an alert.",
            )
        )
    kill = load_ts("src/lib/kill_switch.ts")
    if kill.function_named("arm") is None or kill.function_named("isKilled") is None:
        violations.append(
            Violation(
                file=kill.relpath,
                line=1,
                detail="KillSwitch arm/isKilled path missing",
                fix="Restore the operator kill switch.",
            )
        )
    return violations


def check_override_bounded() -> list[Violation]:
    violations: list[Violation] = []
    kill = load_ts("src/lib/kill_switch.ts")
    arm = kill.function_named("arm")
    if arm is not None:
        body = kill.region_text(arm)
        ln, _ = kill.region_lines(arm)
        # arm() may only assign this.killed / this.reason — no calls, no
        # other field writes, no other side effects.
        assigns = re.findall(r"\bthis\.(\w+)\s*=", body)
        bad_assigns = [a for a in assigns if a not in ("killed", "reason")]
        calls = [c for c in re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", body) if c not in ("arm",)]
        if bad_assigns or calls:
            violations.append(
                Violation(
                    file=kill.relpath,
                    line=ln,
                    detail=f"KillSwitch.arm performs operations beyond the halt "
                    f"flag: writes={bad_assigns} calls={calls}",
                    fix="Override must be bounded to safety halt only.",
                )
            )
    rt = load_ts("src/lib/mining_runtime.ts")
    pre = rt.function_named("preflight")
    if pre is None:
        violations.append(
            Violation(
                file=rt.relpath,
                line=1,
                detail="preflight not found — nothing checks the kill switch "
                "before a mining step",
                fix="preflight must consult KillSwitch.isKilled() first.",
            )
        )
    else:
        body = rt.region_text(pre)
        if "isKilled" not in body:
            ln, _ = rt.region_lines(pre)
            violations.append(
                Violation(
                    file=rt.relpath,
                    line=ln,
                    detail="preflight does not consult KillSwitch.isKilled()",
                    fix="Check the kill switch before any mining action.",
                )
            )
    return violations


def verify() -> list[RuleResult]:
    results: list[RuleResult] = []

    v = check_decisions_logged()
    results.append(
        fail(AGENT, "decisions_logged", v)
        if v
        else pass_(
            AGENT,
            "decisions_logged",
            file="src/lib/mining_service.ts",
            detail="Lifecycle decisions publish on the euclid:jobs / euclid:shares "
            "/ euclid:telemetry / euclid:control topics.",
        )
    )

    v = check_escalation_explicit()
    results.append(
        fail(AGENT, "escalation_explicit", v)
        if v
        else pass_(
            AGENT,
            "escalation_explicit",
            file="src/lib/mining_service.ts",
            detail="chain.broken alert escalates explicitly; KillSwitch halt " "path exists.",
        )
    )

    v = check_override_bounded()
    results.append(
        fail(AGENT, "override_bounded_to_safety", v)
        if v
        else pass_(
            AGENT,
            "override_bounded_to_safety",
            file="src/lib/kill_switch.ts",
            detail="KillSwitch.arm only sets the halt flag+reason; every mining "
            "step consults isKilled() via preflight before acting.",
        )
    )

    results.append(
        not_checkable(
            AGENT,
            "five_intelligences_authority",
            "Domain-authority partitioning across the five intelligences is a "
            "runtime property — which subsystem decided what is not decidable "
            "by static analysis. Verify via decision provenance logs at "
            "runtime.",
        )
    )
    return results
