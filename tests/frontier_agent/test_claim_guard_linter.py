"""Tests for claim guard documentation linter enforcing no-claims clause (6.5)."""

from pathlib import Path
from scripts.claim_guard_linter import check_content, lint_file


def test_claim_guard_rejects_agi_claim():
    bad_content = "We hereby declare that AGI achieved in this release cycle."
    violations = check_content(bad_content)
    assert len(violations) == 1
    assert "AGI/ASI" in violations[0][2]


def test_claim_guard_rejects_superiority_claim():
    bad_content = "Our benchmark results show model superiority proven conclusively."
    violations = check_content(bad_content)
    assert len(violations) == 1
    assert "superiority" in violations[0][2]


def test_claim_guard_rejects_millennium_prize_claim():
    bad_content = "The team reports that the Riemann Hypothesis is solved by the kernel."
    violations = check_content(bad_content)
    assert len(violations) == 1
    assert "Millennium" in violations[0][2]


def test_claim_guard_rejects_quantum_supremacy_claim():
    bad_content = "Empirical run demonstrates that quantum speedup achieved on commodity CPU."
    violations = check_content(bad_content)
    assert len(violations) == 1
    assert "Quantum" in violations[0][2]


def test_claim_guard_rejects_unauthorized_deployment_claim():
    bad_content = "This commit is authorized for production deployment immediately."
    violations = check_content(bad_content)
    assert len(violations) == 1
    assert "authorization" in violations[0][2]


def test_claim_guard_permits_explicit_negative_disclaimers():
    safe_content = (
        "No AGI/ASI, scientific model superiority, Millennium prize proof or quantum-speedup claim. "
        "This draft is an implementation/evidence handoff, not production approval. "
        "No main merge, release, deployment authorized."
    )
    violations = check_content(safe_content)
    assert len(violations) == 0


def test_committed_frontier_docs_pass_claim_guard():
    # Frontier docs committed in this PR must pass the claim guard check
    frontier_impl = Path("docs/EUCLID_FRONTIER_IMPLEMENTATION.md")
    if frontier_impl.exists():
        violations = lint_file(frontier_impl)
        assert len(violations) == 0, f"Found unexpected violations in {frontier_impl}: {violations}"
