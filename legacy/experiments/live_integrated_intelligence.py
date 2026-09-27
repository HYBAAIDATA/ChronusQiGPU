"""Live integrated intelligence run — evidence of cross-scale coupling.

This is the elevated version: not four siloed subsystems running in
parallel, but ONE integrated intelligence where TOE feeds meta-
evolution, meta-evolution's discoveries feed memory, memory's
curriculum gates TOE's capabilities, and Pythia learning biases the
search — all tracked by a metacognitive self-model that calibrates
the system's confidence against reality (Brier score).

The evidence this produces:
- Does TOE confidence shape the meta-evolution mutation rate? (Wire #1)
- Do discovered primitives appear in semantic memory? (Wire #2)
- Does the curriculum gate which capabilities fire? (Wire #3)
- Do germ-line memories bias primitive weights? (Wire #4)
- Does the emergence signal calibrate TOE confidence? (Wire #5)
- Do phase transitions feed back as learning rewards? (Wire #6)
- Does the Brier score track calibration honestly? (Metacognition)
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(_PROJECT_ROOT))

from Intelligence.orchestrator import IntelligenceOrchestrator
from Intelligence.registry import build_default_registry
from Intelligence.intelligence_integration import IntegratedIntelligence

SEED = 1726401000
random.seed(SEED)
np.random.seed(SEED)


def _header(block_height: int) -> bytes:
    payload = f"euclid-core-integrated-{block_height}".encode()
    return hashlib.sha256(payload).digest()[:80].ljust(80, b"\x00")


def _target(difficulty: int = 0) -> bytes:
    return (b"\x00" * difficulty) + (b"\xff" * (32 - difficulty))


def _verify_winner(schedule: List[int], header: bytes, target: bytes) -> int:
    for nonce in schedule:
        n = int(nonce) & 0xFFFFFFFF
        blob = header + n.to_bytes(4, "little")
        h = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
        if h < target:
            return n
    return -1


def _pattern_from_schedule(schedule: List[int], n_units: int = 32) -> np.ndarray:
    if not schedule:
        return np.zeros(n_units, dtype=float)
    sched_i = [int(s) for s in schedule]
    gaps = [
        (sched_i[i + 1] - sched_i[i]) % 1_000_000 for i in range(min(len(sched_i) - 1, n_units))
    ]
    while len(gaps) < n_units:
        gaps.append(0)
    arr = np.array(gaps[:n_units], dtype=float)
    mx = float(arr.max()) if arr.max() > 0 else 1.0
    return arr / mx


def run_integrated_session(n_cycles: int = 12, out_path: Path | None = None) -> Dict[str, Any]:
    registry = build_default_registry()
    orch = IntelligenceOrchestrator(registry=registry)
    integ = IntegratedIntelligence(orch)

    transcript: List[Dict[str, Any]] = []
    semantic_before = orch.memory_status()["semantic_memory"]["n_concepts"]

    for cycle in range(1, n_cycles + 1):
        header = _header(cycle)
        target = _target(difficulty=0)
        block_context = {
            "block_height": cycle,
            "header_bytes": list(header[:16]),
            "difficulty": 0,
        }

        # Run one integrated cycle — all six wires fire inside this.
        result = integ.run_cycle(header, target, block_context, mining_success=False)

        # Mining: verify the evolved schedule.
        guidance = orch.guide_mining(
            header, target, nonce_window=10_000, block_context=block_context
        )
        schedule = list(guidance.nonce_schedule) if guidance.nonce_schedule else []
        if schedule:
            evo = orch.meta_evolve_schedule(schedule, generations=8)
            evolved = evo["best_schedule"]
        else:
            evolved = []
        winner = _verify_winner(evolved, header, target)
        mining_success = winner >= 0

        # Safety FSM.
        if mining_success:
            orch.on_winner_found()
            orch.on_block_submitted()
            if cycle % 3 == 1:
                orch.on_block_accepted(cycle, "0" * 64)
                orch.on_external_block(cycle)
            else:
                orch.on_block_orphaned()
                orch.on_external_block(cycle)
        else:
            orch.on_external_block(cycle)

        # Pythia learning from the outcome.
        pattern = _pattern_from_schedule(evolved)
        reps = 4 if mining_success else 1
        orch.teach([pattern] * reps, [mining_success] * reps)

        # Memory consolidation.
        orch.begin_memory_task(f"Integrated cycle {cycle}")
        orch.memory.execute_step(
            "integrated_evolve",
            {"delta_phi": result.meta_delta_phi, "winner": winner},
            "Done",
            {"mining_success": mining_success},
        )
        orch.consolidate_memory_task(
            trigger=f"Integrated cycle {cycle}",
            plan=["toe", "guide_mining", "meta_evolve", "verify", "learn"],
            tool_calls=[{"tool": "integrated_cycle"}],
            outcome={"expected": "winner", "actual": "winner" if mining_success else "none"},
            reward=1.0 if mining_success else 0.0,
            error_state=not mining_success,
        )

        # Re-run the integration with the updated mining outcome so the
        # self-model records the actual result against the predictions.
        result = integ.run_cycle(header, target, block_context, mining_success=mining_success)

        semantic_after = orch.memory_status()["semantic_memory"]["n_concepts"]

        entry = {
            "cycle": cycle,
            "toe_raw": round(result.toe_confidence_raw, 4),
            "toe_calibrated": round(result.toe_confidence_calibrated, 4),
            "global_calibrated": round(result.global_calibrated_confidence, 4),
            "subsystem_weights": {k: round(v, 4) for k, v in result.subsystem_weights.items()},
            "brier_scores": {k: round(v, 4) for k, v in result.brier_scores.items()},
            "pythia_emergence": round(result.pythia_emergence_signal, 4),
            "germ_line": result.germ_line_count,
            "meta_delta_phi": round(result.meta_delta_phi, 4),
            "phase_transition": result.meta_phase_transition,
            "discovered_primitive": result.meta_discovered_primitive,
            "curriculum_capabilities": result.curriculum_capabilities,
            "semantic_concepts": semantic_after,
            "new_concepts_this_cycle": semantic_after - semantic_before,
            "mining_success": mining_success,
            "winner_nonce": winner,
        }
        transcript.append(entry)
        semantic_before = semantic_after

        marker = "WON" if mining_success else "miss"
        prim = result.meta_discovered_primitive or "-"
        print(
            f"  cycle {cycle:2d}: TOE={result.toe_confidence_raw:.2f}->{result.toe_confidence_calibrated:.2f} "
            f"global={result.global_calibrated_confidence:.2f} "
            f"emergence={result.pythia_emergence_signal:.2f} "
            f"germ={result.germ_line_count} "
            f"dphi={result.meta_delta_phi:+.3f} "
            f"caps={len(result.curriculum_capabilities)} "
            f"semantic={semantic_after} "
            f"brier_toe={result.brier_scores.get('toe', 0):.3f} "
            f"[{marker}] prim={prim[:20]}"
        )

    # Aggregate evidence of coupling.
    first = transcript[0]
    last = transcript[-1]
    summary = {
        "n_cycles": len(transcript),
        "transcript": transcript,
        "coupling_evidence": {
            "wire1_toe_to_meta": {
                "description": "TOE confidence shapes meta-evolution mutation rate",
                "toe_confidence_first_to_last": [first["toe_raw"], last["toe_raw"]],
                "meta_mutation_rate": orch.meta_evolution_status()["mutation_rate"],
            },
            "wire2_meta_to_memory": {
                "description": "Discovered primitives written to semantic memory",
                "semantic_concepts_first_to_last": [
                    first["semantic_concepts"],
                    last["semantic_concepts"],
                ],
                "n_primitives_discovered": sum(
                    1 for t in transcript if t["discovered_primitive"] is not None
                ),
                "new_concepts_total": last["new_concepts_this_cycle"],
            },
            "wire3_memory_to_toe": {
                "description": "Curriculum gates TOE capabilities",
                "capabilities_first": first["curriculum_capabilities"],
                "capabilities_last": last["curriculum_capabilities"],
            },
            "wire4_pythia_to_meta": {
                "description": "Germ-line memories bias primitive weights",
                "germ_line_first_to_last": [first["germ_line"], last["germ_line"]],
                "n_primitives": orch.meta_evolution_status()["n_primitives"],
            },
            "wire5_pythia_to_toe": {
                "description": "Emergence signal calibrates TOE confidence",
                "toe_raw_vs_calibrated_last": [last["toe_raw"], last["toe_calibrated"]],
                "emergence_last": last["pythia_emergence"],
            },
            "wire6_meta_to_pythia": {
                "description": "Phase transitions feed back as learning rewards",
                "total_phase_transitions": sum(1 for t in transcript if t["phase_transition"]),
            },
            "metacognition": {
                "description": "Brier-score self-model tracks calibration",
                "brier_scores_final": last["brier_scores"],
                "subsystem_weights_final": last["subsystem_weights"],
                "global_calibrated_first_to_last": [
                    first["global_calibrated"],
                    last["global_calibrated"],
                ],
            },
        },
    }

    if out_path is not None:
        out_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def main() -> int:
    out_path = Path(__file__).resolve().parent / "live_integrated_intelligence_results.json"
    print("=" * 80)
    print("EUCLID-CORE LIVE INTEGRATED INTELLIGENCE RUN")
    print("Six cross-scale wires + metacognitive self-model. Not siloed. Not a gate.")
    print("=" * 80)
    print()
    summary = run_integrated_session(n_cycles=12, out_path=out_path)

    print()
    print("=" * 80)
    print("CROSS-SCALE COUPLING EVIDENCE")
    print("=" * 80)
    ce = summary["coupling_evidence"]
    for key, val in ce.items():
        print(f"\n  {key}: {val['description']}")
        for k, v in val.items():
            if k == "description":
                continue
            print(f"    {k}: {v}")

    print()
    print("=" * 80)
    print("EVIDENCE WRITTEN TO", out_path)
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
