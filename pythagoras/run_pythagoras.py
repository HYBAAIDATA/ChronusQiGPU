"""Executable verification and healing entry point for PYTHAGORAS v12."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from .adapter import PythagorasEngineAdapter
from .agents.orchestrator import MultiAgentEntangledOrchestrator
from .enterprise.roi_governance import EnterpriseROIGovernanceEngine
from .healing import RepositoryHealingOrchestrator


SAMPLE_CODE = """\
class DataPipeline:
    def process(self, items: list) -> list:
        result: list = []
        for item in items:
            result.append(item * 0.618034)
        return result
"""


def run_verification(generations: int = 5) -> Dict[str, Any]:
    """Exercise every public v12 subsystem without modifying the repository."""
    adapter = PythagorasEngineAdapter()
    analysis = adapter.analyze("data_pipeline.py", SAMPLE_CODE, topological_time=1.0)
    evolution = adapter.evolve(
        "data_pipeline.py",
        SAMPLE_CODE,
        generations=generations,
        seed=42,
    )
    invariants = adapter.verify_property_invariants(
        SAMPLE_CODE,
        str(evolution["final_code"]),
        topological_time=1.0,
    )
    roi = EnterpriseROIGovernanceEngine.calculate_technical_debt_reduction(
        total_evaluations=evolution.get("total_evals_attempted"),
        valid_evaluations=evolution.get("total_evals_valid"),
        initial_phi=float(evolution["initial_phi"]),
        final_phi=float(evolution["final_phi"]),
        wall_time_ms=float(evolution["wall_time_ms"]),
    )
    orchestrator = MultiAgentEntangledOrchestrator(adapter=adapter)
    multi_agent = orchestrator.run_multi_agent_cycle(
        [{"name": "data_pipeline.py", "code_str": SAMPLE_CODE}],
        generations=max(1, min(generations, 3)),
        seed=43,
    )
    return {
        "version": "12.0.0",
        "analysis": analysis,
        "evolution": evolution,
        "invariants": invariants,
        "governance": roi,
        "multi_agent": multi_agent,
        "snapshot": adapter.snapshot(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PYTHAGORAS v12 integration runner")
    parser.add_argument("--generations", type=int, default=5)
    parser.add_argument("--heal-file", action="append", default=[])
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--verify-cmd", default=None)
    parser.add_argument("--persistent-state", default=None)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.heal_file:
        bridge = RepositoryHealingOrchestrator(
            repo_root=Path(args.repo_root),
            verify_cmd=args.verify_cmd,
            persistent_repo_path=args.persistent_state,
        )
        result: Any = bridge.optimize_files(
            args.heal_file,
            generations=args.generations,
        )
    else:
        result = run_verification(generations=args.generations)

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
