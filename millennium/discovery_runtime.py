"""Governed runtime for the previously disconnected mathematical discovery engine.

This module is the production composition root between ``MillenniumSuite`` and
``MathematicalDiscoveryEngine``.  It intentionally preserves a hard boundary:
probe measurements and generated candidates are research inputs, never proof
claims.  Promotion to a theorem remains outside this runtime and requires a
complete derivation, formal verification where feasible, and independent
review.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from millennium.millennium_suite import MillenniumSuite, _series_for

SCHEMA = "hyba.millennium.discovery-campaign/v1"
DEFAULT_PROBLEM = "riemann"
_ALLOWED_PROBLEMS = {
    "riemann",
    "p_vs_np",
    "yang_mills",
    "navier_stokes",
    "bsd",
    "hodge",
    "poincare",
}
_PROOF_FLAGS = {"proof_claim", "theorem_proven", "mathematically_complete"}


def _default_engine_factory() -> Any:
    # Lazy import keeps the ordinary ``python -m millennium`` probe path light,
    # while making this runtime a real production importer of the formerly
    # trapped 3,108-line engine.
    from millennium.mathematical_discovery import MathematicalDiscoveryEngine

    return MathematicalDiscoveryEngine()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _reject_proof_escalation(value: Any, path: str = "output") -> None:
    """Fail closed if any downstream component sets a proof flag true."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in _PROOF_FLAGS and child is True:
                raise RuntimeError(
                    f"discovery claim-boundary violation at {child_path}: true"
                )
            _reject_proof_escalation(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_proof_escalation(child, f"{path}[{index}]")


def _problem_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    """Translate one governed probe result into the explorer's input schema."""
    return {
        "problem_id": result["problem_id"],
        "name": result["problem"],
        "clay_status": result["clay_status"],
        "evidence_class": result["evidence_class"],
        "established_scope": result["established_scope"],
        "statement_of_scope": result["honest_conclusion"],
        "proof_claim": False,
        "measurements": {
            "probe_work_units": result["probe_work_units"],
            "probe_dimension": result["probe_dimension"],
            "entropy_bits": result.get("entropy_bits", 0.0),
        },
        "series": _series_for(result),
    }


async def run_discovery_campaign(
    problem_id: str = DEFAULT_PROBLEM,
    *,
    scale: str = "standard",
    max_depth: int = 3,
    engine_factory: Optional[Callable[[], Any]] = None,
    suite_factory: Callable[..., Any] = MillenniumSuite,
) -> Dict[str, Any]:
    """Run one bounded Millennium probe through the mathematical explorer.

    The returned envelope separates governed probe evidence from unverified
    candidate output.  No result from this function may be promoted directly
    to ``ESTABLISHED`` or used as a theorem certificate.
    """
    if problem_id not in _ALLOWED_PROBLEMS:
        raise ValueError(
            f"unknown problem {problem_id!r}; expected one of "
            f"{sorted(_ALLOWED_PROBLEMS)}"
        )
    if max_depth < 1:
        raise ValueError("max_depth must be >= 1")

    suite = suite_factory(scale=scale)
    probe_report = suite.run(only=[problem_id])
    suite.assert_no_established(probe_report)
    if len(probe_report["results"]) != 1:
        raise RuntimeError(
            f"expected exactly one probe result for {problem_id!r}, got "
            f"{len(probe_report['results'])}"
        )

    payload = _problem_payload(probe_report["results"][0])
    engine = (engine_factory or _default_engine_factory)()
    candidate_output = await engine.deep_mathematical_exploration(
        [payload], max_depth=max_depth
    )
    _reject_proof_escalation(candidate_output)

    discoveries = candidate_output.get("discoveries_by_frontier", {})
    candidate_count = sum(
        len(items) for items in discoveries.values() if isinstance(items, list)
    )

    return {
        "schema": SCHEMA,
        "campaign": {
            "problem_id": problem_id,
            "scale": scale,
            "max_depth": max_depth,
            "input_sha256": _canonical_digest(payload),
        },
        "claim_boundary": {
            "status": "CANDIDATE_GENERATION_ONLY",
            "proof_claim": False,
            "theorem_proven": False,
            "mathematically_complete": False,
            "promotion_requires": [
                "explicit theorem with assumptions and quantifiers",
                "complete derivation closing the accepted problem statement",
                "formal verification where feasible",
                "negative controls and reproducible artifacts",
                "independent expert review",
            ],
        },
        "governed_probe": payload,
        "candidate_count": candidate_count,
        "unverified_engine_output": candidate_output,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a governed Millennium probe through the mathematical discovery "
            "engine. Outputs are candidates, never proof claims."
        )
    )
    parser.add_argument(
        "--problem", choices=sorted(_ALLOWED_PROBLEMS), default=DEFAULT_PROBLEM
    )
    parser.add_argument("--scale", default="standard")
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--json", dest="json_path", default=None)
    args = parser.parse_args(argv)

    report = asyncio.run(
        run_discovery_campaign(
            args.problem,
            scale=args.scale,
            max_depth=args.depth,
        )
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.json_path:
        output = Path(args.json_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
