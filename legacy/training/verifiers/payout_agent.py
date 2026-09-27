"""Payout Agent contract verifier.

Contract (docs/mining_agents/PAYOUT_AGENT.md):
  - Balance is verified via Cassini invariants.
  - Withdrawals are logged with provenance.
  - Withdrawal threshold is respected.
  - Multi-address management (cold, hot, operational).
  - No unverified withdrawals.

Current codebase state: there is NO payout/withdrawal implementation in
src/lib, mining/, or Intelligence/. Every rule is therefore reported as
not_implemented — honestly, rather than passing on absent code.
"""

from __future__ import annotations

import re

from .common import (
    REPO_ROOT,
    RuleResult,
    not_implemented,
)

AGENT = "payout_agent"

_SCAN_DIRS = ("src/lib", "mining", "Intelligence")

_PAYOUT_RE = re.compile(r"\b(withdraw\w*|payout\w*|cold_wallet|hot_wallet)\b")


def _payout_code_exists() -> tuple[bool, str]:
    """Locate any payout/withdrawal implementation across the repo."""
    hits = []
    for d in _SCAN_DIRS:
        base = REPO_ROOT / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.ts")) + sorted(base.rglob("*.py")):
            if ".test." in p.name or p.name.startswith("test_"):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if _PAYOUT_RE.search(text):
                hits.append(str(p.relative_to(REPO_ROOT)))
    return (len(hits) > 0, ", ".join(hits[:5]))


def verify() -> list[RuleResult]:
    exists, where = _payout_code_exists()
    rules = [
        (
            "balance_cassini_verified",
            "No balance-Cassini verification path exists.",
            "Add balance verification via CassiniVerifier / ExactSequenceMath.cassini.",
        ),
        (
            "withdrawals_logged",
            "No withdrawal path exists to log.",
            "Add a withdrawal function that provenance-wraps every payout.",
        ),
        (
            "withdrawal_threshold_respected",
            "No withdrawal threshold check exists.",
            "Add a threshold guard before any withdrawal is constructed.",
        ),
        (
            "multi_address_management",
            "No cold/hot/operational address management exists.",
            "Add an address book with cold/hot/operational roles.",
        ),
    ]
    if not exists:
        return [
            not_implemented(
                AGENT,
                rule,
                detail=f"{detail} No payout/withdrawal module found in "
                f"{', '.join(_SCAN_DIRS)}.",
                fix=fix,
            )
            for rule, detail, fix in rules
        ]
    # If payout code appears, re-verify structurally.
    results = []
    for rule, detail, fix in rules:
        results.append(
            not_implemented(
                AGENT,
                rule,
                detail=f"Payout-related code found at {where}, but no "
                "contract-level enforcement was located.",
                fix=fix,
            )
        )
    return results
