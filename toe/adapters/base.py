"""The adapter contract: translate in, interpret out — never reason."""

from __future__ import annotations

import inspect
from typing import Any, Dict, Mapping

from ..problem import Problem


class OptionalDependencyUnavailable(ImportError):
    """An optional capability was requested without its extra installed."""


class ProblemAdapter:
    """Subclass and implement ``to_problem``; ``interpret`` is optional.

    ``vocabulary`` maps backend node names to domain words, so the
    interpretation speaks the domain's language without the backend ever
    knowing it.
    """

    name = "adapter"
    vocabulary: Mapping[str, str] = {}

    def to_problem(self, raw: Any) -> Problem:
        raise NotImplementedError

    def _word(self, node: Any) -> str:
        return str(self.vocabulary.get(str(node), node))

    def interpret(self, episode: Mapping[str, Any]) -> Dict[str, Any]:
        """Domain-language summary of an episode (presentation only)."""
        rec = episode.get("recommendation") or {}
        out: Dict[str, Any] = {
            "domain": self.name,
            "status": episode.get("status"),
            "episode_sha256": episode.get("episode_sha256"),
        }
        if rec.get("interventions"):
            out["recommended_settings"] = {
                self._word(k): v for k, v in (rec.get("interventions") or {}).items()
            }
            out["recommendation_kind"] = rec.get("kind")
        nav = episode.get("navigation")
        if nav and nav.get("route"):
            out["route"] = [self._word(s) for s in nav["route"]]
        if episode.get("forecast", {}).get("available"):
            out["forecast"] = episode["forecast"]["value"]
        if episode.get("refusal"):
            out["refusal"] = episode["refusal"]
        return out

    def domain_code_lines(self) -> int:
        """Non-empty, non-comment source lines of this adapter class — the
        measured cost of supporting the domain."""
        src = inspect.getsource(type(self))
        return sum(
            1 for ln in src.splitlines() if ln.strip() and not ln.strip().startswith("#")
        )


__all__ = ["OptionalDependencyUnavailable", "ProblemAdapter"]
