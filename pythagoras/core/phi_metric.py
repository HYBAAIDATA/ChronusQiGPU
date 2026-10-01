"""
PYTHAGORAS Golden Ratio Structural Resonance Calculator (φ⁻¹ = 0.618033988749895)
==================================================================================
Computes φ-resonance over a module's *effective* AST (see core.structure):

    raw  = 0.35
         + 0.20 · annotation_coherence      annotated sites, with contradictions subtracted
         + 0.15 · depth_balance             1 / (1 + |depth − 8|)
         + 0.10 · complexity_balance        min(effective_nodes / 50, 1)
         + 0.10 · function_balance          min(live_functions / 5, 1)
         + 0.10 · golden_growth_resonance   level-to-level AST growth vs 1/target_phi (= φ)

    φ-score = clamp(raw · integrity, 0.10, 0.99)
    integrity = (1 − redundant_nodes / raw_nodes) ** φ

Docstrings, comments, dead branches, unreachable code, shadowed definitions,
repeated assignments and unreferenced private helpers contribute nothing to
the structural terms, and all but docstrings lower `integrity`. Appending
code that is never used therefore cannot raise the score.

Weights live in PHI_WEIGHTS so the host project can recalibrate.
"""
import ast
from typing import Any, Dict

from pythagoras.core.structure import (
    analyze_structure, golden_growth_resonance, ast_depth, StructureReport,
)

PHI_TARGET = 0.618033988749895

PHI_WEIGHTS = {
    "base": 0.35,
    "annotation_coherence": 0.20,
    "depth_balance": 0.15,
    "complexity_balance": 0.10,
    "function_balance": 0.10,
    "golden_growth": 0.10,
}
DEPTH_TARGET = 8
COMPLEXITY_SCALE = 50.0
FUNCTION_SCALE = 5.0


class PhiResonanceCalculator:
    def __init__(self, target_phi: float = PHI_TARGET):
        if not 0.0 < target_phi < 1.0:
            raise ValueError("target_phi must lie in (0, 1); the golden growth ratio is 1 / target_phi")
        self.target_phi = target_phi

    # Contract: compute_phi(code_str) -> float in [0.10, 0.99]
    def compute_phi(self, code_str: str) -> float:
        return self.components(code_str)["phi_score"]

    def components(self, code_str: str, report: StructureReport = None) -> Dict[str, Any]:
        report = report or analyze_structure(code_str)
        if not report.parse_ok:
            return {"phi_score": 0.1000, "parse_ok": False}

        w = PHI_WEIGHTS
        depth_balance = 1.0 / (1.0 + abs(report.depth - DEPTH_TARGET))
        complexity_balance = min(report.effective_nodes / COMPLEXITY_SCALE, 1.0)
        function_balance = min(report.function_count / FUNCTION_SCALE, 1.0)
        growth = golden_growth_resonance(report.level_widths, 1.0 / self.target_phi)

        raw = (w["base"]
               + w["annotation_coherence"] * report.annotation_coherence
               + w["depth_balance"] * depth_balance
               + w["complexity_balance"] * complexity_balance
               + w["function_balance"] * function_balance
               + w["golden_growth"] * growth)
        score = round(min(0.9900, max(0.1000, raw * report.integrity)), 6)

        return {
            "phi_score": score,
            "parse_ok": True,
            "raw_resonance": round(raw, 6),
            "integrity": report.integrity,
            "annotation_coherence": report.annotation_coherence,
            "depth_balance": round(depth_balance, 6),
            "complexity_balance": round(complexity_balance, 6),
            "function_balance": round(function_balance, 6),
            "golden_growth_resonance": growth,
        }

    def _get_ast_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        return ast_depth(node, current_depth)

    def extract_features(self, code_str: str) -> Dict[str, Any]:
        report = analyze_structure(code_str)
        if not report.parse_ok:
            return {"node_count": 0, "depth": 0, "annotation_density": 0.0, "function_count": 0,
                    "statement_count": 0, "phi_score": 0.1000, "parse_ok": False}
        comps = self.components(code_str, report)
        return {
            "node_count": report.effective_nodes,
            "raw_node_count": report.raw_nodes,
            "depth": report.depth,
            "annotation_density": report.annotation_density,
            "function_count": report.function_count,
            "statement_count": report.statement_count,
            "redundant_nodes": report.redundant_nodes,
            "redundancy_breakdown": report.redundancy,
            "contradictory_annotations": report.contradictory_annotations,
            **{k: v for k, v in comps.items() if k != "parse_ok"},
        }
