"""Collaborative Automation and Automated Runbook CLI & Dashboard Generator.

Standard-library entrypoint over ``salamander.collaborative_automation``.
Preserves all HYBA/PYTHIA authority boundaries: never fabricates hardware
execution, pool acceptance, or unprovided human approvals.

Run:
  python -m tools.collaborative_automation --catalogue
  python -m tools.collaborative_automation --dashboard
  python -m tools.collaborative_automation --run cyber_it_disaster_recovery
  python -m tools.collaborative_automation --run cyber_it_disaster_recovery --approve-all-human --actor sec-lead-01
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from salamander.collaborative_automation import (  # noqa: E402
    AutomationToolCategory,
    BathtubGuard,
    CollaborativeAutomationEngine,
    CollaborativeRunbook,
    HumanDecision,
    StepMode,
    TeamRole,
    build_canonical_workflow_runbooks,
    load_repository_catalogue_runbooks,
    select_automation_tool,
)


def full_runbook_catalogue(
    *,
    tenant_id: str = "hyba_enterprise",
    catalogue_path: str | Path | None = None,
) -> dict[str, CollaborativeRunbook]:
    """Return the unified dictionary of canonical Collaborative Automation workflows
    plus the repository's ``runbooks/catalogue.json`` operational recovery runbooks."""
    combined: dict[str, CollaborativeRunbook] = {}
    combined.update(build_canonical_workflow_runbooks(tenant_id=tenant_id))
    combined.update(
        load_repository_catalogue_runbooks(
            catalogue_path=catalogue_path,
            tenant_id=tenant_id,
        )
    )
    return combined


def catalogue_payload(
    *,
    tenant_id: str = "hyba_enterprise",
    catalogue_path: str | Path | None = None,
) -> dict[str, Any]:
    """Serializable catalogue of all collaborative runbooks and tool archetypes."""
    canonical = build_canonical_workflow_runbooks(tenant_id=tenant_id)
    repo_cat = load_repository_catalogue_runbooks(
        catalogue_path=catalogue_path,
        tenant_id=tenant_id,
    )
    tool_matrix = [
        select_automation_tool(
            "EUCLID/TOE predictive and causal anomaly context",
            requires_predictive_analytics=True,
        ).to_dict(),
        select_automation_tool(
            "Deterministic rule-based regression and lease drain tasks",
            repetitive_rule_based=True,
        ).to_dict(),
        select_automation_tool(
            "Chronus/Salamander bounded infrastructure and recovery actuation",
            infrastructure_or_config=True,
        ).to_dict(),
        select_automation_tool(
            "OVID/THESEUS cross-system receipt exchange and witness lineage",
            cross_system_data_exchange=True,
        ).to_dict(),
    ]
    return {
        "schema": "hyba.collaborative.catalogue.v1",
        "tenant_id": tenant_id,
        "canonical_workflow_count": len(canonical),
        "repository_catalogue_count": len(repo_cat),
        "total_runbooks": len(canonical) + len(repo_cat),
        "tool_selection_matrix": tool_matrix,
        "canonical_workflows": {k: v.to_dict() for k, v in canonical.items()},
        "repository_catalogue_runbooks": {k: v.to_dict() for k, v in repo_cat.items()},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalogue",
        action="store_true",
        help="Emit the unified Collaborative Automation runbook catalogue JSON.",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Emit the Single Pane of Glass operational dashboard JSON.",
    )
    parser.add_argument(
        "--run",
        metavar="RUNBOOK_ID",
        help="Execute a named collaborative runbook and emit its execution report JSON.",
    )
    parser.add_argument(
        "--approve-all-human",
        action="store_true",
        help="Record explicit human-in-the-loop approvals for all human checkpoints in the target runbook.",
    )
    parser.add_argument(
        "--actor",
        default="operator-cli",
        help="Actor identity for recorded human-in-the-loop decisions.",
    )
    parser.add_argument(
        "--rationale",
        default="CLI operator verified prerequisites and approved collaborative checkpoint.",
        help="Rationale attached to human-in-the-loop approvals.",
    )
    parser.add_argument(
        "--tenant",
        default="hyba_enterprise",
        help="Tenant identifier for runbook execution.",
    )
    parser.add_argument(
        "--scale-phase",
        type=int,
        default=4,
        help="Incremental BathtubGuard scale phase index (default: 4 -> 8 steps max).",
    )
    args = parser.parse_args(argv)

    all_runbooks = full_runbook_catalogue(tenant_id=args.tenant)
    engine = CollaborativeAutomationEngine(
        bathtub_guard=BathtubGuard(scale_phase_index=args.scale_phase),
    )

    if args.catalogue:
        print(json.dumps(catalogue_payload(tenant_id=args.tenant), indent=2, sort_keys=True))
        return 0

    if args.run:
        runbook = all_runbooks.get(args.run)
        if runbook is None:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": f"unknown runbook_id: {args.run!r}",
                        "available_runbooks": sorted(all_runbooks),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2

        if args.approve_all_human:
            for step in runbook.ordered_steps():
                if step.mode in (StepMode.HUMAN_IN_THE_LOOP, StepMode.COLLABORATIVE_HYBRID):
                    role: TeamRole = (
                        step.required_approver_roles[0]
                        if step.required_approver_roles
                        else step.owner_team
                    )
                    engine.record_human_decision(
                        HumanDecision(
                            decision_id=f"cli-dec:{runbook.runbook_id}:{step.step_id}",
                            runbook_id=runbook.runbook_id,
                            step_id=step.step_id,
                            actor_id=args.actor,
                            team_role=role,
                            approved=True,
                            rationale=args.rationale,
                            at_ns=time.time_ns(),
                        )
                    )

        report = engine.execute_runbook(runbook)
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 0 if report.status.value in ("COMPLETED_VERIFIED", "AWAITING_HUMAN") else 1

    # Default or --dashboard: emit Single Pane of Glass dashboard
    dashboard = engine.single_pane_dashboard(all_runbooks.values())
    print(json.dumps(dashboard, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
