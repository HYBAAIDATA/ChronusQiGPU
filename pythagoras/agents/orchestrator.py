"""
PYTHAGORAS Multi-Agent Orchestrator
===================================
Every payload is produced by the agent's own computation:
  EUCLID      — structural directive: measured hotspots (unannotated sites, redundancy,
                deepest function, contradictory annotations) and Lucas telemetry
  AL HARAS    — static security audit (core.sandbox.al_haras_audit)
  SALAMANDER  — runs the V6.5 engine (including HEAL:dead_code_elimination) on the file
  PYTHIA      — the surrogate's operator ranking for the next search, with its RMSE
"""
import ast
from typing import Any, Callable, Dict, List, Optional

from pythagoras.agents.manifold import AgentID, PayloadType, SharedEntangledManifold
from pythagoras.core.euclid_intelligence import EuclidIntelligenceEngine
from pythagoras.core.phi_metric import PhiResonanceCalculator
from pythagoras.core.sandbox import al_haras_audit
from pythagoras.core.state import measure_state
from pythagoras.core.structure import analyze_structure, ast_depth


def _hotspots(code_str: str) -> List[Dict[str, Any]]:
    report = analyze_structure(code_str)
    if not report.parse_ok:
        return [{"kind": "parse_error"}]
    spots = []
    if report.redundancy:
        spots.append({"kind": "redundancy", "nodes": report.redundant_nodes, "breakdown": report.redundancy})
    if report.contradictory_annotations:
        spots.append({"kind": "contradictory_annotations", "count": report.contradictory_annotations})
    unannotated = report.annotation_sites - report.coherent_annotations - report.contradictory_annotations
    if unannotated > 0:
        spots.append({"kind": "unannotated_sites", "count": unannotated})
    funcs = [n for n in ast.walk(report.effective_tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if funcs:
        deepest = max(funcs, key=lambda f: ast_depth(f))
        spots.append({"kind": "deepest_function", "name": deepest.name, "depth": ast_depth(deepest),
                      "statements": len(deepest.body)})
    return spots


class MultiAgentEntangledOrchestrator:
    def __init__(self, calculator: Optional[PhiResonanceCalculator] = None,
                 manifold: Optional[SharedEntangledManifold] = None, engine=None):
        from pythagoras.engine.v6_5_manifold_escape import V65ManifoldEscapeEngine
        self.manifold = manifold or SharedEntangledManifold()
        self.calculator = calculator or PhiResonanceCalculator()
        self.engine = engine or V65ManifoldEscapeEngine(target_phi=self.calculator.target_phi)
        self.euclid = EuclidIntelligenceEngine()

    def run_multi_agent_cycle(self, codebase_files: List[Dict[str, Any]], generations: int = 10,
                              external_test_runner: Optional[Callable[[str], bool]] = None) -> Dict[str, Any]:
        session_results = {}
        for file_info in codebase_files:
            fname = file_info["name"]
            code = file_info["code_str"]
            initial_phi = self.calculator.compute_phi(code)
            initial_state = measure_state(code, self.calculator, self.euclid)

            self.manifold.broadcast(AgentID.EUCLID, PayloadType.DIRECTIVE, {
                "target_file": fname, "initial_phi": initial_phi, "state_11d": initial_state["vector"],
                "structural_hotspots": _hotspots(code),
                "intelligence": self.euclid.compute_intelligence_scale(code, 0.0),
            })

            audit = al_haras_audit(code)
            self.manifold.broadcast(AgentID.AL_HARAS, PayloadType.SECURITY_AUDIT, {
                "target_file": fname, "state_11d": initial_state["vector"], **audit.to_dict()})

            if not audit.approved:
                result = None
                final_code, final_phi = code, initial_phi
            else:
                result = self.engine.run_optimization(fname, code, generations, external_test_runner)
                final_code, final_phi = result["final_code"], result["final_phi"]
            final_state = measure_state(final_code, self.calculator, self.euclid)

            self.manifold.broadcast(AgentID.SALAMANDER, PayloadType.OPTIMIZATION, {
                "target_file": fname, "original_phi": initial_phi, "optimized_phi": final_phi,
                "delta_phi": round(final_phi - initial_phi, 6), "state_11d": final_state["vector"],
                "applied_primitives": [s["winning_operator"] for s in result["accepted_steps"]] if result else [],
                "skipped_reason": None if result else "blocked by AL HARAS import-time findings",
            })

            features = self.calculator.extract_features(final_code)
            active = {n for n, _ in self.engine._active_operators(external_test_runner is not None)}
            ranking = sorted(((self.engine.surrogate.predict_gain(features, n), n)
                              for n in active if not self.engine.surrogate.is_anti_primitive(n)), reverse=True)
            self.manifold.broadcast(AgentID.PYTHIA, PayloadType.SEARCH_STRATEGY, {
                "search_space_id": fname, "state_11d": final_state["vector"],
                "next_operator_ranking": [{"operator": n, "predicted_gain": g} for g, n in ranking[:5]],
                "surrogate_rmse": self.engine.surrogate.compute_rmse(),
            })

            session_results[fname] = {
                "file": fname,
                "measured_initial_phi": initial_phi,
                "measured_final_phi": final_phi,
                "total_delta_phi": round(final_phi - initial_phi, 6),
                "accepted_steps": len(result["accepted_steps"]) if result else 0,
                "final_code": final_code,
                "11d_state": final_state["axes"],
            }

        return {"session_results": session_results, "manifold_snapshot": self.manifold.get_snapshot()}
