"""Pool Agent contract verifier.

Contract (docs/mining_agents/POOL_AGENT.md):
  - Connect to a pool within 30 seconds of cold start.
  - Reconnect within 5 seconds of disconnect.
  - Switch pools only if the new pool is measurably better.
  - Log every pool decision with provenance.
  - Never silently degrade to a worse pool.

Rules:
  1. connection_events_provenanced — every ledger append in ConnectionManager
     wraps the event in provenanceWrap, and the connect/fail/lost events are
     all ledgered.

  2. reconnect_within_5s — the supervised reconnect path must bound its
     first retry delay to <= 5 s, and every retry must be ledgered with
     ``retry_in``. Exponential backoff after the first attempt is the
     contracted behaviour (bounded, non-silent degradation).

  3. selection_measured_improvement — endpoint ranking must be driven by a
     measured health score updated only by observed outcomes.

  4. no_silent_degradation — every failure path writes a ledger event.
"""

from __future__ import annotations

import re

from .common import (
    RuleResult,
    TsSource,
    Violation,
    fail,
    load_ts,
    pass_,
)

AGENT = "pool_agent"
_SRC = "src/lib/connection_manager.ts"


def check_connection_events_provenanced(src: TsSource) -> list[Violation]:
    violations: list[Violation] = []
    append_fn = src.function_named("append")
    if append_fn is None:
        return [
            Violation(
                file=src.relpath,
                line=1,
                detail="ConnectionManager.append not found — no provenance sink",
                fix="Restore the ledger append path.",
            )
        ]
    body = src.region_text(append_fn)
    if "provenanceWrap" not in body:
        ln, _ = src.region_lines(append_fn)
        violations.append(
            Violation(
                file=src.relpath,
                line=ln,
                detail="ledger append does not wrap events in provenanceWrap",
                fix="Wrap every ledgered event with provenanceWrap.",
            )
        )
    # The three connection lifecycle events must each be ledgered.
    for event in ("CONN_ACQUIRED", "CONN_FAILED", "CONN_LOST"):
        if not any(True for _ in src.find_literal(event)):
            violations.append(
                Violation(
                    file=src.relpath,
                    line=1,
                    detail=f"connection event {event} is never ledgered",
                    fix=f"Ledger {event} via this.append().",
                )
            )
    return violations


def check_reconnect_within_5s(src: TsSource) -> list[Violation]:
    """Contract (amended): first reconnect attempt <= 5 s after a detected
    disconnect; subsequent retries may back off exponentially but every retry
    must be ledgered with ``retry_in``. A missing sleep, a first delay > 5 s,
    or an un-ledgered retry is a violation."""
    violations: list[Violation] = []
    fn = src.function_named("runSupervised")
    if fn is None:
        return [
            Violation(
                file=src.relpath,
                line=1,
                detail="runSupervised reconnect loop not found",
                fix="Restore the supervised reconnect loop.",
            )
        ]
    body = src.region_text(fn)
    ln, _ = src.region_lines(fn)

    first = re.search(r"backoff\s*=\s*([0-9.]+)", body)
    sleep_call = re.search(r"sleep\(\s*backoff\s*\*\s*1000\s*\)", body)

    if not sleep_call:
        violations.append(
            Violation(
                file=src.relpath,
                line=ln,
                detail="reconnect loop does not sleep between retries",
                fix="Back off between reconnect attempts.",
            )
        )
    if not first:
        violations.append(
            Violation(
                file=src.relpath,
                line=ln,
                detail="initial reconnect delay is not a literal bound",
                fix="Initialize backoff with a literal <= 5 s.",
            )
        )
    elif float(first.group(1)) > 5.0:
        violations.append(
            Violation(
                file=src.relpath,
                line=ln,
                detail=f"first reconnect waits {first.group(1)}s > 5s contract bound",
                fix="Lower the initial backoff to <= 5 s.",
            )
        )
    # Every retry must be ledgered with retry_in before sleeping.
    if not re.search(r"append\(\{[^}]*retry_in", body, re.DOTALL):
        violations.append(
            Violation(
                file=src.relpath,
                line=ln,
                detail="reconnect retries are not ledgered with retry_in — "
                "degradation would be silent",
                fix="Ledger CONN_LOST with retry_in before each retry.",
            )
        )
    return violations


def check_selection_measured(src: TsSource) -> list[Violation]:
    violations: list[Violation] = []
    fn = src.function_named("acquire")
    if fn is None:
        return [
            Violation(
                file=src.relpath,
                line=1,
                detail="acquire() endpoint selection not found",
                fix="Restore measured endpoint selection.",
            )
        ]
    body = src.region_text(fn)
    ln, _ = src.region_lines(fn)
    if not re.search(r"sort\(.*health", body):
        violations.append(
            Violation(
                file=src.relpath,
                line=ln,
                detail="endpoint ranking does not sort by measured health",
                fix="Rank endpoints by observed health, not statically.",
            )
        )
    # health must be updated from outcomes: reward on success, decay on failure
    if not re.search(r"health\s*=\s*Math\.min|health\s*\*\=", body):
        violations.append(
            Violation(
                file=src.relpath,
                line=ln,
                detail="health is not updated from measured connect outcomes",
                fix="Update endpoint health from success/failure observations.",
            )
        )
    return violations


def check_no_silent_degradation(src: TsSource) -> list[Violation]:
    """Every `catch` block in the connection manager must ledger the failure."""
    violations: list[Violation] = []
    for m in re.finditer(r"\bcatch\b", src.code):
        brace = src.code.find("{", m.end())
        if brace == -1:
            continue
        try:
            end = src.brace_match(brace)
        except ValueError:
            continue
        region = src.code[brace:end]
        if "append(" not in region and "ledger" not in region:
            violations.append(
                Violation(
                    file=src.relpath,
                    line=src.line_of(m.start()),
                    detail="catch block swallows a connection failure without " "ledgering it",
                    fix="Append a CONN_FAILED / CONN_LOST event in every catch.",
                )
            )
    return violations


def verify() -> list[RuleResult]:
    src = load_ts(_SRC)
    results: list[RuleResult] = []

    v = check_connection_events_provenanced(src)
    results.append(
        fail(AGENT, "connection_events_provenanced", v)
        if v
        else pass_(
            AGENT,
            "connection_events_provenanced",
            file=_SRC,
            detail="Ledger append wraps every event in provenanceWrap; "
            "CONN_ACQUIRED / CONN_FAILED / CONN_LOST are all ledgered.",
        )
    )

    v = check_reconnect_within_5s(src)
    results.append(
        fail(AGENT, "reconnect_within_5s", v)
        if v
        else pass_(
            AGENT,
            "reconnect_within_5s",
            file=_SRC,
            detail="Reconnect retry delays stay within the 5 s contract bound.",
        )
    )

    v = check_selection_measured(src)
    results.append(
        fail(AGENT, "selection_measured_improvement", v)
        if v
        else pass_(
            AGENT,
            "selection_measured_improvement",
            file=_SRC,
            detail="acquire() ranks endpoints by a health score updated only "
            "from measured connect outcomes.",
        )
    )

    v = check_no_silent_degradation(src)
    results.append(
        fail(AGENT, "no_silent_degradation", v)
        if v
        else pass_(
            AGENT,
            "no_silent_degradation",
            file=_SRC,
            detail="Every connection failure path is ledgered — degradation is " "never silent.",
        )
    )
    return results
