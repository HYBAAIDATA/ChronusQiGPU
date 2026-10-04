from __future__ import annotations

from pathlib import Path

import pytest

from al_haras.refuted_claims import ClaimRefuted, assert_claims
from al_haras.unmeasured_claims import ClaimUnmeasured, assert_no_unmeasured_claims
from chronus.v33.research_reconciliation import (
    CLAIMS,
    DISPOSITIONS,
    DOMAINS,
    LINTERS,
    by_domain,
    linted_claims,
    claims_with_test_results,
    claims_untested,
    validate_claims,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_every_documented_claim_is_dispositioned_and_sourced():
    validate_claims()
    for claim in CLAIMS:
        assert claim.disposition in DISPOSITIONS, claim.id
        assert claim.source_page, claim.id
        assert claim.source_url.startswith("https://"), claim.id


def test_nothing_is_refuted_without_a_regime_an_outcome_and_an_artefact():
    refuted = [claim for claim in CLAIMS if claim.disposition == "TESTED_AND_REFUTED"]
    assert refuted
    for claim in refuted:
        assert claim.regime, claim.id
        assert claim.outcome, claim.id
        assert claim.evidence, claim.id


def test_untested_claims_carry_no_test_result():
    untested = claims_untested()
    assert untested
    for claim in untested:
        assert claim.falsification, claim.id
        assert not claim.regime, claim.id
        assert not claim.outcome, claim.id


def test_the_refuted_lint_stays_silent_on_untested_claims():
    """The rule, as a gate: an untested claim is not a refuted one."""
    for claim in claims_untested():
        try:
            assert_claims(claim.page_quote)
        except ClaimRefuted as exc:  # pragma: no cover - fires only on regression
            raise AssertionError(
                f"{claim.id} is untested, but the refuted register claims it: {exc}"
            ) from None


def test_unmeasured_phrasings_are_caught_by_the_unmeasured_lint():
    checked = 0
    for claim in CLAIMS:
        if claim.lint != "unmeasured":
            continue
        with pytest.raises(ClaimUnmeasured):
            assert_no_unmeasured_claims(claim.page_quote)
        checked += 1
    assert checked >= 8, checked


def test_prohibited_phrasings_are_caught_by_their_named_linter():
    checked = 0
    for claim in CLAIMS:
        if claim.disposition != "PROHIBITED" or claim.lint != "refuted-register":
            continue
        with pytest.raises(ClaimRefuted):
            assert_claims(claim.page_quote)
        checked += 1
    assert checked >= 2, checked


def test_every_linted_claim_names_a_known_linter():
    for claim in linted_claims():
        assert claim.lint in LINTERS, claim.id


def test_no_prohibited_entry_borrows_a_test_result():
    for claim in CLAIMS:
        if claim.disposition == "PROHIBITED":
            assert claim.reason, claim.id
            assert not claim.regime and not claim.outcome, claim.id


def test_hypotheses_stay_isolated():
    for claim in CLAIMS:
        if claim.disposition == "HYPOTHESIS":
            assert claim.isolated_under, claim.id


def test_verified_claims_name_a_test():
    verified = [claim for claim in claims_with_test_results() if claim.disposition == "VERIFIED"]
    assert verified
    for claim in verified:
        assert claim.test_node, claim.id


def test_the_catalogue_covers_mining_intelligence_and_quantum():
    for domain in DOMAINS:
        assert by_domain(domain), domain


def test_the_reconciliation_document_exists():
    assert (_REPO_ROOT / "docs" / "RESEARCH_RECONCILIATION.md").is_file()
