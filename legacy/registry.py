"""Mining subsystem registry — the single source of truth for what the
mining loop wires in.

Only subsystems that serve the mining cycle are registered here:
schedule building, search, learning, memory, folded state, safety.
Each entry names its Lucas kernel route (see ``lucas/routing.md``).

This is wiring-layer code: it may import subsystem modules. Subsystems
themselves never import each other.
"""

# LUCAS WIRING: wiring layer — registers subsystems, does not serve one.
# Substrate route: step

from __future__ import annotations

import importlib
from typing import Any, Dict, List

from Intelligence.registry import ModuleRegistry

THEOREM_PROVEN = False


def _import(path: str):
    return importlib.import_module(path)


# (name, import_path, kernel, description, factory?)
_MINING_SUBSYSTEMS: List[Dict[str, Any]] = [
    {
        "name": "turing_core",
        "import_path": "turing_core",
        "kernel": "step_kernel",
        "description": "Canonical T_phi fold + exact Q[sqrt(5)] substrate + "
        "double-SHA256 mining engine. Zero external deps.",
    },
    {
        "name": "folded_state_engine",
        "import_path": "Intelligence.folded_state",
        "kernel": "folded_kernel",
        "description": "Exact folded-state execution engine: T_phi byte-pair "
        "bijection, compiled queries in fold-space, no raw buffers.",
        "factory": lambda: _import("Intelligence.folded_state").ExactFoldedStateEngine(),
    },
    {
        "name": "safety_fsm",
        "import_path": "mining.safety_fsm",
        "kernel": "step_kernel",
        "description": "Four-state cycle SEARCHING->SUBMITTING->"
        "WAITING_EXTERNAL->COOLDOWN->SEARCHING; never two consecutive blocks.",
    },
    {
        "name": "nonce_scheduler",
        "import_path": "mining.nonce_scheduler",
        "kernel": "mining_kernel",
        "description": "Deterministic Zeckendorf multi-family nonce ordering.",
    },
    {
        "name": "difficulty_controller",
        "import_path": "mining.difficulty",
        "kernel": "mining_kernel",
        "description": "Per-block target adjustment, deterministic.",
    },
    {
        "name": "mining_search",
        "import_path": "mining.search",
        "kernel": "path_kernel",
        "description": "Grover-style search, Merkle path verifier, hash " "preimage search.",
    },
    {
        "name": "toe_bridge",
        "import_path": "Intelligence.toe_bridge",
        "kernel": "gap_kernel",
        "description": "TOE quantum predictive engine on the project's own "
        "quantum tensor; predicts block context.",
        "factory": lambda: _import("Intelligence.toe_bridge").create_toe_bridge(),
    },
    {
        "name": "pythia_learning",
        "import_path": "Intelligence.pythia_learning",
        "kernel": "trace_kernel",
        "description": "Germ-line consolidation of winning patterns.",
    },
    {
        "name": "pythia_memory",
        "import_path": "Intelligence.pythia_memory",
        "kernel": "trace_kernel",
        "description": "Episodic / semantic / curriculum / archival memory.",
    },
    {
        "name": "meta_evolution",
        "import_path": "Intelligence.meta_evolution",
        "kernel": "gap_kernel",
        "description": "Pythagoras->Pythia schedule evolution, phase "
        "transitions, surrogate, auto-primitive discovery, delta_phi.",
    },
    {
        "name": "counterfactual_intelligence",
        "import_path": "Intelligence.counterfactual_intelligence",
        "kernel": "folded_kernel",
        "description": "Superposition store: holds FoldedStateArtifacts, " "queries in fold-space.",
    },
    {
        "name": "lucas_scales",
        "import_path": "Intelligence.lucas_scales",
        "kernel": "trace_kernel",
        "description": "The L_10->L_20 intelligence scale ladder.",
    },
    {
        "name": "safety_constraints",
        "import_path": "Intelligence.safety_constraints",
        "kernel": "gap_kernel",
        "description": "Hashrate cap + never-two-consecutive enforcement "
        "alongside the mining FSM.",
    },
    {
        "name": "quantum_algorithms",
        "import_path": "Intelligence.quantum_algorithms",
        "kernel": "path_kernel",
        "description": "Lucas-elevated quantum algorithms (Grover, QFT, "
        "walks) backing the search core.",
        "factory": lambda: _import("Intelligence.quantum_algorithms").LucasEngine(),
    },
    {
        "name": "agentic_controller",
        "import_path": "Intelligence.agentic_controller",
        "kernel": "step_kernel",
        "description": "Classical-quantum hybrid dispatch controller.",
    },
    {
        "name": "predictive_solver",
        "import_path": "Intelligence.predictive_solver",
        "kernel": "mining_kernel",
        "description": "O(1) nonce predictor — honest about SHA256 limits.",
    },
    {
        "name": "mining_bridge",
        "import_path": "Intelligence.mining_bridge",
        "kernel": "mining_kernel",
        "description": "Wires the orchestrator's guidance into the miner.",
    },
    # Quantum substrates the guidance pipeline instantiates.
    {
        "name": "agi_substrate",
        "import_path": "core_engine.agi_substrate",
        "kernel": "amplitude_kernel",
        "description": "AGI substrate used by guide_mining for block-context "
        "prediction (honest confidence).",
        "factory": lambda: _import("core_engine.agi_substrate").create_canonical_agi_substrate(),
    },
    {
        "name": "quantum_cuda",
        "import_path": "core_engine.quantum_cuda",
        "kernel": "mining_kernel",
        "description": "iGPU/Turing exact-quantum-math accelerator: exact "
        "Grover k*, Zeckendorf schedule, consensus check.",
        "factory": lambda: _import("core_engine.quantum_cuda").create_simulator(0),
    },
    {
        "name": "cortex_golden_transform",
        "import_path": "src.cortex_golden_transform",
        "kernel": "amplitude_kernel",
        "description": "Pisot-optimised golden transform: reorders the "
        "nonce schedule by Lucas-resonant offsets.",
        "factory": lambda: _import("src.cortex_golden_transform").CortexTrainingOptimizer(),
    },
]


def build_mining_registry() -> ModuleRegistry:
    """Build the mining-loop registry — every entry contributes to mining."""
    reg = ModuleRegistry()
    for spec in _MINING_SUBSYSTEMS:
        reg.register(
            spec["name"],
            spec["import_path"],
            spec["description"] + f" Kernel route: {spec['kernel']}.",
            ["mining", spec["kernel"]],
            factory=spec.get("factory"),
        )
    return reg


def subsystem_kernels() -> Dict[str, str]:
    """name -> kernel for every registered mining subsystem."""
    return {s["name"]: s["kernel"] for s in _MINING_SUBSYSTEMS}


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool."""
    from lucas.pool import get as _lucas_get

    result = _lucas_get("step_kernel")({"states": 4}, n)
    result["module"] = __name__
    return result
