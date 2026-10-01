"""PYTHAGORAS v12 measured multi-agent orchestration.

EUCLID evaluates Intelligence, PYTHAGORAS evolves candidates, SALAMANDER owns
optimization/healing publication, AL HARAS receives the candidate validity
gate, and PYTHIA receives the measured search-state record.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pythagoras.adapter import CandidateTestRunner, PythagorasEngineAdapter
from pythagoras.agents.manifold import AgentID, PayloadType, SharedEntangledManifold


class MultiAgentEntangledOrchestrator:
    """Coordinate one measured v12 evolution cycle across the four agents."""

    def __init__(
        self,
        adapter: Optional[PythagorasEngineAdapter] = None,
        persistent_repo_path: Optional[str] = None,
    ) -> None:
        self.manifold = SharedEntangledManifold()
        self.adapter = adapter or PythagorasEngineAdapter(
            persistent_repo_path=persistent_repo_path,
            manifold=self.manifold,
        )
        self.adapter.manifold = self.manifold

    def run_multi_agent_cycle(
        self,
        codebase_files: List[Dict[str, Any]],
        generations: int = 5,
        seed: int = 42,
        external_test_runner: Optional[CandidateTestRunner] = None,
    ) -> Dict[str, Any]:
        """Analyze and evolve each supplied file without writing the repository."""
        session_results: Dict[str, Any] = {}

        for index, file_info in enumerate(codebase_files):
            name = str(file_info["name"])
            code_content = str(file_info["code_str"])
            analysis = self.adapter.analyze(name, code_content, topological_time=0.0)

            evolution = self.adapter.evolve(
                name,
                code_content,
                generations=generations,
                seed=seed + index,
                external_test_runner=external_test_runner,
            )
            final_code = str(evolution.get("final_code", code_content))
            gate = dict(evolution["candidate_gate"])
            failed_gates = [
                gate_name
                for gate_name in ("parse_valid", "compile_valid", "runtime_valid")
                if gate.get(gate_name) is False
            ]
            checked_gates = 2 + int(gate.get("runtime_valid") is not None)

            self.manifold.broadcast(
                AgentID.AL_HARAS,
                PayloadType.SECURITY_AUDIT,
                {
                    "target_file": name,
                    "initial_phi": analysis["phi_score"],
                    "ast_mutation_approved": not failed_gates,
                    "validity_gates_checked": checked_gates,
                    "security_violations": failed_gates,
                    "runtime_gate": gate["runtime_gate"],
                },
            )

            substrate_initial = float(evolution.get("initial_phi", 0.0))
            substrate_final = float(evolution.get("final_phi", substrate_initial))
            discovered = evolution.get("discovered_primitives", {})
            self.manifold.broadcast(
                AgentID.SALAMANDER,
                PayloadType.OPTIMIZATION,
                {
                    "target_file": name,
                    "original_phi": substrate_initial,
                    "optimized_phi": substrate_final,
                    "delta_phi": round(substrate_final - substrate_initial, 6),
                    "applied_primitives": sorted(discovered),
                    "candidate_accepted": evolution["candidate_accepted"],
                },
            )

            self.manifold.broadcast(
                AgentID.PYTHIA,
                PayloadType.SEARCH_STRATEGY,
                {
                    "target_file": name,
                    "initial_phi": substrate_initial,
                    "search_space_id": name,
                    "condition": evolution.get("condition"),
                    "geometry_state": evolution.get("geometry_state", {}),
                    "phase_transitions": evolution.get("phase_transitions", []),
                },
            )

            final_analysis = self.adapter.analyze(
                name,
                final_code,
                topological_time=float(max(0, generations)),
            )
            session_results[name] = {
                "file": name,
                "measured_initial_phi": analysis["phi_score"],
                "measured_final_phi": final_analysis["phi_score"],
                "total_delta_phi": round(
                    final_analysis["phi_score"] - analysis["phi_score"],
                    6,
                ),
                "substrate_initial_phi": substrate_initial,
                "substrate_final_phi": substrate_final,
                "candidate_gate": gate,
                "candidate_accepted": evolution["candidate_accepted"],
                "euclid_intelligence_telemetry": evolution[
                    "euclid_intelligence_telemetry"
                ],
                "11d_projection": self.manifold.agent_11d_states.get(
                    AgentID.SALAMANDER.value,
                    [],
                ),
                "final_code": final_code,
            }

        return {
            "session_results": session_results,
            "manifold_snapshot": self.manifold.get_snapshot(),
        }
