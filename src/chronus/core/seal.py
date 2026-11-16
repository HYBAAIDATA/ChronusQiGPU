"""One-way mechanism seal for customer-visible Chronus surfaces.

Internally, audit and math keep full provenance. Externally, only measured
behavior (tier, envelope, evidence hash) is exposed. The seal wins on every
customer-visible string; the audit wins on every ledger entry.
"""

from __future__ import annotations

import re
from typing import Iterable

# Banned on all customer-visible strings (API, console, docs under seal scope,
# error messages, manifests). Matching is case-insensitive with word boundaries
# so substrings like "graphic" do not trip on ``phi``.
BANNED_MECHANISM_TOKENS: tuple[str, ...] = (
    "lucas",
    "fibonacci",
    "golden",
    "phi-ratio",
    "phi",
    "pisot",
    "zeckendorf",
    "cassini",
    "binet",
    "icosahedron",
    "dodecahedron",
    "e8",
    "600-cell",
)

# Customer-visible path prefixes (relative to repo root). Internal math,
# execution, tests, audit ledgers, historical manifests, and research HTML
# demos under frontend/public/ stay outside this set (provenance / archive).
EXTERNAL_SURFACE_PREFIXES: tuple[str, ...] = (
    "frontend/app/",
    "frontend/components/",
    "frontend/lib/",
    "src/chronus/service/",
    "console/",
)

_TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (token, re.compile(rf"(?i)(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"))
    for token in BANNED_MECHANISM_TOKENS
)


def find_banned_tokens(text: str) -> list[str]:
    """Return banned tokens found in ``text`` (deduplicated, stable order)."""
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for token, pattern in _TOKEN_PATTERNS:
        if pattern.search(text) and token not in seen:
            found.append(token)
            seen.add(token)
    return found


def assert_sealed(text: str, *, context: str = "external surface") -> None:
    hits = find_banned_tokens(text)
    if hits:
        raise ValueError(f"{context} contains sealed mechanism token(s): {', '.join(hits)}")


def is_external_surface(rel_path: str) -> bool:
    return any(rel_path.startswith(prefix) for prefix in EXTERNAL_SURFACE_PREFIXES)


def scrub_dict_strings(payload: dict, *, context: str = "api payload") -> dict:
    """Recursively assert string keys and leaves are sealed; returns the same dict."""
    def walk(node, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                key_path = f"{path}.{key}" if path else str(key)
                if isinstance(key, str):
                    assert_sealed(key, context=f"{context}:{key_path}")
                walk(value, key_path)
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        elif isinstance(node, str):
            assert_sealed(node, context=f"{context}:{path}")

    walk(payload, "")
    return payload


def external_behavior_blurb() -> str:
    """Canonical external answer when asked how scaling works."""
    return (
        "tier class is assigned by measured convergence behavior under our "
        "qualification harness"
    )
