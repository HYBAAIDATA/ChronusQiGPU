"""Agent table, vocabulary isolation, and the write-path guard.

The load-bearing rule: TRUTH agents never write; CHANGE agents emit
bounded bundles only; CONTROL agents cannot patch code. No agent both
judges and fixes. No shared mandates. No mixed vocabularies. Humans merge.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Set

STRICT = True

LAYERS = {
    "TRUTH": frozenset({1, 6, 7, 8, 9, 10}),
    "CHANGE": frozenset({2, 3}),
    "CONTROL": frozenset({4, 5}),
}

AGENT = {
    1: "auditor",
    2: "remediator",
    3: "test_engineer",
    4: "governance",
    5: "provenance",
    6: "math_verifier",
    7: "security_verifier",
    8: "quantum_checker",
    9: "precision_sentinel",
    10: "pin_verifier",
}

# Vocabularies MUST NOT mix. Each agent reads/writes only its own.
VOCAB = {
    1: {"claim", "trace", "laureate", "reduction", "confirmed_defect"},
    6: {"holds", "fails", "undecidable", "range", "symbolic", "counterexample"},
    7: {"fail_closed", "fails_open", "stub_crypto", "real_crypto",
        "key_lifecycle"},
    8: {"unitary", "non_unitary", "channel", "kraus", "cptp",
        "measurement_formalism"},
    9: {"exact", "float_leak", "bound_violated", "ill_conditioned",
        "cancellation"},
    2: {"draft_pr", "minimal_diff", "file_cap", "byte_cap",
        "complexity_cap", "why_this_fix"},
    3: {"known_answer", "property", "falsification", "failure_predicate",
        "tests_dir_only"},
    4: {"pass", "fail", "not_provable", "reason"},
    5: {"sha", "chain_of_custody", "replayable"},
    10: {"pin_holds", "pin_violated", "theorem_proven_false_everywhere"},
}

# Change-layer caps — cap by complexity and fanout, not just size.
REMEDIATOR_MAX_FILES = 4
REMEDIATOR_MAX_BYTES = 128 * 1024
REMEDIATOR_MAX_CYCLOMATIC = 10
REMEDIATOR_MAX_FANOUT = 3

# This tree keeps its suite at repo-root tests/ (the spec's
# python_backend/tests/** belongs to a different layout).
TESTS_DIR = "tests/"
PROVENANCE_DIR = "docs/provenance"


def may_write(agent_id: int, path: str, *, is_draft_pr: bool = False) -> bool:
    """Write-path guard — the one rule everything else defers to."""
    if agent_id not in AGENT:
        raise ValueError(f"unknown agent id {agent_id}")
    if agent_id in LAYERS["TRUTH"]:
        return False
    if agent_id == 2:
        return is_draft_pr and path_in_change_scope(agent_id, path)
    if agent_id == 3:
        return is_draft_pr and path_in_change_scope(agent_id, path)
    if agent_id == 4:
        return False
    if agent_id == 5:
        return path.startswith(PROVENANCE_DIR + "/") and path.endswith(".json")
    return False


def path_in_change_scope(agent_id: int, path: str) -> bool:
    if agent_id == 2:
        return not path.startswith(TESTS_DIR)  # remediate code, not tests
    if agent_id == 3:
        return path.startswith(TESTS_DIR)
    return False


def may_approve(agent_id: int) -> bool:
    return False


def may_merge(agent_id: int) -> bool:
    return False


def suite_is_non_tautological(agent_ids: Optional[Iterable[int]] = None) -> bool:
    """Non-tautology invariant: writers exist, no truth-writer, no dual role,
    nobody approves, nobody merges."""
    ids: Set[int] = set(agent_ids) if agent_ids is not None else set(AGENT)
    writers = [a for a in ids if a in LAYERS["CHANGE"]]
    truth_writers = [a for a in writers if a in LAYERS["TRUTH"]]
    dual_role = [a for a in ids if a in LAYERS["TRUTH"] and a in LAYERS["CHANGE"]]
    return (
        bool(writers)
        and not truth_writers
        and not dual_role
        and all(not may_approve(a) for a in ids)
        and all(not may_merge(a) for a in ids)
    )


def repo_root(start: Optional[Path] = None) -> Path:
    """Repo root = two parents above this file (hyba/operating_model/)."""
    return (start or Path(__file__)).resolve().parents[2]
