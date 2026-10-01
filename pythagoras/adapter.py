"""
PYTHAGORAS Integration Façade API (PythagorasEngineAdapter)
===========================================================
Enterprise integration boundary connecting host systems (HYBA / PYTHIPhi Platform)
to the production PYTHAGORAS computational payload without leaking engine internals.

EUCLID owns Intelligence overall, using Lucas L_n numbers and the Lucas
20^(phi * t_p) Intelligence Scaling Formula:
    Intelligence_EUCLID = L_n * 20^(phi * t_p)

v12.2 contract notes
  - Method names, parameters and result keys from v12.0 are preserved; new keys are additive.
  - topological_time (t_p) is host-supplied. Before/after comparisons always use the same t_p.
  - Candidate code never runs in the host process (AL HARAS isolated gate, core.sandbox).
  - Historical V6 staged engines are not part of the production host-facing surface.
"""

from typing import Any, Callable, Dict, List, Optional

from pythagoras.agents.manifold import AgentID, SharedEntangledManifold
from pythagoras.core import sandbox
from pythagoras.core.euclid_intelligence import EuclidIntelligenceEngine, LucasSequenceCalculator, PHI
from pythagoras.core.primitives import OPERATOR_REGISTRY, compose
from pythagoras.core.state import measure_state
from pythagoras.engine.evolution import AnnealingConfig, PythagorasEvolutionEngine
from pythagoras.engine.geometry import CollectiveGeometryCoordinator
from pythagoras.engine.primitive_repository import CrossFilePrimitiveRepository


class PythagorasEngineAdapter:
    """Stable host-facing façade for the PYTHAGORAS meta-evolution engine."""

    def __init__(
        self,
        target_phi: float = 0.618033988749895,
        persistent_repo_path: Optional[str] = None,
        sandbox_config: Optional[sandbox.SandboxConfig] = None,
        euclid_gate: bool = True,
        annealing: Optional[AnnealingConfig] = None,
        geometry_signal: str = "measured_phi",
    ):
        self.repository = CrossFilePrimitiveRepository(storage_path=persistent_repo_path)
        saved = self.repository.get_adaptive_state()
        collective = CollectiveGeometryCoordinator(saved.get("collective_geometry"))
        self.engine = PythagorasEvolutionEngine(
            repository=self.repository,
            target_phi=target_phi,
            sandbox_config=sandbox_config,
            euclid_gate=euclid_gate,
            annealing=annealing,
            geometry_signal=geometry_signal,
            collective_geometry=collective,
        )
        self.engine.surrogate.import_state(saved.get("surrogate"))
        self.euclid_intelligence = EuclidIntelligenceEngine(pisot_base=20.0)
        self.manifold = SharedEntangledManifold()

    def analyze(
        self,
        file_path: str,
        code_content: str,
        topological_time: float = 0.0,
    ) -> Dict[str, Any]:
        """Return measured φ, EUCLID, AST, AL HARAS and 11D state data."""
        phi_score = self.engine.calculator.compute_phi(code_content)
        features = self.engine.calculator.extract_features(code_content)
        intelligence = self.euclid_intelligence.compute_intelligence_scale(
            code_content,
            topological_time,
        )
        state = measure_state(
            code_content,
            self.engine.calculator,
            self.euclid_intelligence,
        )
        projection = self.manifold.overlay_11d.project_11d_coordinates(
            AgentID.EUCLID.value,
            phi_score,
            state["vector"],
        )
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

    def analyze_intelligence(
        self,
        file_path: str,
        code_content: str,
        topological_time: float = 0.0,
    ) -> Dict[str, Any]:
        intelligence = self.euclid_intelligence.compute_intelligence_scale(
            code_content,
            topological_time,
        )
        intelligence["file_path"] = file_path
        return intelligence

    def evolve(
        self,
        file_path: str,
        code_content: str,
        generations: int = 20,
        seed: int = 42,
        external_test_runner: Optional[Callable[[str], bool]] = None,
        topological_time: float = 0.0,
    ) -> Dict[str, Any]:
        """Run production evolutionary search with EUCLID co-gating and isolated validation."""
        self.engine.seed = seed
        result = self.engine.run_optimization(
            target_name=file_path,
            initial_code=code_content,
            max_generations=generations,
            external_test_runner=external_test_runner,
        )
        final_code = result["final_code"]
        initial_intel = self.euclid_intelligence.compute_intelligence_scale(
            code_content,
            topological_time,
        )
        final_intel = self.euclid_intelligence.compute_intelligence_scale(
            final_code,
            topological_time,
        )
        result["final_code_sample"] = final_code
        result["euclid_intelligence_telemetry"] = {
            "topological_time_t_p": topological_time,
            "initial_intelligence": initial_intel,
            "final_intelligence": final_intel,
            "intelligence_gain_ratio": round(
                final_intel["intelligence_score"]
                / max(initial_intel["intelligence_score"], 1e-12),
                6,
            ),
            "lucas_phase_transitions": result["lucas_phase_transitions"],
        }
        self._persist_adaptive_state()
        return result

    def _persist_adaptive_state(self) -> None:
        self.repository.save_adaptive_state(
            {
                "schema_version": 1,
                "surrogate": self.engine.surrogate.export_state(),
                "collective_geometry": self.engine.collective_geometry.to_dict(),
            }
        )

    def evaluate_candidate(
        self,
        code_content: str,
        external_test_runner: Optional[Callable[[str], bool]] = None,
    ) -> Dict[str, Any]:
        record = sandbox.validate(
            code_content,
            external_test_runner,
            self.engine.sandbox_config,
        )
        parse_valid = record["parse_valid"]
        phi_score = (
            self.engine.calculator.compute_phi(code_content)
            if parse_valid
            else 0.1000
        )
        intelligence = (
            self.euclid_intelligence.compute_intelligence_scale(code_content, 0.0)
            if parse_valid
            else {"intelligence_score": 0.0}
        )
        return {
            "parse_valid": parse_valid,
            "compile_valid": record["compile_valid"],
            "runtime_valid": record["runtime_valid"],
            "runtime_mode": record["runtime_mode"],
            "reason": record["reason"],
            "al_haras_audit": record["audit"],
            "phi_score": phi_score,
            "euclid_intelligence_score": intelligence["intelligence_score"],
        }

    def verify_property_invariants(
        self,
        original_code: str,
        mutated_code: str,
        topological_time: float = 1.0,
        external_test_runner: Optional[Callable[[str], bool]] = None,
    ) -> Dict[str, Any]:
        """Verify monotonicity, positivity, Lucas, syntax and optional behaviour gates."""
        phi_orig = self.engine.calculator.compute_phi(original_code)
        phi_mut = self.engine.calculator.compute_phi(mutated_code)
        intel_orig = self.euclid_intelligence.compute_intelligence_scale(
            original_code,
            topological_time,
        )
        intel_mut = self.euclid_intelligence.compute_intelligence_scale(
            mutated_code,
            topological_time,
        )
        record = sandbox.validate(mutated_code, None, self.engine.sandbox_config)

        monotonicity = (not phi_mut > phi_orig) or (
            intel_mut["intelligence_score"] >= intel_orig["intelligence_score"]
        )
        non_degeneracy = (
            intel_orig["intelligence_score"] > 0
            and intel_mut["intelligence_score"] > 0
        )

        calculator = LucasSequenceCalculator()
        n = intel_mut["lucas_index_discrete"]
        if n >= 2:
            lucas_ok = (
                calculator.exact_lucas(n)
                == calculator.exact_lucas(n - 1) + calculator.exact_lucas(n - 2)
                and calculator.exact_lucas(n) == round(PHI**n)
            )
        else:
            lucas_ok = True

        behaviour = None
        if external_test_runner is not None:
            try:
                behaviour = bool(external_test_runner(original_code)) and bool(
                    external_test_runner(mutated_code)
                )
            except Exception:
                behaviour = False

        syntax_ok = record["parse_valid"] and record["compile_valid"]
        all_pass = (
            monotonicity
            and non_degeneracy
            and lucas_ok
            and syntax_ok
            and behaviour is not False
        )
        return {
            "invariants_pass": all_pass,
            "monotonicity_invariant": monotonicity,
            "non_degeneracy_invariant": non_degeneracy,
            "lucas_recurrence_invariant": lucas_ok,
            "syntax_compilation_invariant": syntax_ok,
            "behaviour_preservation_invariant": behaviour,
            "behaviour_preservation_note": (
                None
                if behaviour is not None
                else "not verified: no host test runner supplied"
            ),
            "details": {
                "topological_time_t_p": topological_time,
                "phi_original": phi_orig,
                "phi_mutated": phi_mut,
                "intelligence_original": intel_orig["intelligence_score"],
                "intelligence_mutated": intel_mut["intelligence_score"],
            },
        }

    def commit_primitive(
        self,
        primitive_name: str,
        op_func_code_str: str,
        origin_target: str = "host_repo",
    ) -> None:
        """Register a host-defined primitive as a recipe over known operators."""
        recipe = [
            part.strip()
            for part in op_func_code_str.replace("|", "+").replace(",", "+").split("+")
            if part.strip()
        ]
        if not recipe:
            raise ValueError("primitive recipe is empty")
        op = compose(recipe, primitive_name)
        self.repository.register_promoted_primitive(
            primitive_name,
            op,
            origin_target,
            0.0,
        )
        self.engine.discovery_engine.promoted_vocabulary[primitive_name] = op

    def available_operators(self) -> List[str]:
        return sorted(OPERATOR_REGISTRY)

    def orchestrate(
        self,
        files: List[Dict[str, Any]],
        generations: int = 10,
        external_test_runner: Optional[Callable[[str], bool]] = None,
    ) -> Dict[str, Any]:
        from pythagoras.agents.orchestrator import MultiAgentEntangledOrchestrator

        orchestrator = MultiAgentEntangledOrchestrator(
            self.engine.calculator,
            self.manifold,
            self.engine,
        )
        result = orchestrator.run_multi_agent_cycle(
            files,
            generations,
            external_test_runner,
        )
        self._persist_adaptive_state()
        return result

    def snapshot(self) -> Dict[str, Any]:
        return {
            "manifold_snapshot": self.manifold.get_snapshot(),
            "repository_summary": self.repository.get_summary(),
            "adaptive_state": {
                "surrogate": self.engine.surrogate.export_state(),
                "collective_geometry": self.engine.collective_geometry.to_dict(),
            },
        }
