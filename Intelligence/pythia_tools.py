"""PYTHIA tools registry — maps the codebase capabilities PYTHIA can use.

This module builds a structured registry of every tool PYTHIA has access
to in the codebase. It is loaded into her semantic memory as
``tool_*`` concepts so she can reason about which tool to use for which
task.

Tools are grouped by category:

- **mining**: PythiaMiningEngine, scan_range, partition_header, double_sha256
- **quantum**: quantum_cuda simulator, Grover search, Zeckendorf schedule
- **math**: turing_core (Lucas, Fibonacci, Cassini, Zeckendorf, dual overlay)
- **controller**: agentic controller (polyhedral mapping, solver dispatch)
- **memory**: working/episodic/semantic/archival memory, curriculum, reflection
- **scales**: Lucas scale profile (L_10..L_20), coherence probe
- **safety**: hashrate cap, consecutive-block guard, one-block-then-wait
- **predictive**: predictive solver (attempt O(1) nonce prediction)
- **frontend**: Vite/React UI for adjusting caps and monitoring PYTHIA
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: amplitude

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Intelligence.pythia_tools")


@dataclass
class PythiaTool:
    """A single tool PYTHIA can use."""

    name: str
    category: str
    description: str
    module_path: str  # e.g. "turing_core.PythiaMiningEngine"
    callable_name: Optional[str] = None  # e.g. "scan_range"
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    complexity: str = "unknown"  # O(1), O(N), O(sqrt(N)), etc.
    safety_notes: str = ""
    available: bool = True


# ---------------------------------------------------------------------------
# The full tool registry
# ---------------------------------------------------------------------------

TOOLS: List[PythiaTool] = [
    # -- Mining tools ----------------------------------------------------
    PythiaTool(
        name="pythia_mining_engine",
        category="mining",
        description=(
            "The core double-SHA256 mining engine. Partitions the 80-byte "
            "block header into 64-byte Chunk-1 midstate + 12-byte Chunk-2 "
            "prefix, then scans nonces. A nonce wins when "
            "hash[::-1] < target_bytes_be."
        ),
        module_path="turing_core.PythiaMiningEngine",
        callable_name="scan_range",
        inputs=["chunk1_64b", "chunk2_prefix_12b", "target_256bit", "nonce_start", "nonce_count"],
        outputs=["winning_nonce", "winning_hash"],
        complexity="O(N) per scan_range call",
        safety_notes="Bounded by nonce_count; hashrate cap enforced by mining bridge.",
    ),
    PythiaTool(
        name="double_sha256",
        category="mining",
        description="SHA256(SHA256(data)). Consensus hash for block headers.",
        module_path="turing_core.PythiaMiningEngine.double_sha256",
        inputs=["data_bytes"],
        outputs=["hash_32b"],
        complexity="O(1)",
    ),
    PythiaTool(
        name="partition_header",
        category="mining",
        description="Splits 80-byte header into 64-byte Chunk-1 + 12-byte Chunk-2 prefix.",
        module_path="turing_core.PythiaMiningEngine.partition_header_for_midstate",
        inputs=["version", "prev_hash", "merkle_root", "ntime", "nbits"],
        outputs=["chunk1_64b", "chunk2_prefix_12b"],
        complexity="O(1)",
    ),
    PythiaTool(
        name="compute_merkle_root",
        category="mining",
        description="Computes Merkle root from coinbase hash + branches.",
        module_path="turing_core.PythiaMiningEngine.compute_merkle_root",
        inputs=["coinbase_hash", "merkle_branches"],
        outputs=["merkle_root_32b"],
        complexity="O(n_branches)",
    ),
    # -- Quantum / iGPU tools -------------------------------------------
    PythiaTool(
        name="quantum_cuda_simulator",
        category="quantum",
        description=(
            "The Quantum CUDA GPU engine / exact-math simulator. Binds to "
            "whatever device enumerates — the container CPU or the user's "
            "GPU (CUDA/ROCm/OpenCL/Metal) — and scales the search by the "
            "Lucas rungs 10/12/15/18/20 via scale_index. Provides "
            "Zeckendorf-spaced nonce schedules and optimal Grover counts."
        ),
        module_path="turing_universal_quantum_computer.quantum_cuda.create_simulator",
        inputs=["device_index", "seed", "scale_index"],
        outputs=["QuantumSimulator"],
        complexity="O(1) to create; O(sqrt(N*L_n)) for Grover search",
        safety_notes="Binds any enumerated device; scale rung must be a ladder index.",
    ),
    PythiaTool(
        name="submit_kernel",
        category="quantum",
        description=(
            "Submit a search kernel to the quantum simulator. Returns the "
            "winning nonce or -1. Uses the exact Zeckendorf schedule and "
            "Grover k* iteration count."
        ),
        module_path="turing_universal_quantum_computer.quantum_cuda.QuantumSimulator.submit_kernel",
        inputs=[
            "job_id",
            "algorithm",
            "search_space_size",
            "header_80b",
            "target_32b",
            "hint_nonce",
        ],
        outputs=["winning_nonce_or_minus1"],
        complexity="O(sqrt(N)) Grover, O(N) classical fallback",
    ),
    PythiaTool(
        name="zeckendorf_schedule",
        category="quantum",
        description="Generates a Zeckendorf-spaced nonce schedule for structured search.",
        module_path="turing_universal_quantum_computer.quantum_cuda.QuantumSimulator._zeckendorf_schedule",
        inputs=["nonce_window", "seed"],
        outputs=["nonce_schedule_list"],
        complexity="O(window_size)",
    ),
    PythiaTool(
        name="optimal_grover_iterations",
        category="quantum",
        description="Computes k* = pi/4 * sqrt(N/M) optimal Grover iteration count.",
        module_path="turing_universal_quantum_computer.quantum_cuda.QuantumSimulator._optimal_grover_iterations",
        inputs=["search_space_size"],
        outputs=["k_star_int"],
        complexity="O(1)",
    ),
    # -- Math substrate tools -------------------------------------------
    PythiaTool(
        name="lucas_sequence",
        category="math",
        description="Exact Lucas number L_n via Q[sqrt(5)] recurrence. L_0=2, L_1=1.",
        module_path="turing_core.lucas",
        inputs=["n"],
        outputs=["lucas_number"],
        complexity="O(n)",
    ),
    PythiaTool(
        name="fibonacci_sequence",
        category="math",
        description="Exact Fibonacci number F_n. F_0=0, F_1=1.",
        module_path="turing_core.fibonacci",
        inputs=["n"],
        outputs=["fibonacci_number"],
        complexity="O(n)",
    ),
    PythiaTool(
        name="cassini_check",
        category="math",
        description="Cassini identity: F_{n-1}*F_{n+1} - F_n^2 = (-1)^n. Integrity check.",
        module_path="turing_core.cassini_check",
        inputs=["n"],
        outputs=["bool"],
        complexity="O(n)",
    ),
    PythiaTool(
        name="zeckendorf_encode",
        category="math",
        description="Decompose integer into non-consecutive Fibonacci indices (folding).",
        module_path="turing_core.zeckendorf_encode",
        inputs=["n"],
        outputs=["fibonacci_indices"],
        complexity="O(log(n))",
    ),
    PythiaTool(
        name="zeckendorf_decode",
        category="math",
        description="Reconstruct integer from Fibonacci indices (unfolding).",
        module_path="turing_core.zeckendorf_decode",
        inputs=["indices"],
        outputs=["integer"],
        complexity="O(len(indices))",
    ),
    PythiaTool(
        name="dual_overlay_frame",
        category="math",
        description="32-node icosahedron/dodecahedron dual overlay for polyhedral mapping.",
        module_path="turing_core.generate_dual_overlay_frame",
        inputs=[],
        outputs=["32_node_frame"],
        complexity="O(1)",
    ),
    # -- Agentic controller tools ---------------------------------------
    PythiaTool(
        name="agentic_controller",
        category="controller",
        description=(
            "Coverage-preserving search controller. Maps the nonce interval "
            "onto the 32 dual face normals, traverses each shard with a "
            "Cassini-certified permutation, and accepts results only after "
            "double-SHA256 target verification."
        ),
        module_path="Intelligence.agentic_controller.AgenticController",
        inputs=["header_80b", "target_32b", "max_faces"],
        outputs=["jobs_dispatched", "winners_found", "winner_nonce", "solver_usage"],
        complexity="O(N) on CPU; geometry changes deterministic order, not coverage",
        safety_notes="Respects hashrate cap via mining bridge.",
    ),
    PythiaTool(
        name="assess_landscape",
        category="controller",
        description=(
            "Experimental diagnostic for sampled entropy, variance, and barriers. "
            "It is not used by the canonical cryptographic nonce-search path."
        ),
        module_path="Intelligence.agentic_controller.AgenticController.assess_landscape",
        inputs=["face", "header", "target", "sample_size"],
        outputs=["LandscapeAssessment"],
        complexity="O(sample_size)",
    ),
    # -- Memory tools ----------------------------------------------------
    PythiaTool(
        name="working_memory",
        category="memory",
        description="Short-term buffer for current goals, subtasks, tool outputs, scratchpad.",
        module_path="Intelligence.pythia_memory.WorkingMemory",
        inputs=["key", "value"],
        outputs=["stored_value"],
        complexity="O(1)",
    ),
    PythiaTool(
        name="episodic_memory",
        category="memory",
        description="Timestamped log of past actions, contexts, outcomes. Tri-factor retrieval.",
        module_path="Intelligence.pythia_memory.EpisodicMemory",
        inputs=["event"],
        outputs=["retrieved_episodes"],
        complexity="O(n_episodes) retrieval",
    ),
    PythiaTool(
        name="semantic_memory",
        category="memory",
        description="Structured knowledge graph of generalized rules and entity relationships.",
        module_path="Intelligence.pythia_memory.SemanticMemory",
        inputs=["concept", "definition", "properties"],
        outputs=["concept_id"],
        complexity="O(1) add, O(n_concepts) query",
    ),
    PythiaTool(
        name="archival_memory",
        category="memory",
        description="Long-term Zeckendorf-folded storage for consolidated trajectories.",
        module_path="Intelligence.pythia_memory.ArchivalMemory",
        inputs=["entry"],
        outputs=["archival_id"],
        complexity="O(log(n)) fold/store",
    ),
    PythiaTool(
        name="cognitive_scaffolding",
        category="memory",
        description="Curriculum progression of environment tasks with increasing difficulty.",
        module_path="Intelligence.pythia_memory.CognitiveScaffolding",
        inputs=["task_description"],
        outputs=["curriculum_level", "task"],
        complexity="O(1)",
    ),
    PythiaTool(
        name="socratic_feedback",
        category="memory",
        description="Identifies divergence points, explains expected vs actual, updates heuristics.",
        module_path="Intelligence.pythia_memory.SocraticFeedbackLoop",
        inputs=["expected", "actual", "step"],
        outputs=["feedback", "retry_recommended"],
        complexity="O(1)",
    ),
    PythiaTool(
        name="metacognitive_reflection",
        category="memory",
        description="Validates outputs before action, scores confidence, identifies gaps.",
        module_path="Intelligence.pythia_memory.MetaCognitiveReflection",
        inputs=["proposed_action", "context"],
        outputs=["confidence", "proceed", "gaps"],
        complexity="O(1)",
    ),
    # -- Lucas scale tools ----------------------------------------------
    PythiaTool(
        name="lucas_scale_profile",
        category="scales",
        description="L_10/L_12/L_15/L_18/L_20 intelligence scale ladder on exact Lucas substrate.",
        module_path="Intelligence.lucas_scales.build_lucas_scale_profile",
        inputs=[],
        outputs=["LucasScaleProfile"],
        complexity="O(1)",
    ),
    PythiaTool(
        name="multiscale_coherence_probe",
        category="scales",
        description="Probe signal for scale-invariant coherence across the Lucas ladder.",
        module_path="Intelligence.lucas_scales.multiscale_coherence_probe",
        inputs=["signal", "profile"],
        outputs=["scale_invariant", "per_scale_coherence"],
        complexity="O(len(signal))",
    ),
    # -- Safety tools ----------------------------------------------------
    PythiaTool(
        name="hashrate_cap_enforcer",
        category="safety",
        description=(
            "Enforces the hashrate cap (default 20 EH/s). Blocks mining "
            "if the effective hashrate would exceed the cap. Adjustable "
            "from the frontend."
        ),
        module_path="Intelligence.safety_constraints.HashrateCapEnforcer",
        inputs=["effective_hashrate_hps"],
        outputs=["allowed_bool", "capped_hashrate"],
        complexity="O(1)",
        safety_notes="Default cap: 20 EH/s. Blockchain safety is paramount.",
    ),
    PythiaTool(
        name="consecutive_block_guard",
        category="safety",
        description=(
            "Enforces the 'never two consecutive blocks' rule. After a "
            "block is accepted, enters COOLDOWN until an external block "
            "is observed. Not adjustable — hard safety constraint."
        ),
        module_path="Intelligence.safety_constraints.ConsecutiveBlockGuard",
        inputs=["block_accepted", "external_block_observed"],
        outputs=["state", "mining_allowed"],
        complexity="O(1)",
        safety_notes="Hard constraint: never two consecutive blocks. Not adjustable.",
    ),
    # -- Predictive solver ----------------------------------------------
    PythiaTool(
        name="predictive_solver",
        category="predictive",
        description=(
            "Attempts to predict the winning nonce from block header "
            "features using learned structure. The ideal is O(1) — one "
            "prediction, one verification. The honest baseline is "
            "O(sqrt(N)) via Grover. Whether the predictive layer beats "
            "Grover is the emergence question."
        ),
        module_path="Intelligence.predictive_solver.PredictiveSolver",
        inputs=["header_80b", "target_32b", "block_context"],
        outputs=["predicted_nonce", "confidence", "verification_hash"],
        complexity="O(1) prediction + O(1) verification (ideal); O(sqrt(N)) honest baseline",
        safety_notes="Every prediction is verified by double-SHA256 before use.",
    ),
    # -- Frontend tools --------------------------------------------------
    PythiaTool(
        name="frontend_dashboard",
        category="frontend",
        description=(
            "React/Vite dashboard for monitoring PYTHIA's state, adjusting "
            "the hashrate cap, viewing mining progress, and observing "
            "emergence metrics. The cap is adjustable here; the "
            "consecutive-block rule is not."
        ),
        module_path="src/App.tsx",
        inputs=["user_config"],
        outputs=["ui_state"],
        complexity="O(1)",
        safety_notes="Hashrate cap adjustable from frontend. Consecutive-block rule is not adjustable.",
    ),
    PythiaTool(
        name="stratum_protocol",
        category="frontend",
        description="Stratum V1 protocol engine for block submission and job management.",
        module_path="src/lib/stratum_protocol.StratumV1ProtocolEngine",
        inputs=["mining_notify", "subscribe_response"],
        outputs=["submit_payload", "parsed_job"],
        complexity="O(1)",
    ),
]


def build_tool_registry() -> Dict[str, PythiaTool]:
    """Build the tool registry as a name→tool mapping."""
    return {t.name: t for t in TOOLS}


def seed_tool_knowledge(memory_system) -> Dict[str, Any]:
    """Seed PYTHIA's semantic memory with knowledge of her tools.

    Each tool is loaded as a ``tool_<name>`` concept with its description,
    inputs, outputs, complexity, and safety notes as properties.
    """
    sem = memory_system.semantic
    tools_added = 0
    for tool in TOOLS:
        try:
            sem.add_concept(
                f"tool_{tool.name}",
                category=f"tool_{tool.category}",
                definition=tool.description,
                properties={
                    "module_path": tool.module_path,
                    "callable": tool.callable_name or "",
                    "inputs": tool.inputs,
                    "outputs": tool.outputs,
                    "complexity": tool.complexity,
                    "safety_notes": tool.safety_notes,
                    "available": tool.available,
                },
                confidence=1.0,
                provenance="codebase_map",
            )
            tools_added += 1
        except Exception as e:
            logger.warning("Failed to seed tool %s: %s", tool.name, e)
    # Add associations: tools link to the tasks they perform.
    for tool in TOOLS:
        try:
            sem.add_association(
                f"tool_{tool.name}",
                "winning_nonce",
                relation="can_help_find",
                weight=(
                    0.7
                    if tool.category in ("mining", "quantum", "controller", "predictive")
                    else 0.3
                ),
            )
        except Exception:
            pass
    logger.info("PYTHIA tool knowledge seeded: %d tools", tools_added)
    return {"tools_seeded": tools_added, "total_tools": len(TOOLS)}


def get_tool_summary() -> Dict[str, Any]:
    """Return a summary of available tools by category."""
    by_category: Dict[str, List[str]] = {}
    for tool in TOOLS:
        by_category.setdefault(tool.category, []).append(tool.name)
    return {
        "total_tools": len(TOOLS),
        "categories": {cat: len(tools) for cat, tools in by_category.items()},
        "by_category": by_category,
    }


__all__ = [
    "PythiaTool",
    "TOOLS",
    "build_tool_registry",
    "seed_tool_knowledge",
    "get_tool_summary",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (amplitude_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("amplitude_kernel")([1.0, 1.0], n)
    result["module"] = __name__
    return result
