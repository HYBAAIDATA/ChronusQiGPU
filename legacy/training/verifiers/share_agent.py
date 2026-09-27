"""Share Agent contract verifier.

Contract (docs/mining_agents/SHARE_AGENT.md):
  - Every share is double-SHA256-verified before submission.
  - SHA-256d is the sole accept authority.
  - Submission happens within the network's expected window.
  - Every rejection is logged and analyzed.
  - No share bypasses the SHA-256d check.

Statically checkable rules:

  1. no_target_comparison_outside_authority
     Any expression comparing a hash-shaped value to a target-shaped value
     (``hash <= target`` etc.) must live inside a function named
     ``meetsTarget`` — the declared accept authorities
     (``MiningService.meetsTarget``, ``StratumV1ProtocolEngine.meetsTarget``).
     Exception: ``dense_reward.ts`` computes ``meetsTarget`` as a *telemetry*
     field only; rule 4 verifies it is never consumed on the accept path.

  2. submit_gated_by_sha256d_pass_and_approval
     Every ``submitShare(...)`` call site in the mining service must be
     dominated by the ``if (bestPassing)`` block (only set when
     ``check.passes``), and the stratum client must gate on
     ``isLiveSubmitApproved`` before issuing ``mining.submit``.

  3. shares_created_only_after_pass
     ``insertShare`` / share creation must be dominated by the passing check.

  4. dense_reward_not_accept_path
     The dense-reward ``meetsTarget`` field must never be consumed as an
     accept decision outside ``dense_reward.ts`` itself.

  5. share_zeckendorf_certificate
     Every recorded share should carry a Zeckendorf certificate. Not present
     in the schema today — reported honestly as not_implemented.
"""

from __future__ import annotations

import re

from .common import (
    RuleResult,
    TsSource,
    Violation,
    fail,
    glob_ts,
    load_ts,
    not_implemented,
    pass_,
)

AGENT = "share_agent"

# Operands that look like a hash value and a target value.
_HASH_OPERAND = r"(?:hashBigInt|hashVal|hash|headerHash|digest)"
_TARGET_OPERAND = r"(?:target|targetBigInt|poolShareTarget|shareTarget|MAX_TARGET|diff\w*)"
_HASH_VS_TARGET = re.compile(
    rf"\b{_HASH_OPERAND}\w*\s*(?:<=?|>=?)\s*\w*{_TARGET_OPERAND}\w*\b"
    rf"|\b{_TARGET_OPERAND}\w*\s*(?:<=?|>=?)\s*\w*{_HASH_OPERAND}\w*\b"
)

# Comparisons allowed only inside the two declared authorities (any function
# named meetsTarget) or the documented non-authoritative readouts below —
# dense_reward.ts (telemetry field, never consumed for acceptance — rule 4)
# and BitcoinBlockHeaderBuilder.evaluateHeader (diagnostic breakdown struct).
_AUTHORITY_FN = "meetsTarget"
_READOUT_EXCEPTIONS = {
    "src/lib/dense_reward.ts": None,  # whole file is telemetry
    "src/lib/bitcoin_header.ts": {"evaluateHeader"},  # breakdown diagnostic
}
_PRODUCTION_SCOPE = "src/lib"


def check_no_target_comparison_outside_authority(
    sources: list[TsSource],
) -> list[Violation]:
    """Every hash<=target comparison must be inside a meetsTarget function
    or the documented dense_reward telemetry exception."""
    violations: list[Violation] = []
    for src in sources:
        if src.relpath.endswith(".test.ts"):
            continue
        for line_no, line_text, m in src.find(_HASH_VS_TARGET):
            fn = src.enclosing_function(m.start())
            if fn is not None and fn.name == _AUTHORITY_FN:
                continue
            if src.relpath in _READOUT_EXCEPTIONS:
                allowed_fns = _READOUT_EXCEPTIONS[src.relpath]
                if allowed_fns is None or (fn is not None and fn.name in allowed_fns):
                    continue
            violations.append(
                Violation(
                    file=src.relpath,
                    line=line_no,
                    detail=f"hash-vs-target comparison outside a meetsTarget authority: {line_text.strip()[:120]}",
                    fix="Move the comparison inside MiningService.meetsTarget / "
                    "StratumV1ProtocolEngine.meetsTarget, or consume check.passes.",
                )
            )
    return violations


def check_submit_gated(src_service: TsSource, src_client: TsSource) -> list[Violation]:
    violations: list[Violation] = []

    # mining_service: every submitShare( call must be inside `if (bestPassing)`
    # and the same region must call isLiveSubmitApproved().
    passing_block = src_service.if_block(r"\bbestPassing\b")
    if passing_block is None:
        violations.append(
            Violation(
                file=src_service.relpath,
                line=1,
                detail="no `if (bestPassing)` block found — share submit is not dominated by the SHA-256d pass check",
                fix="Gate submitShare inside the bestPassing block.",
            )
        )
    else:
        region = src_service.region_text(passing_block)
        if "isLiveSubmitApproved" not in region:
            ln, _ = src_service.region_lines(passing_block)
            violations.append(
                Violation(
                    file=src_service.relpath,
                    line=ln,
                    detail="bestPassing block does not gate on isLiveSubmitApproved()",
                    fix="Require isLiveSubmitApproved() && client.connected before submitShare.",
                )
            )
        for line_no, line_text, m in src_service.find(r"\bsubmitShare\s*\("):
            if not (passing_block.body_start < m.start() < passing_block.body_end):
                violations.append(
                    Violation(
                        file=src_service.relpath,
                        line=line_no,
                        detail="submitShare call is not dominated by `if (bestPassing)`",
                        fix="Move submitShare inside the bestPassing block so only "
                        "SHA-256d-passing candidates are submitted.",
                    )
                )

    # stratum_tcp_client: submitShare must consult isLiveSubmitApproved before
    # the first mining.submit.
    sub_fn = src_client.function_named("submitShare")
    if sub_fn is None:
        violations.append(
            Violation(
                file=src_client.relpath,
                line=1,
                detail="StratumTcpClient.submitShare not found",
                fix="Restore the gated submitShare method.",
            )
        )
    else:
        body = src_client.region_text(sub_fn)
        ln, _ = src_client.region_lines(sub_fn)
        gate_off = body.find("isLiveSubmitApproved")
        if gate_off == -1:
            violations.append(
                Violation(
                    file=src_client.relpath,
                    line=ln,
                    detail="submitShare does not gate on isLiveSubmitApproved before mining.submit",
                    fix="Return gated:true unless isLiveSubmitApproved(env).",
                )
            )
        else:
            # The gate must precede the mining.submit RPC literal. String
            # contents are stripped from `code`, so locate the literal via
            # the literals table (offsets are absolute).
            submit_lit = next(
                (
                    off
                    for off, content in src_client.literals
                    if sub_fn.body_start < off < sub_fn.body_end and content == "mining.submit"
                ),
                None,
            )
            if submit_lit is None:
                violations.append(
                    Violation(
                        file=src_client.relpath,
                        line=ln,
                        detail="submitShare never issues a mining.submit RPC",
                        fix="Issue mining.submit after the approval gate.",
                    )
                )
            elif sub_fn.body_start + gate_off > submit_lit:
                violations.append(
                    Violation(
                        file=src_client.relpath,
                        line=ln,
                        detail="mining.submit is issued before the " "isLiveSubmitApproved gate",
                        fix="Evaluate the gate before any mining.submit RPC.",
                    )
                )
    return violations


def check_shares_created_only_after_pass(src_service: TsSource) -> list[Violation]:
    """insertShare / markShareResolved must be dominated by the pass check."""
    violations: list[Violation] = []
    passing_block = src_service.if_block(r"\bbestPassing\b")
    for line_no, line_text, m in src_service.find(r"\binsertShare\s*\("):
        if passing_block is None or not (
            passing_block.body_start < m.start() < passing_block.body_end
        ):
            violations.append(
                Violation(
                    file=src_service.relpath,
                    line=line_no,
                    detail="insertShare is called outside the SHA-256d-passing block",
                    fix="Only create share records for candidates where check.passes.",
                )
            )
    # bestPassing must be assigned only inside a `check.passes`-dominated region
    passes_block = src_service.if_block(r"\bcheck\.passes\b")
    for line_no, line_text, m in src_service.find(r"\bbestPassing\s*="):
        if passes_block is None or not (
            passes_block.body_start < m.start() < passes_block.body_end
        ):
            violations.append(
                Violation(
                    file=src_service.relpath,
                    line=line_no,
                    detail="bestPassing assigned outside `if (check.passes)`",
                    fix="bestPassing may only be set when meetsTarget reports passes.",
                )
            )
    return violations


def check_dense_reward_not_accept_path(sources: list[TsSource]) -> list[Violation]:
    """`.meetsTarget` property reads outside dense_reward.ts would mean the
    telemetry field is being consumed as an accept decision. Receivers
    `this.` (MiningService method) and `StratumV1ProtocolEngine.` (the second
    declared authority) are the authorized call sites."""
    violations: list[Violation] = []
    allowed_receiver = re.compile(r"(?:this|StratumV1ProtocolEngine|MiningService)\.meetsTarget")
    for src in sources:
        if src.relpath.endswith(".test.ts") or src.relpath in _READOUT_EXCEPTIONS:
            continue
        for line_no, line_text, m in src.find(r"\.meetsTarget\b"):
            stmt = line_text.strip()
            if allowed_receiver.search(src.code[m.start() - 40 : m.end()]):
                continue
            # a bare `.meetsTarget` read on a dense-reward result object
            violations.append(
                Violation(
                    file=src.relpath,
                    line=line_no,
                    detail=f"`.meetsTarget` consumed outside the accept authorities: {stmt[:120]}",
                    fix="Acceptance must come from meetsTarget()'s `passes`, never the "
                    "dense-reward telemetry field.",
                )
            )
    return violations


def check_share_zeckendorf_certificate(src_repo: TsSource, src_service: TsSource) -> RuleResult:
    """Every recorded share should carry a Zeckendorf certificate field."""
    has_field = bool(
        re.search(r"zeckendorf", src_repo.code, re.IGNORECASE)
        and re.search(r"zeckendorf", src_service.code, re.IGNORECASE)
    )
    if has_field:
        return pass_(
            AGENT,
            "share_zeckendorf_certificate",
            file="src/lib/repositories.ts",
            detail="Share record carries a Zeckendorf certificate field.",
        )
    return not_implemented(
        AGENT,
        "share_zeckendorf_certificate",
        detail="Share schema (repositories.ts Share interface / insertShare) has no "
        "Zeckendorf certificate field — shares are recorded with nonce, hash, "
        "amplitude only.",
        fix="Add `zeckendorf_certificate` to the Share schema and populate it via "
        "ExactSequenceMath.zeckendorf(nonce) at insertShare time.",
    )


def verify() -> list[RuleResult]:
    results: list[RuleResult] = []

    sources = glob_ts(_PRODUCTION_SCOPE)
    service = load_ts("src/lib/mining_service.ts")
    client = load_ts("src/lib/stratum_tcp_client.ts")
    repo = load_ts("src/lib/repositories.ts")

    # Rule 1
    v = check_no_target_comparison_outside_authority(sources)
    results.append(
        fail(
            AGENT,
            "no_target_comparison_outside_authority",
            v,
            detail="hash-vs-target comparisons found outside meetsTarget authorities",
            fix="Route all accept decisions through meetsTarget(); dense_reward "
            "comparison is telemetry-only.",
        )
        if v
        else pass_(
            AGENT,
            "no_target_comparison_outside_authority",
            detail="All hash-vs-target comparisons live inside meetsTarget "
            "authorities or the documented dense_reward telemetry exception.",
        )
    )

    # Rule 2
    v = check_submit_gated(service, client)
    results.append(
        fail(AGENT, "submit_gated_by_sha256d_pass_and_approval", v)
        if v
        else pass_(
            AGENT,
            "submit_gated_by_sha256d_pass_and_approval",
            file="src/lib/mining_service.ts",
            detail="submitShare is dominated by if (bestPassing) and gated by "
            "isLiveSubmitApproved in both the service and the stratum client.",
        )
    )

    # Rule 3
    v = check_shares_created_only_after_pass(service)
    results.append(
        fail(AGENT, "shares_created_only_after_pass", v)
        if v
        else pass_(
            AGENT,
            "shares_created_only_after_pass",
            file="src/lib/mining_service.ts",
            detail="insertShare and bestPassing assignment are dominated by the "
            "SHA-256d pass check.",
        )
    )

    # Rule 4
    v = check_dense_reward_not_accept_path(sources)
    results.append(
        fail(AGENT, "dense_reward_not_accept_path", v)
        if v
        else pass_(
            AGENT,
            "dense_reward_not_accept_path",
            detail="No consumer reads the dense-reward meetsTarget field as an " "accept decision.",
        )
    )

    # Rule 5
    results.append(check_share_zeckendorf_certificate(repo, service))
    return results
