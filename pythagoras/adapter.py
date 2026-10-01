"""PYTHAGORAS v12 integration façade for PYTHIPhiMiner.

The v12 API is backed by the repository's current PYTHAGORAS engine. EUCLID
owns Intelligence evaluation; Salamander remains responsible for verified
publication of evolved source into the working repository.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from .agents.manifold import AgentID, PayloadType, SharedEntangledManifold
from .core.euclid_intelligence import EuclidIntelligenceEngine, LucasSequenceCalculator
from .core.phi_metric import PhiResonanceCalculator as V12PhiResonanceCalculator
from .core.primitives import ASTPrimitives
from .orchestrator import Pythagoras
from .verification import CandidateTestRunner, evaluate_candidate


class PythagorasEngineAdapter:
    """Stable host-facing façade for the complete v12 drop-in contract."""

    def __init__(
        self,
        target_phi: float = 0.618033988749895,
        persistent_repo_path: Optional[str] = None,
        condition: str = "B",
        domain: Any = "code",
        manifold: Optional[SharedEntangledManifold] = None,
    ) -> None:
        self.engine = Pythagoras(condition=condition, domain=domain)
        self.calculator = V12PhiResonanceCalculator(target_phi=target_phi)
        self.euclid_intelligence = EuclidIntelligenceEngine(pisot_base=20.0)
        self.manifold = manifold or SharedEntangledManifold()
        self.persistent_repo_path = (
            Path(persistent_repo_path).expanduser() if persistent_repo_path else None
        )
        if self.persistent_repo_path and self.persistent_repo_path.exists():
            self.engine.load_session(self.persistent_repo_path)

    def _persist(self) -> None:
        if self.persistent_repo_path is not None:
            self.engine.save_session(self.persistent_repo_path)

    def analyze(
        self,
        file_path: str,
        code_content: str,
        topological_time: float = 0.0,
    ) -> Dict[str, Any]:
        phi_score = self.calculator.compute_phi(code_content)
        features = self.calculator.extract_features(code_content)
        intelligence = self.euclid_intelligence.compute_intelligence_scale(
            code_content,
            topological_time,
        )
        substrate_phi = float(self.engine.domain.coherence(code_content))
        projection = self.manifold.overlay_11d.project_11d_coordinates(
            AgentID.EUCLID.value,
            phi_score,
        )
        self.manifold.broadcast(
            AgentID.EUCLID,
            PayloadType.DIRECTIVE,
            {
                "target_file": file_path,
                "initial_phi": phi_score,
                "substrate_phi": substrate_phi,
                "euclid_intelligence_score": intelligence["intelligence_score"],
                "parse_valid": features["parse_valid"],
            },
        )
        return {
            "file_path": file_path,
            "domain": self.engine.domain.name,
            "phi_score": phi_score,
            "substrate_phi_score": substrate_phi,
            "euclid_intelligence": intelligence,
            "ast_features": features,
            "11d_projection": projection,
        }

    def analyze_intelligence(
        self,
        file_path: str,
        code_content: str,
        topological_time: float = 0.0,
    ) -> Dict[str, Any]:
        result = self.euclid_intelligence.compute_intelligence_scale(
            code_content,
            topological_time,
        )
        result["file_path"] = file_path
        return result

    def evolve(
        self,
        file_path: str,
        code_content: str,
        generations: int = 20,
        seed: int = 42,
        external_test_runner: Optional[CandidateTestRunner] = None,
    ) -> Dict[str, Any]:
        """Evolve a candidate without writing ``file_path``."""
        if generations < 0:
            raise ValueError("generations must be non-negative")

        np.random.seed(int(seed))
        started = time.perf_counter()
        initial_metric = self.calculator.compute_phi(code_content)
        initial_intel = self.euclid_intelligence.compute_intelligence_scale(code_content, 0.0)
        result = self.engine.evolve_file(
            code_content,
            generations=generations,
            filename=file_path,
        )
        final_source = str(result.get("final_source", code_content))
        gate = self.evaluate_candidate(final_source, external_test_runner)
        final_metric = self.calculator.compute_phi(final_source)
        topological_time = float(max(0, len(result.get("fitness_history", [])) - 1))
        final_intel = self.euclid_intelligence.compute_intelligence_scale(
            final_source,
            topological_time,
        )
        history = [float(value) for value in result.get("fitness_history", [])]
        accepted_steps = sum(
            current > previous for previous, current in zip(history, history[1:])
        )

        result.update(
            {
                "engine": "PYTHAGORAS_CURRENT_META_EVOLUTION",
                "target": file_path,
                "seed": int(seed),
                "final_code": final_source,
                "final_code_sample": final_source,
                "accepted_steps_count": accepted_steps,
                "wall_time_ms": round((time.perf_counter() - started) * 1000.0, 3),
                "candidate_gate": gate,
                "candidate_accepted": bool(
                    gate["parse_valid"]
                    and gate["compile_valid"]
                    and gate["runtime_valid"] is not False
                ),
                "v12_phi_metric": {
                    "initial_phi": initial_metric,
                    "final_phi": final_metric,
                    "delta_phi": round(final_metric - initial_metric, 6),
                },
                "euclid_intelligence_telemetry": {
                    "owner": "EUCLID_REPO_INTELLIGENCE",
                    "initial_intelligence": initial_intel,
                    "final_intelligence": final_intel,
                    "intelligence_gain_ratio": round(
                        final_intel["intelligence_score"]
                        / max(initial_intel["intelligence_score"], 1e-12),
                        6,
                    ),
                    "topological_time_source": "pythagoras_generation_history",
                },
            }
        )
        self._persist()
        return result

    def evaluate_candidate(
        self,
        code_content: str,
        external_test_runner: Optional[CandidateTestRunner] = None,
    ) -> Dict[str, Any]:
        return dict(
            evaluate_candidate(
                code_content,
                self.calculator,
                self.euclid_intelligence,
                external_test_runner,
            )
        )

    def verify_property_invariants(
        self,
        original_code: str,
        mutated_code: str,
        topological_time: float = 1.0,
        external_test_runner: Optional[CandidateTestRunner] = None,
    ) -> Dict[str, Any]:
        phi_original = self.calculator.compute_phi(original_code)
        phi_mutated = self.calculator.compute_phi(mutated_code)
        intel_original = self.euclid_intelligence.compute_intelligence_scale(
            original_code,
            topological_time,
        )
        intel_mutated = self.euclid_intelligence.compute_intelligence_scale(
            mutated_code,
            topological_time,
        )
        gate = self.evaluate_candidate(mutated_code, external_test_runner)
        monotonicity = bool(
            phi_mutated <= phi_original
            or intel_mutated["intelligence_score"] >= intel_original["intelligence_score"]
        )
        non_degeneracy = bool(
            intel_original["intelligence_score"] >= 2.0
            and intel_mutated["intelligence_score"] >= 2.0
        )
        n = int(intel_mutated["lucas_index_discrete"])
        lucas = LucasSequenceCalculator()
        recurrence = bool(
            n < 2
            or lucas.exact_lucas(n)
            == lucas.exact_lucas(n - 1) + lucas.exact_lucas(n - 2)
        )
        syntax_compilation = bool(gate["parse_valid"] and gate["compile_valid"])
        runtime = gate["runtime_valid"] is not False
        return {
            "invariants_pass": bool(
                monotonicity and non_degeneracy and recurrence and syntax_compilation and runtime
            ),
            "monotonicity_invariant": monotonicity,
            "non_degeneracy_invariant": non_degeneracy,
            "lucas_recurrence_invariant": recurrence,
            "syntax_compilation_invariant": syntax_compilation,
            "runtime_invariant": gate["runtime_valid"],
            "runtime_gate": gate["runtime_gate"],
            "details": {
                "phi_original": phi_original,
                "phi_mutated": phi_mutated,
                "intelligence_original": intel_original["intelligence_score"],
                "intelligence_mutated": intel_mutated["intelligence_score"],
            },
        }

    def commit_primitive(
        self,
        primitive_name: str,
        op_func_code_str: str,
        origin_target: str = "host_repo",
    ) -> Dict[str, Any]:
        """Persist primitive provenance and activate a shipped operator by name."""
        if not primitive_name:
            raise ValueError("primitive_name must not be empty")
        shipped = dict(ASTPrimitives.get_all_operators())
        active = primitive_name in shipped
        if active:
            operation = shipped[primitive_name]

            def bound(source: str, op: Any = operation) -> str:
                return op(source, 42)[0]

            self.engine.mutator.primitives[primitive_name] = bound

        record = {
            "name": primitive_name,
            "origin_target": origin_target,
            "weight": float(self.engine.mutator.weights.get(primitive_name, 0.1)),
            "active": active,
            "source_sha256": hashlib.sha256(op_func_code_str.encode("utf-8")).hexdigest(),
        }
        self.engine.discovery.discovered[primitive_name] = dict(record)
        self.engine.mutator.weights.setdefault(primitive_name, record["weight"])
        self._persist()
        return record

    def snapshot(self) -> Dict[str, Any]:
        primitives = dict(self.engine.discovery.get_discovered())
        return {
            "manifold_snapshot": self.manifold.get_snapshot(),
            "repository_summary": {
                "persistent_session": (
                    str(self.persistent_repo_path) if self.persistent_repo_path else None
                ),
                "primitives_detail": primitives,
                "discovered_primitives_count": len(primitives),
                "active_operator_weights": dict(self.engine.mutator.weights),
                "phase_transitions": list(self.engine.meta.phase_transitions),
            },
        }
