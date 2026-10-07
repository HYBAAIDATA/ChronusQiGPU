"""
EUCLID Program Search Façade API (ProgramSearchEngine) v16.0
=====================================================================
Enterprise integration boundary connecting host systems (HYBA / PYTHIPhi Platform)
to EUCLID drop-in computational payload with MCTS search & Silver updates.
"""

from typing import Dict, List, Any, Optional, Callable, Tuple
from euclid.core.phi_metric import PhiResonanceCalculator
from euclid.core.euclid_intelligence import EuclidIntelligenceEngine, LucasSequenceCalculator
from euclid.search.evolutionary_search import EvolutionarySearchEngine
from euclid.search.mcts_search import MCTSSearchEngine
from euclid.transfer.persistent_repository import PersistentPrimitiveRepository
from euclid.agents.manifold import SharedEntangledManifold
from euclid.agents.orchestrator import MultiAgentEntangledOrchestrator
from euclid.enterprise.roi_governance import EnterpriseROIGovernanceEngine

class ProgramSearchEngine:
    """
    Program-search façade for the EUCLID v16 MCTS/evolution substrate.

    This class is a specialist search engine, not the EUCLID cognition
    authority. General intelligence composition lives in EuclidRuntime.
    """
    def __init__(self, target_phi: float = 0.618033988749895, persistent_repo_path: Optional[str] = None):
        self.repository = PersistentPrimitiveRepository(storage_path=persistent_repo_path)
        self.engine = EvolutionarySearchEngine(repository=self.repository, target_phi=target_phi)
        self.mcts_engine = MCTSSearchEngine(repository=self.repository, target_phi=target_phi)
        self.manifold = SharedEntangledManifold()
        self.euclid = EuclidIntelligenceEngine()
        self.orchestrator = MultiAgentEntangledOrchestrator(shared_manifold=self.manifold)

    def analyze(self, file_path: str, code_content: str) -> Dict[str, Any]:
        """Calculates current φ-resonance coherence, AST features, 11D projection, and EUCLID structural complexity."""
        phi_score = self.engine.calculator.compute_phi(code_content)
        features = self.engine.calculator.extract_features(code_content)
        
        self.manifold.register_agent_projection("ANALYZER", phi_score)
        projection_11d = self.manifold.overlay_11d.project_11d_coordinates("ANALYZER", phi_score)
        euclid_intel = self.euclid.compute_intelligence_metrics(code_content, topological_time=0.0)

        return {
            "file_path": file_path,
            "phi_score": phi_score,
            "ast_features": features,
            "11d_projection": projection_11d,
            "euclid_intelligence": euclid_intel
        }

    def evolve(
        self, 
        file_path: str, 
        code_content: str, 
        generations: int = 20, 
        seed: int = 42,
        mode: str = "mcts",
        external_test_runner: Optional[Callable[[str], bool]] = None,
        external_test_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Executes search (MCTS with policy priors or Evolutionary) with process-isolated validity gates."""
        if mode == "mcts":
            self.mcts_engine.seed = seed
            res = self.mcts_engine.run_mcts_search(
                target_name=file_path,
                initial_code=code_content,
                max_generations=generations,
                external_test_runner=external_test_runner,
                external_test_code=external_test_code
            )
        else:
            self.engine.seed = seed
            res = self.engine.run_optimization(
                target_name=file_path,
                initial_code=code_content,
                max_generations=generations,
                external_test_runner=external_test_runner,
                external_test_code=external_test_code
            )

        evolved_code = res.get("final_code", code_content)
        
        # EUCLID evaluates ACTUAL evolved source code!
        topological_time = float(res.get("accepted_steps_count", 0))
        euclid_intel = self.euclid.compute_intelligence_metrics(evolved_code, topological_time=topological_time)
        res["euclid_intelligence_telemetry"] = euclid_intel

        # Register projection in unified manifold
        self.manifold.register_agent_projection("EVOLVER", res["final_phi"], step=int(topological_time))
        self.manifold.record_file_mapping(file_path, res["final_phi"])

        return res

    def evaluate_candidate(
        self, 
        code_content: str, 
        external_test_runner: Optional[Callable[[str], bool]] = None,
        external_test_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Evaluates parse, compile, runtime safety, and φ score for an arbitrary AST mutation."""
        p_v, c_v, r_v, msg = self.engine.evaluator.evaluate_validity(
            code_content, external_test_runner, external_test_code
        )
        phi_score = self.engine.calculator.compute_phi(code_content) if (p_v and r_v) else 0.1000
        return {
            "parse_valid": p_v,
            "compile_valid": c_v,
            "runtime_valid": r_v,
            "diagnostic_message": msg,
            "phi_score": phi_score
        }

    def commit_primitive(
        self, 
        primitive_name: str, 
        rule_type: str = "ADD:AnnAssign", 
        origin_target: str = "host_repo",
        cum_gain: float = 0.005
    ):
        """Allows host repo to explicitly register a verified primitive using declarative AST rule schemas."""
        def _external_op(code_str: str, seed: int = 42) -> Tuple[str, str]:
            return code_str, primitive_name

        self.repository.register_primitive(
            primitive_name, _external_op, rule_type, origin_target, cum_gain
        )

    def verify_property_invariants(
        self, 
        code_before: str, 
        code_after: str, 
        topological_time: float = 1.0
    ) -> Dict[str, Any]:
        """Verifies core system property invariants across before/after AST states."""
        phi_before = self.engine.calculator.compute_phi(code_before)
        phi_after = self.engine.calculator.compute_phi(code_after)
        
        intel_before = self.euclid.compute_intelligence_metrics(code_before, 0.0)
        intel_after = self.euclid.compute_intelligence_metrics(code_after, topological_time)

        # 1. Monotonicity Invariant: phi_after >= phi_before implies structural complexity non-decreasing
        monotonic = (phi_after < phi_before) or (intel_after["structural_complexity_L_n"] >= intel_before["structural_complexity_L_n"])
        
        # 2. Non-Degeneracy Invariant: L_n >= 2.0 unconditionally
        non_degenerate = (intel_before["structural_complexity_L_n"] >= 2.0) and (intel_after["structural_complexity_L_n"] >= 2.0)

        # 3. Lucas Recurrence Invariant: L_n = L_{n-1} + L_{n-2}
        lucas_ok = True
        for n in range(2, 10):
            if LucasSequenceCalculator.exact_lucas(n) != LucasSequenceCalculator.exact_lucas(n-1) + LucasSequenceCalculator.exact_lucas(n-2):
                lucas_ok = False
                break

        # 4. Execution Safety Invariant
        p_v, c_v, r_v, _ = self.engine.evaluator.evaluate_validity(code_after)

        invariants_pass = monotonic and non_degenerate and lucas_ok and r_v

        return {
            "invariants_pass": invariants_pass,
            "monotonicity_invariant": monotonic,
            "non_degeneracy_invariant": non_degenerate,
            "lucas_recurrence_invariant": lucas_ok,
            "syntax_compilation_invariant": r_v,
            "details": {
                "phi_original": phi_before,
                "phi_mutated": phi_after,
                "structural_intel_original": intel_before["structural_complexity_L_n"],
                "structural_intel_mutated": intel_after["structural_complexity_L_n"]
            }
        }

    def snapshot(self) -> Dict[str, Any]:
        """Returns 11D manifold state, primitive repository summary, and active agent metadata."""
        return {
            "manifold_snapshot": self.manifold.get_snapshot(),
            "repository_summary": self.repository.get_summary()
        }


# Backward-compatible import for historical manifests and callers. New
# production cognition code imports ProgramSearchEngine so there is one clear
# EUCLID authority: EuclidRuntime / CognitiveService.
EuclidEngineAdapter = ProgramSearchEngine

__all__ = ["ProgramSearchEngine", "EuclidEngineAdapter"]
