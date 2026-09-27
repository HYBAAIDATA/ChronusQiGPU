"""
PYTHAGORAS — DOMAIN REGISTRY
Pluggable domains for the meta-evolutionary engine.

The engine is the point; the domain is pluggable. Registered domains:
    - code:     Python AST coherence        (the first domain)
    - circuit:  quantum/classical gate coherence
    - molecule: molecular folding coherence
    - market:   causal dependency coherence
    - network:  topology coherence

Register additional domains via register_domain().
"""

from __future__ import annotations

from typing import Dict, List, Type

from ..domain import Domain
from .code_domain import CodeDomain
from .circuit_domain import CircuitDomain
from .market_domain import MarketDomain
from .molecule_domain import MoleculeDomain
from .network_domain import NetworkDomain


_DOMAIN_TYPES: Dict[str, Type[Domain]] = {
    CodeDomain.name: CodeDomain,
    CircuitDomain.name: CircuitDomain,
    MoleculeDomain.name: MoleculeDomain,
    MarketDomain.name: MarketDomain,
    NetworkDomain.name: NetworkDomain,
}


def register_domain(domain_cls: Type[Domain]) -> None:
    """Register a Domain subclass under its canonical name."""
    if not issubclass(domain_cls, Domain):
        raise TypeError("register_domain expects a Domain subclass")
    _DOMAIN_TYPES[domain_cls.name] = domain_cls


def available_domains() -> List[str]:
    """Return the registered domain names."""
    return sorted(_DOMAIN_TYPES.keys())


def get_domain(name: str = "code") -> Domain:
    """Instantiate a registered domain by name."""
    if name not in _DOMAIN_TYPES:
        raise KeyError(
            f"unknown domain '{name}'. Available: {', '.join(available_domains())}"
        )
    return _DOMAIN_TYPES[name]()


__all__ = [
    "CodeDomain",
    "CircuitDomain",
    "MoleculeDomain",
    "MarketDomain",
    "NetworkDomain",
    "available_domains",
    "get_domain",
    "register_domain",
]
