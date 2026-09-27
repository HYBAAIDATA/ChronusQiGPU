"""Proof 4: a third-party implementation can be scored."""

from __future__ import annotations

from typing import Any, Dict

from igpu.seam.invariants import score as score_invariants


def score(module: Any = None) -> Dict[str, Any]:
    return score_invariants(module)
