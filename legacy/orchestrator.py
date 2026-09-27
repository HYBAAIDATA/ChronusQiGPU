"""Mining orchestrator — the loop driver.

STATUS: Research/simulation driver — not the production miner.
The production mining path is the TypeScript server (server.ts +
src/lib/stratum_*): it owns the pool socket, the consensus check, and
share submission. This driver runs synthetic headers for experiments
and the mining battery only (experiments/live_mining_run.py,
tests/mining_battery.py) — it is never started in production.

This system mines and only mines. One cycle:

    SEARCHING -> SUBMITTING -> WAITING_EXTERNAL -> COOLDOWN -> SEARCHING

Per cycle the driver: predicts block context (TOE), builds an
intelligence-guided nonce schedule, evolves it (meta-evolution),
searches it (Grover-style + preimage consensus check), submits the
winner, waits for the external block, cools down, and consolidates the
outcome into germ-line memory. Winners feed learning; the Lucas ladder
climbs on coherence gain. ``theorem_proven`` stays ``False`` everywhere.

This is wiring-layer code: it may import subsystem modules. Subsystems
never import each other.
"""

# LUCAS WIRING: wiring layer — drives subsystems, does not serve one.
# Substrate route: step

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

import numpy as np

from Intelligence.orchestrator import IntelligenceOrchestrator
from Intelligence.registry import ModuleRegistry
from mining.difficulty import DifficultyController
from mining.nonce_scheduler import NonceScheduler
from mining.safety_fsm import SafetyFSM
from mining.search import GroverStyleSearch, MerklePathVerifier, PreimageSearch
from registry import build_mining_registry

logger = logging.getLogger("orchestrator")

THEOREM_PROVEN = False

NONCE_WINDOW = 1_000_000
SCHEDULE_CAP = 10_000
EVOLVE_GENERATIONS = 12


def _header(block_height: int) -> bytes:
    """Deterministic 80-byte block header for block N."""
    payload = f"euclid-core-live-run-{block_height}".encode()
    return hashlib.sha256(payload).digest()[:80].ljust(80, b"\x00")


class MiningOrchestrator:
    """Boots the real intelligence stack and drives the mining cycle."""

    def __init__(
        self,
        registry: Optional[ModuleRegistry] = None,
        store_dir: Optional[Any] = None,
    ) -> None:
        self.registry = registry or build_mining_registry()
        self.intelligence = IntelligenceOrchestrator(registry=self.registry, store_dir=store_dir)
        # Mining subsystems owned by the loop driver.
        self.fsm = SafetyFSM()
        self.scheduler = NonceScheduler(nonce_window=NONCE_WINDOW, cap=SCHEDULE_CAP)
        self.difficulty = DifficultyController()
        self.grover = GroverStyleSearch()
        self.merkle = MerklePathVerifier()
        self.preimage = PreimageSearch()
        # Folded-state interface — the canonical engine, exposed directly.
        self.folded = self.intelligence.folded
        self.cycles = 0
        self.winners = 0

    # -- folded-state passthrough -------------------------------------------

    def folded_store(self, payload: bytes, key: Optional[str] = None) -> Dict[str, Any]:
        return self.intelligence.folded_store(payload, key=key)

    def folded_query(self, key: str, op: str, **kwargs):
        return self.intelligence.folded_query(key, op, **kwargs)

    def folded_status(self) -> Dict[str, Any]:
        return self.intelligence.folded_status()

    # -- the mining cycle ------------------------------------------------------

    def note_block_accepted(self, block_height: int, block_hash: str) -> None:
        """Inject a real 'our block was accepted' observation.

        Acceptance is a network verdict — it must be supplied by an
        external observation, never self-generated inside a cycle.
        """
        self.fsm.on_block_accepted(block_height)
        self.intelligence.on_block_accepted(block_height, block_hash)

    def note_block_orphaned(self) -> None:
        """Inject a real 'our submitted block was orphaned' observation."""
        self.fsm.on_block_orphaned()
        self.intelligence.on_block_orphaned()

    def note_external_block(self, block_height: int) -> None:
        """Inject a real external-block observation.

        This is the event the never-two-consecutive rule waits for. It
        must come from the network (or an explicit test/experiment
        driver) — the cycle itself never fabricates it.
        """
        self.fsm.on_external_block(block_height)
        self.intelligence.on_external_block(block_height)
        self.fsm.cooldown_complete()

    def run_cycle(self, block_height: int) -> Dict[str, Any]:
        """Run one mining cycle.

        The cycle is admitted only if the never-two-consecutive rule
        holds; a blocked cycle does no hashing and reports
        ``fsm.admitted=False``. A found winner moves the FSM to
        SUBMITTING — acceptance and external-block events arrive only via
        ``note_block_accepted`` / ``note_external_block``.
        """
        orch = self.intelligence
        fsm_trace_start = len(self.fsm.history)

        # SEARCHING — admitted only if the never-two-consecutive rule holds.
        admitted = self.fsm.begin_search()
        if not admitted:
            return {
                "cycle": block_height,
                "theorem_proven": False,
                "blocked": True,
                "fsm": {
                    "admitted": False,
                    "state": self.fsm.state.value,
                    "states_visited": self.fsm.history[fsm_trace_start:],
                    "consecutive_blocks_prevented": self.fsm.consecutive_blocks_prevented,
                    "kernel": "step_kernel",
                    "theorem_proven": False,
                },
            }

        header = _header(block_height)
        target = self.difficulty.target_bytes()

        # 1. TOE — quantum-mathematical prediction of the block context.
        toe_data = {
            "block_height": [block_height],
            "header_entropy": [b / 255.0 for b in header[:32]],
        }
        try:
            toe_result = orch.toe_predict(toe_data)
            toe_live = bool(toe_result.get("available", False))
            toe_conf = float(toe_result.get("confidence", 0.0))
        except Exception as e:  # pragma: no cover - defensive
            toe_result = {"error": str(e)}
            toe_live, toe_conf = False, 0.0

        # 2. Intelligence-guided schedule (AGI + quantum_cuda + golden);
        #    the nonce scheduler is the deterministic fallback substrate
        #    and bounds whatever schedule is searched.
        block_context = {
            "block_height": block_height,
            "header_bytes": list(header[:16]),
            "difficulty": self.difficulty.difficulty(),
        }
        guidance = orch.guide_mining(
            header, target, nonce_window=NONCE_WINDOW, block_context=block_context
        )
        base_schedule = list(guidance.nonce_schedule) if guidance.nonce_schedule else []
        if not base_schedule:
            base_schedule = self.scheduler.schedule(header)
            guidance = type(guidance)(
                nonce_schedule=base_schedule,
                confidence=guidance.confidence,
                source="nonce_scheduler",
                diagnostics=guidance.diagnostics,
            )
        sched_kernel = self.scheduler.kernel_check(len(base_schedule))

        # 3. Meta-evolution — evolve the schedule toward coherence.
        evo = orch.meta_evolve_schedule(base_schedule, generations=EVOLVE_GENERATIONS)
        evolved_schedule = evo["best_schedule"]
        delta_phi = evo["delta_phi"]
        n_transitions = evo["phase_transitions"]

        # 4. Search — Grover-ordered probe, real double-SHA256 consensus.
        search = self.grover.search(header, evolved_schedule, target)
        winner = search["winner_nonce"]
        mining_success = search["mining_success"]

        # SUBMITTING — only self-observable events fire here. Acceptance
        # is a network verdict and the external-block observation is a
        # network event: both arrive via note_block_accepted /
        # note_external_block, never fabricated by the cycle.
        if mining_success:
            self.winners += 1
            self.fsm.on_winner_found()
            orch.on_winner_found()
            orch.on_block_submitted()
            # The winning block is held in superposition as a folded artifact.
            orch.hold_in_superposition(header, winner, True)
            orch.counterfactual_analyze(
                {
                    "block_height": block_height,
                    "winner_nonce": winner,
                    "delta_phi": delta_phi,
                }
            )

        # 5. Pythia learning — germ-line consolidation of the outcome.
        pattern = _pattern_from_schedule(evolved_schedule)
        reps = 4 if mining_success else 1
        orch.teach([pattern] * reps, [mining_success] * reps)

        # 6. Memory — full begin -> execute -> consolidate cycle.
        orch.begin_memory_task(f"Mining cycle {block_height}: evolve, verify, learn")
        orch.memory.execute_step(
            "meta_evolve",
            {"delta_phi": delta_phi, "transitions": n_transitions},
            "Evolved",
            {"mining_success": mining_success, "winner": winner},
        )
        orch.memory.reflect_before_action({"action": "commit_learning"})
        orch.consolidate_memory_task(
            trigger=f"Mining cycle {block_height}",
            plan=["toe_predict", "guide_mining", "meta_evolve", "verify", "learn"],
            tool_calls=[{"tool": "meta_evolve"}, {"tool": "verify"}],
            outcome={
                "expected": "winner" if mining_success else "no_winner",
                "actual": "winner" if mining_success else "no_winner",
                "winner_nonce": winner,
            },
            reward=1.0 if mining_success else 0.0,
            error_state=not mining_success,
            unexpected=False,
        )

        # 7. Lucas scale — advance when the cycle improved coherence.
        orch.lucas_scale_status()
        if delta_phi > 0.01:
            orch.advance_lucas_scale()
        scale_after = orch.lucas_scale_status()

        # 8. Difficulty — per-block adjustment.
        difficulty_adj = self.difficulty.update(mining_success)
        self.cycles += 1

        # Snapshot every subsystem's live state.
        pythia_status = orch.pythia_status()
        mem_status = orch.memory_status()
        meta_status = orch.meta_evolution_status()
        safety_status = orch.safety_status()

        return {
            "cycle": block_height,
            "theorem_proven": False,
            "fsm": {
                "admitted": admitted,
                "state": self.fsm.state.value,
                "states_visited": self.fsm.history[fsm_trace_start:],
                "consecutive_blocks_prevented": self.fsm.consecutive_blocks_prevented,
                "kernel": "step_kernel",
                "theorem_proven": False,
            },
            "toe": {
                "live": toe_live,
                "confidence": toe_conf,
                "trend": (
                    toe_result.get("trajectory_prediction", {}).get("trend", "n/a")
                    if isinstance(toe_result, dict)
                    else "n/a"
                ),
                "kernel": "gap_kernel",
                "theorem_proven": False,
            },
            "mining": {
                "source": guidance.source,
                "base_schedule_len": len(base_schedule),
                "evolved_schedule_len": len(evolved_schedule),
                "scheduler_bound": sched_kernel["bound"],
                "scheduler_is_lucas_bounded": sched_kernel["is_lucas_bounded"],
                "base_coherence": evo.get("base_coherence", 0.0),
                "best_coherence": evo.get("best_coherence", 0.0),
                "delta_phi": delta_phi,
                "phase_transitions": n_transitions,
                "grover_k_star": search["grover_k_star"],
                "winner_nonce": winner,
                "mining_success": mining_success,
                "theorem_proven": False,
            },
            "meta_evolution": {
                "step": meta_status["step"],
                "n_primitives": meta_status["n_primitives"],
                "n_discovered": meta_status["discovery"]["n_discovered"],
                "surrogate_rmse": meta_status["surrogate"]["rmse"],
                "surrogate_trustworthy": meta_status["surrogate"]["trustworthy"],
                "mutation_rate": meta_status["mutation_rate"],
                "geometry_lucas_index": meta_status["geometry"]["lucas_index"],
                "geometry_breadth": meta_status["geometry"]["search_breadth"],
                "kernel": "gap_kernel",
                "theorem_proven": False,
            },
            "pythia_learning": {
                "germ_line": pythia_status.get("germ_line", 0),
                "somatic": pythia_status.get("somatic", 0),
                "emergence_signal": pythia_status.get("emergence_signal", 0.0),
                "pythia_active": pythia_status.get("pythia_active", False),
                "n_consolidated": pythia_status.get("n_consolidated", 0),
                "kernel": "trace_kernel",
                "theorem_proven": False,
            },
            "memory": {
                "episodic_events": mem_status["episodic_memory"]["n_events"],
                "semantic_concepts": mem_status["semantic_memory"]["n_concepts"],
                "archival_entries": mem_status["archival_memory"]["n_entries"],
                "curriculum_tasks_completed": mem_status["curriculum"]["tasks_completed"],
                "socratic_heuristics": len(mem_status["socratic_heuristics"]),
                "reflection_avg_confidence": mem_status["reflection"]["avg_confidence"],
                "pythia_active": mem_status["pythia_active"],
                "kernel": "trace_kernel",
                "theorem_proven": False,
            },
            "safety": {
                "state": safety_status.get("state", "unknown"),
                "mining_allowed": safety_status.get("mining_allowed", False),
                "last_mined_block_height": safety_status.get("last_mined_block_height"),
                "cooldown_active": safety_status.get("cooldown_active", False),
                "consecutive_block_attempts": safety_status.get("consecutive_block_attempts", 0),
                "kernel": "gap_kernel",
                "theorem_proven": False,
            },
            "difficulty": {
                "zero_bits": difficulty_adj["zero_bits_after"],
                "difficulty": difficulty_adj["difficulty"],
                "kernel": "mining_kernel",
                "theorem_proven": False,
            },
            "folded": {
                "artifacts": self.folded_status()["artifacts"],
                "queries": self.folded_status()["queries_executed"],
                "raw_materializations": self.folded_status()["raw_materializations"],
                "kernel": "folded_kernel",
                "theorem_proven": False,
            },
            "lucas_scale": scale_after,
        }


def _pattern_from_schedule(schedule: List[int], n_units: int = 32) -> np.ndarray:
    """Encode a schedule as a Pythia-learning pattern (length-n_units vector)."""
    if not schedule:
        return np.zeros(n_units, dtype=float)
    gaps = [
        (int(schedule[i + 1]) - int(schedule[i])) % 1_000_000
        for i in range(min(len(schedule) - 1, n_units))
    ]
    while len(gaps) < n_units:
        gaps.append(0)
    arr = np.array(gaps[:n_units], dtype=float)
    mx = float(arr.max()) if arr.max() > 0 else 1.0
    return arr / mx


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool."""
    from lucas.pool import get as _lucas_get

    result = _lucas_get("step_kernel")({"states": 4}, n)
    result["module"] = __name__
    return result
