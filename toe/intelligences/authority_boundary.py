"""Canonical EUCLID/PYTHIA intelligence authority boundary.

EUCLID owns cognition and may advise specialist systems. PYTHIA remains the
final authority for mining truth and every transition that can affect Bitcoin
consensus semantics or pool-facing execution.

This module is deliberately dependency-free so both production code and tests
can import the same contract without creating a second authority graph.
"""
from __future__ import annotations

from typing import Final

CANONICAL_EUCLID_INTELLIGENCES: Final[tuple[str, ...]] = (
    "predictive",
    "causal",
    "counterfactual",
    "topological",
    "geometric",
)

# Quantum is an extension/capability surface, not a sixth canonical EUCLID
# intelligence. L-HRAS/AL HARAS owns security decisions; TURING owns quantum
# compute. EUCLID may consume their evidence but does not absorb their authority.
EUCLID_EXTENSIONS: Final[tuple[str, ...]] = ("quantum",)

PYTHIA_FINAL_AUTHORITY: Final[frozenset[str]] = frozenset(
    {
        "search-plan",
        "nonce-estate-coverage",
        "hendrix-traversal",
        "sha256d",
        "target",
        "share-validation",
        "submission",
        "pool-acknowledgement",
        "credentials",
    }
)

EUCLID_FORBIDDEN_DOMAINS: Final[frozenset[str]] = frozenset(
    {
        "bitcoin-header",
        "nonce-semantics",
        "sha256d",
        "target",
        "credentials",
        "share-validation",
        "submission",
        "pool-acknowledgement",
    }
)

# Twelve advisory domains recovered from the intelligence-first workstream.
# They are reasoning/learning surfaces only: none conveys execution authority.
EUCLID_ADVISORY_DOMAINS: Final[frozenset[str]] = frozenset(
    {
        "prediction",
        "causal-reasoning",
        "counterfactual-reasoning",
        "topological-reasoning",
        "geometric-reasoning",
        "representation",
        "memory",
        "planning",
        "hypothesis-generation",
        "strategy-selection",
        "transfer",
        "discovery",
    }
)


def _normalise(domain: str) -> str:
    return str(domain).strip().lower().replace("_", "-")


def is_pythia_final(domain: str) -> bool:
    """Return True when the domain is final-authority PYTHIA territory."""
    return _normalise(domain) in PYTHIA_FINAL_AUTHORITY


def is_forbidden(domain: str) -> bool:
    """Return True when EUCLID must never claim or exercise this authority."""
    return _normalise(domain) in EUCLID_FORBIDDEN_DOMAINS


def is_advisory(domain: str) -> bool:
    """Return True when EUCLID may reason/learn without owning execution."""
    return _normalise(domain) in EUCLID_ADVISORY_DOMAINS


__all__ = [
    "CANONICAL_EUCLID_INTELLIGENCES",
    "EUCLID_EXTENSIONS",
    "PYTHIA_FINAL_AUTHORITY",
    "EUCLID_FORBIDDEN_DOMAINS",
    "EUCLID_ADVISORY_DOMAINS",
    "is_pythia_final",
    "is_forbidden",
    "is_advisory",
]
