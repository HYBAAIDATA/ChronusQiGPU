"""Regression contract for EUCLID/PYTHIA authority separation."""
from __future__ import annotations

import importlib
import inspect

import pytest

from toe.intelligences.authority_boundary import (
    CANONICAL_EUCLID_INTELLIGENCES,
    EUCLID_ADVISORY_DOMAINS,
    EUCLID_EXTENSIONS,
    EUCLID_FORBIDDEN_DOMAINS,
    PYTHIA_FINAL_AUTHORITY,
    is_advisory,
    is_forbidden,
    is_pythia_final,
)

INTELLIGENCE_MODULES = (
    "toe.intelligences.causal",
    "toe.intelligences.counterfactual",
    "toe.intelligences.geometric",
    "toe.intelligences.plastic",
    "toe.intelligences.quantum",
)


def test_canonical_five_are_exact():
    assert CANONICAL_EUCLID_INTELLIGENCES == (
        "predictive",
        "causal",
        "counterfactual",
        "topological",
        "geometric",
    )


def test_quantum_is_extension_not_canonical():
    assert EUCLID_EXTENSIONS == ("quantum",)
    assert "quantum" not in CANONICAL_EUCLID_INTELLIGENCES


def test_advisory_scope_has_twelve_domains():
    assert len(EUCLID_ADVISORY_DOMAINS) == 12


@pytest.mark.parametrize(
    "domain",
    (
        "search-plan",
        "nonce-estate-coverage",
        "hendrix-traversal",
        "sha256d",
        "target",
        "share-validation",
        "submission",
        "pool-acknowledgement",
        "credentials",
    ),
)
def test_pythia_final_domains(domain):
    assert is_pythia_final(domain)


@pytest.mark.parametrize(
    "domain",
    (
        "bitcoin-header",
        "nonce-semantics",
        "sha256d",
        "target",
        "credentials",
        "share-validation",
        "submission",
        "pool-acknowledgement",
    ),
)
def test_euclid_forbidden_domains(domain):
    assert is_forbidden(domain)


@pytest.mark.parametrize(
    "domain",
    (
        "prediction",
        "causal_reasoning",
        "counterfactual-reasoning",
        "topological_reasoning",
        "geometric-reasoning",
        "representation",
        "memory",
        "planning",
        "hypothesis-generation",
        "strategy-selection",
        "transfer",
        "discovery",
    ),
)
def test_euclid_advisory_domains(domain):
    assert is_advisory(domain)


def test_consensus_domains_never_advisory():
    assert not (EUCLID_FORBIDDEN_DOMAINS & EUCLID_ADVISORY_DOMAINS)


@pytest.mark.parametrize("module_name", INTELLIGENCE_MODULES)
def test_intelligence_modules_no_longer_claim_full_authority(module_name):
    source = inspect.getsource(importlib.import_module(module_name))
    assert "FULL AUTHORITY" not in source.upper()


@pytest.mark.parametrize("module_name", INTELLIGENCE_MODULES)
def test_intelligence_modules_declare_advisory_boundary(module_name):
    source = inspect.getsource(importlib.import_module(module_name))
    assert "ADVISORY" in source.upper()
    assert "PYTHIA" in source.upper()
