"""
PYTHAGORAS Integration Façade API (PythagorasEngineAdapter)
===========================================================
Enterprise integration boundary connecting host systems (HYBA / PYTHIPhi Platform)
to the PYTHAGORAS drop-in computational payload without leaking engine internals.

EUCLID owns Intelligence overall, using Lucas L_n numbers and the Lucas
20^(phi * t_p) Intelligence Scaling Formula:
    Intelligence_EUCLID = L_n * 20^(phi * t_p)

v12.1 contract notes
  - Method names, parameters and result keys from v12.0 are preserved; new keys are additive.
  - topological_time (t_p) is host-supplied. Before/after comparisons always use the same t_p.
  - Candidate code never runs in the host process (AL HARAS isolated gate, core.sandbox).
"""
from typing import Any, Callable, Dict, List, Optional, Tuple

from pythagoras.agents.manifold import AgentID, SharedEntangledManifold
from pythagoras.core import sandbox
from pythagoras.core.euclid_intelligence import EuclidIntelligenceEngine, LucasSequenceCalculator, PHI
from pythagoras.core.phi_metric import PhiResonanceCalculator
from pythagoras.core.primitives import OPERATOR_REGISTRY, compose
from pythagoras.core.state import measure_state
from pythagoras.engine.v6_4_cross_file_reuse import CrossFilePrimitiveRepository
from pythagoras.engine.v6_2_geometry import CollectiveGeometryCoordinator
from pythagoras.engine.v6_5_manifold_escape import AnnealingConfig, V65ManifoldEscapeEngine


class PythagorasEngineAdapter:
    """Stable, host-facing façade for the PYTHAGORAS Meta-Evolution Engine."""

    def __init__(self, target_phi: float = 0.618033988749895, persistent_repo_path: Optional[str] = None,
                 sandbox_config: Optional[sandbox.SandboxConfig] = None, euclid_gate: bool = True,
                 annealing: Optional[AnnealingConfig] = None,
                 geometry_signal: str = "measured_phi"):
        self.repository = CrossFilePrimitiveRepository(storage_path=persistent_repo_path)
        saved = self.repository.get_adaptive_state()
        collective = CollectiveGeometryCoordinator(saved.get("collective_geometry"))
        self.engine = V65ManifoldEscapeEngine(repository=self.repository, target_phi=target_phi,
                                              sandbox_config=sandbox_config, euclid_gate=euclid_gate,
                                              annealing=annealing, geometry_signal=geometry_signal,
                                              collective_geometry=collective)
        self.engine.surrogate.import_state(saved.get("surrogate"))
        self.euclid_intelligence = EuclidIntelligenceEngine(pisot_base=20.0)
        self.manifold = SharedEntangledManifold()

    # ------------------------------------------------------------------ analysis
    def analyze(self, file_path: str, code_content: str, topological_time: float = 0.0) -> Dict[str, Any]:
        """φ-resonance, EUCLID intelligence, AST features, AL HARAS audit and measured 11D state."""
        phi_score = self.engine.calculator.compute_phi(code_content)
        features = self.engine.calculator.extract_features(code_content)
        intelligence = self.euclid_intelligence.compute_intelligence_scale(code_content, topological_time)
        state = measure_state(code_content, self.engine.calculator, self.euclid_intelligence)
        projection = self.manifold.overlay_11d.project_11d_coordinates(AgentID.EUCLID.value, phi_score, state["vector"])
        return {
            "file_path": file_path,
            "phi_score": phi_score,
            "euclid_intelligence": intelligence,
            "ast_features": features,
            "al_haras_audit": sandbox.al_haras_audit(code_content).to_dict(),
            "11d_state": state["axes"],
            "11d_projection": projection,
            "dual_symmetry_coherence": self.manifold.overlay_11d.dual_coherence(projection),
        }

    def analyze_intelligence(self, file_path: str, code_content: str, topological_time: float = 0.0) -> Dict[str, Any]:
        intel = self.euclid_intelligence.compute_intelligence_scale(code_content, topological_time)
        intel["file_path"] = file_path
        return intel

    # ------------------------------------------------------------------ evolution
    def evolve(self, file_path: str, code_content: str, generations: int = 20, seed: int = 42,
               external_test_runner: Optional[Callable[[str], bool]] = None,
               topological_time: float = 0.0) -> Dict[str, Any]:
        """V6.5 evolutionary search. Intelligence telemetry compares initial and final code at the
        same t_p, so the gain ratio reflects the code change only."""
        self.engine.seed = seed
        res = self.engine.run_optimization(target_name=file_path, initial_code=code_content,
                                           max_generations=generations, external_test_runner=external_test_runner)
        final_code = res["final_code"]
        initial_intel = self.euclid_intelligence.compute_intelligence_scale(code_content, topological_time)
        final_intel = self.euclid_intelligence.compute_intelligence_scale(final_code, topological_time)
        res["final_code_sample"] = final_code  # v12.0 key, kept for host compatibility
        res["euclid_intelligence_telemetry"] = {
            "topological_time_t_p": topological_time,
            "initial_intelligence": initial_intel,
            "final_intelligence": final_intel,
            "intelligence_gain_ratio": round(final_intel["intelligence_score"] / max(initial_intel["intelligence_score"], 1e-12), 6),
            "lucas_phase_transitions": res["lucas_phase_transitions"],
        }
        self._persist_adaptive_state()
        return res

    def _persist_adaptive_state(self) -> None:
        self.repository.save_adaptive_state({
            "schema_version": 1,
            "surrogate": self.engine.surrogate.export_state(),
            "collective_geometry": self.engine.collective_geometry.to_dict(),
        })

    def evaluate_candidate(self, code_content: str,
                           external_test_runner: Optional[Callable[[str], bool]] = None) -> Dict[str, Any]:
        rec = sandbox.validate(code_content, external_test_runner, self.engine.sandbox_config)
        parse_v = rec["parse_valid"]
        phi_score = self.engine.calculator.compute_phi(code_content) if parse_v else 0.1000
        intel = self.euclid_intelligence.compute_intelligence_scale(code_content, 0.0) if parse_v else {"intelligence_score": 0.0}
        return {
            "parse_valid": parse_v,
            "compile_valid": rec["compile_valid"],
            "runtime_valid": rec["runtime_valid"],
            "runtime_mode": rec["runtime_mode"],
            "reason": rec["reason"],
            "al_haras_audit": rec["audit"],
            "phi_score": phi_score,
            "euclid_intelligence_score": intel["intelligence_score"],
        }

    # ------------------------------------------------------------------ invariants
    def verify_property_invariants(self, original_code: str, mutated_code: str, topological_time: float = 1.0,
                                   external_test_runner: Optional[Callable[[str], bool]] = None) -> Dict[str, Any]:
        """
        1. Monotonicity (implication): φ(mut) > φ(orig) ⇒ I(mut, t_p) ≥ I(orig, t_p)
        2. Non-degeneracy (positivity): I > 0 for both — follows from L(x) > 0 for x ≥ 0
        3. Lucas consistency: L_n = L_{n−1} + L_{n−2} and the Pisot rounding identity
           L_n = round(φ^n) (n ≥ 2) at the mutated code's index. Validates the calculator,
           not the transformation.
        4. Validity: mutated code parses and compiles
        5. Behaviour preservation: host tests pass on both versions (None when no runner given)
        """
        phi_orig = self.engine.calculator.compute_phi(original_code)
        phi_mut = self.engine.calculator.compute_phi(mutated_code)
        intel_orig = self.euclid_intelligence.compute_intelligence_scale(original_code, topological_time)
        intel_mut = self.euclid_intelligence.compute_intelligence_scale(mutated_code, topological_time)
        rec = sandbox.validate(mutated_code, None, self.engine.sandbox_config)

        monotonicity = (not phi_mut > phi_orig) or (intel_mut["intelligence_score"] >= intel_orig["intelligence_score"])
        non_degeneracy = intel_orig["intelligence_score"] > 0 and intel_mut["intelligence_score"] > 0

        calc = LucasSequenceCalculator()
        n = intel_mut["lucas_index_discrete"]
        if n >= 2:
            lucas_ok = (calc.exact_lucas(n) == calc.exact_lucas(n - 1) + calc.exact_lucas(n - 2)
                        and calc.exact_lucas(n) == round(PHI ** n))
        else:
            lucas_ok = True

        behaviour = None
        if external_test_runner is not None:
            try:
                behaviour = bool(external_test_runner(original_code)) and bool(external_test_runner(mutated_code))
            except Exception:
                behaviour = False

        syntax_ok = rec["parse_valid"] and rec["compile_valid"]
        all_pass = monotonicity and non_degeneracy and lucas_ok and syntax_ok and behaviour is not False
        return {
            "invariants_pass": all_pass,
            "monotonicity_invariant": monotonicity,
            "non_degeneracy_invariant": non_degeneracy,
            "lucas_recurrence_invariant": lucas_ok,
            "syntax_compilation_invariant": syntax_ok,
            "behaviour_preservation_invariant": behaviour,
            "behaviour_preservation_note": None if behaviour is not None else "not verified: no host test runner supplied",
            "details": {
                "topological_time_t_p": topological_time,
                "phi_original": phi_orig,
                "phi_mutated": phi_mut,
                "intelligence_original": intel_orig["intelligence_score"],
                "intelligence_mutated": intel_mut["intelligence_score"],
            },
        }

    # ------------------------------------------------------------------ primitives
    def commit_primitive(self, primitive_name: str, op_func_code_str: str, origin_target: str = "host_repo"):
        """Registers a host-defined primitive as a recipe over registry operators, e.g.
        "ADD:AnnAssign + NON_LOCAL:function_split_refactor". Raises ValueError for unknown operators."""
        recipe = [p.strip() for p in op_func_code_str.replace("|", "+").replace(",", "+").split("+") if p.strip()]
        if not recipe:
            raise ValueError("primitive recipe is empty")
        op = compose(recipe, primitive_name)  # validates operator names
        self.repository.register_promoted_primitive(primitive_name, op, origin_target, 0.0)
        self.engine.discovery_engine.promoted_vocabulary[primitive_name] = op

    def available_operators(self) -> List[str]:
        return sorted(OPERATOR_REGISTRY)

    # ------------------------------------------------------------------ agents
    def orchestrate(self, files: List[Dict[str, Any]], generations: int = 10,
                    external_test_runner: Optional[Callable[[str], bool]] = None) -> Dict[str, Any]:
        from pythagoras.agents.orchestrator import MultiAgentEntangledOrchestrator
        orch = MultiAgentEntangledOrchestrator(self.engine.calculator, self.manifold, self.engine)
        result = orch.run_multi_agent_cycle(files, generations, external_test_runner)
        self._persist_adaptive_state()
        return result

    def snapshot(self) -> Dict[str, Any]:
        return {"manifold_snapshot": self.manifold.get_snapshot(),
                "repository_summary": self.repository.get_summary(),
                "adaptive_state": {
                    "surrogate": self.engine.surrogate.export_state(),
                    "collective_geometry": self.engine.collective_geometry.to_dict(),
                }}
