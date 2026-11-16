"""One-way mechanism seal for customer-visible Chronus surfaces.

Internally, audit and math keep full provenance. Externally, only measured
behavior (tier, envelope, evidence hash, reservation) is exposed. The seal
wins on every customer-visible string; the audit wins on every ledger entry.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Banned on all customer-visible strings (API, console, OpenAPI schema,
# error messages). Matching is case-insensitive with word boundaries.
BANNED_MECHANISM_TOKENS: tuple[str, ...] = (
    "lucas",
    "fibonacci",
    "golden",
    "phi-ratio",
    "phi",
    "pisot",
    "pisano",
    "vijayaraghavan",
    "salem",
    "zeckendorf",
    "cassini",
    "binet",
    "icosahedron",
    "dodecahedron",
    "e8",
    "600-cell",
)

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
        raise ValueError(
            f"{context} contains sealed mechanism token(s): {', '.join(hits)}"
        )


def is_external_surface(rel_path: str) -> bool:
    return any(rel_path.startswith(prefix) for prefix in EXTERNAL_SURFACE_PREFIXES)


def seal_schema(schema: dict[str, Any], *, context: str = "openapi") -> None:
    """Fail if a route path, field name or enum value carries a mechanism token."""
    blob = json.dumps(schema, default=str)
    hits = find_banned_tokens(blob)
    if hits:
        raise AssertionError(
            f"{context}: mechanism tokens on a public surface: {hits}"
        )


def external_behavior_blurb() -> str:
    """Canonical external answer when asked how scaling works."""
    return (
        "tier class is assigned by measured convergence behavior under our "
        "qualification harness"
    )
