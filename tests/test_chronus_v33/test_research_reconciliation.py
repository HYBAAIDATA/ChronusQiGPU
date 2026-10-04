from __future__ import annotations

from pathlib import Path

import pytest

from al_haras.refuted_claims import ClaimRefuted, assert_claims
from chronus.v33.research_reconciliation import (
    CLAIMS,
    DISPOSITIONS,
    DOMAINS,
    LINTERS,
    by_domain,
    linted_claims,
    validate_claims,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_every_documented_claim_is_dispositioned_and_sourced():
    validate_claims()
    for claim in CLAIMS:
        assert claim.disposition in DISPOSITIONS, claim.id
        assert claim.source_page, claim.id
        assert claim.source_url.startswith("https://"), claim.id


def test_refuted_and_prohibited_quotes_are_caught_by_the_al_haras_linter():
    checked = 0
    for claim in linted_claims():
        if claim.lint != "al_haras":
            continue
        with pytest.raises(ClaimRefuted):
            assert_claims(claim.page_quote)
        checked += 1
    assert checked >= 8, checked


def test_every_linted_claim_names_a_known_linter():
    for claim in linted_claims():
        assert claim.lint in LINTERS, claim.id


def test_verified_claims_name_evidence():
    verified = [claim for claim in CLAIMS if claim.disposition == "VERIFIED"]
    assert verified
    for claim in verified:
        assert claim.evidence, claim.id


def test_hypotheses_stay_isolated():
    for claim in CLAIMS:
        if claim.disposition == "HYPOTHESIS":
            assert claim.isolated_under, claim.id


def test_the_catalogue_covers_mining_intelligence_and_quantum():
    for domain in DOMAINS:
        assert by_domain(domain), domain


def test_the_reconciliation_document_exists():
    assert (_REPO_ROOT / "docs" / "RESEARCH_RECONCILIATION.md").is_file()
