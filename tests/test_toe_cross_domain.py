"""One backend, many problem forms — the architectural claim, measured.

Materially different problem classes run through ONE TOEMachine; only the
adapter (translation) differs per domain. Adapter code never appears in a
backend trace, the reasoning core never imports the adapters, and the new
core modules carry no mining vocabulary.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from toe.voyage import DOMAINS, cross_domain_voyage

ROOT = Path(__file__).resolve().parent.parent

CORE_MODULES = (
    "machine.py",
    "problem.py",
    "relationships.py",
    "geometry.py",
    "custody.py",
    "topology.py",
    "world_model.py",
    "precision.py",
    "causal_stack.py",
    "planning.py",
    "policy.py",
    "meta_reasoning.py",
    "intelligence_state.py",
    "representation.py",
)

_MINING_TERMS = re.compile(
    r"\bStratum\b|(?i:\b(nonces?|extranonce\w*|hashrate|mining|miners?|bitcoin|sha256d"
    r"|wallets?|viabtc|nicehash|braiins|ckpool|share_\w+|pool_\w+)\b)"
)


@pytest.fixture(scope="module")
def voyage():
    return cross_domain_voyage()


def test_every_domain_runs_through_one_machine(voyage):
    assert voyage["machine_instances"] == 1
    assert set(voyage["domains"]) == set(DOMAINS)
    for name, d in voyage["domains"].items():
        assert d["backend"] == "toe.machine.TOEMachine", name
        assert d["result"]["status"] in ("ACT", "NAVIGATE", "DESCRIBE"), (name, d["result"])


def test_adapter_code_never_executes_as_backend(voyage):
    assert voyage["reuse"]["adapter_code_in_any_backend_trace"] == []
    for d in voyage["domains"].values():
        assert d["adapter_code_in_backend_trace"] == []


def test_shared_core_path_is_measured(voyage):
    shared = set(voyage["reuse"]["shared_by_every_domain"])
    assert {
        "toe.representation.choose",
        "toe.intelligence_state.IntelligenceState.observe",
    } <= shared
    assert voyage["reuse"]["backend_callables_total"] >= 15


def test_domain_results_are_the_domain_answers(voyage):
    d = voyage["domains"]
    assert d["tabular"]["result"]["arbitration"] == "DISAGREEMENT"
    assert d["causal_system"]["result"]["plan"] == ["small_step+2", "small_step+2"]
    assert d["graph"]["result"]["representations"]["euclidean_greedy"] is False
    assert d["code"]["result"]["unreachable_from_source"] == ["legacy_export"]
    assert d["scientific.recurrence"]["result"]["forecast_method"].startswith(
        "exact integer recurrence"
    )
    assert d["scientific.linear_system"]["result"]["precision"]["regime"] == "exact-required"
    assert d["temporal"]["result"]["futures_rung"] == 2
    assert d["legacy_hr"]["result"]["selected"] == "set_promotion=1.0"


def test_reasoning_core_never_imports_adapters():
    for name in CORE_MODULES:
        tree = ast.parse((ROOT / "toe" / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "adapters" not in mod, f"{name} imports {mod}"
            elif isinstance(node, ast.Import):
                assert not any("adapters" in a.name for a in node.names), name


@pytest.mark.parametrize(
    "module", CORE_MODULES + ("adapters/__init__.py", "adapters/legacy_hr.py", "voyage.py")
)
def test_core_and_adapters_carry_no_mining_semantics(module):
    source = (ROOT / "toe" / module).read_text(encoding="utf-8")
    assert _MINING_TERMS.findall(source) == [], module


def test_adapters_are_small(voyage):
    # Domain cost is translation only; measured, not asserted elsewhere.
    for name, d in voyage["domains"].items():
        assert d["adapter_code_lines"] < 80, (name, d["adapter_code_lines"])
