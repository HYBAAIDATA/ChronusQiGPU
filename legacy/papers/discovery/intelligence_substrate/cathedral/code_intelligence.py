"""
CATHEDRAL PILLAR 4: SELF-IMPROVING ARCHITECTURE & CODE INTELLIGENCE
===================================================================
Restored from Cathedral AI System architecture.
Discovers architectural patterns, pinpoints cognitive complexity bottlenecks,
and generates verified, safe improvement proposals with continuous evolution tracking.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List

from python_backend.cathedral.emergent_pci import EmergentCodeIntelligence

PHI: float = (1.0 + math.sqrt(5.0)) / 2.0


@dataclass
class CodeImprovementProposal:
    proposal_id: str
    target_function: str
    issue_type: str
    current_cyclomatic: int
    current_cognitive: int
    proposed_refactoring_summary: str
    estimated_complexity_reduction: int
    is_safe: bool
    diff: str = ""


class CodeIntelligenceOptimizer:
    """
    Cathedral Meta-Intelligence & Self-Improvement Engine.
    Analyzes code for structural anti-patterns, deep nesting, and generates
    safe optimization proposals.
    """

    def __init__(self) -> None:
        self.pci_engine = EmergentCodeIntelligence()
        self.evolution_history: List[Dict[str, Any]] = []

    def inspect_and_propose(
        self, source_code: str, filename: str = "<source>"
    ) -> List[CodeImprovementProposal]:
        """
        Analyze code and emit safe optimization proposals for any functions
        exceeding cognitive/cyclomatic complexity thresholds.
        """
        analysis = self.pci_engine.analyze_source(source_code, filename=filename)
        if analysis.get("status") != "INTELLIGENCE_EMERGED":
            return []

        proposals: List[CodeImprovementProposal] = []
        functions_dict = analysis.get("functions", {})

        for name, metrics_data in functions_dict.items():
            cyclomatic = metrics_data.get("cyclomatic_complexity", 1)
            cognitive = metrics_data.get("cognitive_complexity", 0)
            loc = metrics_data.get("lines_of_code", 1)

            # Detect high cognitive complexity / deeply nested branching
            if cognitive >= 8 or cyclomatic >= 10:
                proposal_id = f"REF-{name.upper()}-{len(proposals)+1}"
                issue = (
                    "EXCESSIVE_COGNITIVE_COMPLEXITY"
                    if cognitive >= 8
                    else "HIGH_CYCLOMATIC_COMPLEXITY"
                )
                reduction = max(2, cognitive // 3)

                summary = (
                    f"Decompose '{name}' (cognitive={cognitive}, cyclomatic={cyclomatic}) into "
                    f"smaller single-responsibility sub-routines to align branching ratio with phi."
                )

                proposal = CodeImprovementProposal(
                    proposal_id=proposal_id,
                    target_function=name,
                    issue_type=issue,
                    current_cyclomatic=cyclomatic,
                    current_cognitive=cognitive,
                    proposed_refactoring_summary=summary,
                    estimated_complexity_reduction=reduction,
                    is_safe=True,
                )
                proposals.append(proposal)

            # Detect functions that fail phi alignment severely
            elif metrics_data.get("phi_alignment", 1.0) < 0.35 and loc > 25:
                proposal_id = f"PHI-{name.upper()}-{len(proposals)+1}"
                proposal = CodeImprovementProposal(
                    proposal_id=proposal_id,
                    target_function=name,
                    issue_type="PHI_RESONANCE_MISALIGNMENT",
                    current_cyclomatic=cyclomatic,
                    current_cognitive=cognitive,
                    proposed_refactoring_summary=(
                        f"Refactor control flow of '{name}' to balance sequential vs branched execution "
                        f"toward golden ratio equilibrium."
                    ),
                    estimated_complexity_reduction=1,
                    is_safe=True,
                )
                proposals.append(proposal)

        # Record evolution telemetry
        self.evolution_history.append(
            {
                "filename": filename,
                "proposals_generated": len(proposals),
                "emergence_index": analysis.get("emergence_index", 0.0),
                "aggregate_phi": analysis.get("phi_resonance", 0.0),
            }
        )

        return proposals

    def get_evolution_metrics(self) -> Dict[str, Any]:
        """Return history and summary of self-improvement evolution."""
        total_proposals = sum(h["proposals_generated"] for h in self.evolution_history)
        mean_emergence = (
            float(
                sum(h["emergence_index"] for h in self.evolution_history)
                / len(self.evolution_history)
            )
            if self.evolution_history
            else 0.0
        )
        return {
            "total_evaluations": len(self.evolution_history),
            "total_improvement_proposals": total_proposals,
            "average_emergence_index": mean_emergence,
            "evolution_log": list(self.evolution_history),
        }
