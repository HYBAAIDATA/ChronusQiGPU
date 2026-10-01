"""Mining integration boundary for PYTHAGORAS v12 and EUCLID.

EUCLID owns repository-level Intelligence evaluation. The existing PYTHAGORAS
engine remains the transformation/meta-evolution substrate. This façade does not
interfere with Stratum, nonce search, share submission, or mining telemetry.
"""
from __future__ import annotations

from typing import Any, Dict

from .core.euclid_intelligence import EuclidIntelligenceEngine, LucasSequenceCalculator
from .orchestrator import Pythagoras


class PythagorasEngineAdapter:
    """Host-facing façade over the mining repository's canonical Pythagoras engine."""

    def __init__(self, condition: str = "B", domain: Any = "code") -> None:
        self.engine = Pythagoras(condition=condition, domain=domain)
        self.euclid_intelligence = EuclidIntelligenceEngine(pisot_base=20.0)

    def analyze_intelligence(self, file_path: str, code_content: str, topological_time: float = 0.0) -> Dict[str, Any]:
        result = self.euclid_intelligence.compute_intelligence_scale(code_content, topological_time)
        result["file_path"] = file_path
        return result

    def analyze(self, file_path: str, code_content: str, topological_time: float = 0.0) -> Dict[str, Any]:
        return {
            "file_path": file_path,
            "domain": self.engine.domain.name,
            "phi_score": self.engine.domain.coherence(code_content),
            "euclid_intelligence": self.analyze_intelligence(file_path, code_content, topological_time),
        }

    def evolve(self, file_path: str, code_content: str, generations: int = 20) -> Dict[str, Any]:
        initial = self.euclid_intelligence.compute_intelligence_scale(code_content, 0.0)
        result = self.engine.evolve_file(code_content, generations=generations, filename=file_path)
        final_source = result.get("final_source", code_content)
        topological_time = float(max(0, len(result.get("fitness_history", [])) - 1))
        final = self.euclid_intelligence.compute_intelligence_scale(final_source, topological_time)
        result["euclid_intelligence_telemetry"] = {
            "owner": "EUCLID_REPO_INTELLIGENCE",
            "initial_intelligence": initial,
            "final_intelligence": final,
            "topological_time_source": "pythagoras_generation_history",
        }
        return result

    def evaluate_candidate(self, code_content: str) -> Dict[str, Any]:
        try:
            compile(code_content, "<pythagoras-candidate>", "exec")
        except (SyntaxError, ValueError, TypeError):
            return {"parse_valid": False, "compile_valid": False, "phi_score": 0.1000, "euclid_intelligence_score": 0.0}
        return {
            "parse_valid": True,
            "compile_valid": True,
            "phi_score": self.engine.domain.coherence(code_content),
            "euclid_intelligence_score": self.euclid_intelligence.compute_intelligence_scale(code_content, 0.0)["intelligence_score"],
        }

    def verify_property_invariants(self, original_code: str, mutated_code: str, topological_time: float = 1.0) -> Dict[str, Any]:
        phi_original = self.engine.domain.coherence(original_code)
        phi_mutated = self.engine.domain.coherence(mutated_code)
        intel_original = self.euclid_intelligence.compute_intelligence_scale(original_code, topological_time)
        intel_mutated = self.euclid_intelligence.compute_intelligence_scale(mutated_code, topological_time)
        try:
            compile(mutated_code, "<pythagoras-mutated>", "exec")
            compilation_holds = True
        except (SyntaxError, ValueError, TypeError):
            compilation_holds = False
        monotonicity_holds = phi_mutated <= phi_original or intel_mutated["intelligence_score"] >= intel_original["intelligence_score"]
        non_degeneracy_holds = intel_original["intelligence_score"] >= 2.0 and intel_mutated["intelligence_score"] >= 2.0
        n = intel_mutated["lucas_index_discrete"]
        lucas = LucasSequenceCalculator()
        recurrence_holds = n < 2 or lucas.exact_lucas(n) == lucas.exact_lucas(n - 1) + lucas.exact_lucas(n - 2)
        return {
            "invariants_pass": monotonicity_holds and non_degeneracy_holds and recurrence_holds and compilation_holds,
            "monotonicity_invariant": monotonicity_holds,
            "non_degeneracy_invariant": non_degeneracy_holds,
            "lucas_recurrence_invariant": recurrence_holds,
            "syntax_compilation_invariant": compilation_holds,
            "details": {"phi_original": phi_original, "phi_mutated": phi_mutated, "intelligence_original": intel_original["intelligence_score"], "intelligence_mutated": intel_mutated["intelligence_score"]},
        }
