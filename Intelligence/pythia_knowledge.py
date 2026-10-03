"""PYTHIA knowledge seed — loads domain knowledge into her memory on startup.

This module seeds PYTHIA's semantic memory with the domain knowledge she
needs to understand what she is doing:

- **What a winning nonce is** — a 32-bit value such that
  double-SHA256(chunk1 + chunk2_prefix + nonce_le32), interpreted in
  little-endian consensus order, is numerically less than the 256-bit
  target derived from the block's ``nbits`` field.
- **How a winning nonce is identified** — the PythiaMiningEngine
  partitions the 80-byte block header into a 64-byte Chunk-1 midstate
  and a 12-byte Chunk-2 prefix (version + prev_hash + merkle_root +
  ntime + nbits), then scans nonces. A nonce wins when
  ``hash[::-1] < target_bytes_be``.
- **How Lucas projections are labelled** — some research surfaces multiply
  physical hashrate by L_n as a decorative accounting projection. This is not
  measured speedup, does not avoid SHA-256 work, and must not be called hashrate.
- **Safety boundaries** — the hashrate cap (default 20 EH/s), the
  "never two consecutive blocks" rule, and the "one block then wait"
  protocol. Blockchain safety is paramount.
- **The codebase map** — the tools PYTHIA can use (see
  :mod:`Intelligence.pythia_tools`).

This is **not** a claim that PYTHIA understands mining. It is a
knowledge seed — structured facts loaded into semantic memory that
PYTHIA's learning substrate can build on. Whether she develops genuine
predictive understanding is the emergence question.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: amplitude

from __future__ import annotations

import logging
from typing import Any, Dict, List

from lucas.ladder import FULL_LADDER

logger = logging.getLogger("Intelligence.pythia_knowledge")

# ---------------------------------------------------------------------------
# Domain knowledge facts — loaded into PYTHIA's semantic memory
# ---------------------------------------------------------------------------

KNOWLEDGE_FACTS: List[Dict[str, Any]] = [
    # -- What a winning nonce is -----------------------------------------
    {
        "concept": "winning_nonce",
        "category": "mining_fundamentals",
        "definition": (
            "A 32-bit unsigned integer nonce such that "
            "double_SHA256(80_byte_block_header_with_nonce) interpreted "
            "in little-endian consensus byte order is numerically less "
            "than the 256-bit target threshold."
        ),
        "properties": {
            "size_bits": 32,
            "range": [0, 4294967295],
            "hash_function": "double_SHA256",
            "comparison": "hash_little_endian < target_big_endian",
            "uniqueness": "multiple winning nonces may exist in a range",
        },
        "confidence": 1.0,
        "provenance": "bitcoin_consensus",
    },
    {
        "concept": "block_header_structure",
        "category": "mining_fundamentals",
        "definition": (
            "80-byte header: version(4) + prev_hash(32) + merkle_root(32) "
            "+ ntime(4) + nbits(4) + nonce(4). Partitioned into 64-byte "
            "Chunk-1 midstate (version+prev_hash+merkle_root+first 4 bytes "
            "of ntime) and 12-byte Chunk-2 prefix (remaining ntime+nbits)."
        ),
        "properties": {
            "total_bytes": 80,
            "chunk1_bytes": 64,
            "chunk2_prefix_bytes": 12,
            "nonce_bytes": 4,
            "nonce_offset": 76,
        },
        "confidence": 1.0,
        "provenance": "bitcoin_consensus",
    },
    {
        "concept": "target_threshold",
        "category": "mining_fundamentals",
        "definition": (
            "256-bit big-endian value derived from nbits (compact form). "
            "A hash is a winning hash if hash[::-1] < target_bytes_be. "
            "Lower target = higher difficulty = harder to find a winner."
        ),
        "properties": {
            "derived_from": "nbits",
            "format": "256-bit big-endian",
            "comparison": "less_than",
            "retarget_interval": 2016,
            "retarget_time": 1209600,
        },
        "confidence": 1.0,
        "provenance": "bitcoin_consensus",
    },
    {
        "concept": "double_sha256",
        "category": "cryptographic_primitives",
        "definition": (
            "SHA256(SHA256(data)). The consensus hash function for Bitcoin "
            "block headers and Merkle tree computation. Preimage-resistant: "
            "given a target hash, finding an input that produces it is "
            "computationally infeasible (O(2^256) brute force)."
        ),
        "properties": {
            "algorithm": "SHA-256",
            "rounds": 2,
            "output_bits": 256,
            "preimage_resistance": True,
            "collision_resistance": True,
        },
        "confidence": 1.0,
        "provenance": "cryptographic_fact",
    },
    # -- How power scales ------------------------------------------------
    {
        "concept": "lucas_pisot_scaling",
        "category": "power_scaling",
        "definition": (
            "Lucas values L_10=123, L_12=322, L_15=1364, L_18=5778 and "
            "L_20=15127 are exact structural labels. Multiplying measured "
            "physical hashrate by one of these values is a decorative accounting "
            "projection only: it is not measured speedup, additional hashes, or "
            "evidence that SHA-256 work was avoided."
        ),
        "properties": {
            "mechanism": "decorative_projection = physical_hashrate * L_n",
            "scales": [123, 322, 1364, 5778, 15127],
            "scale_indices": list(FULL_LADDER),
            "substrate": "Q[sqrt(5)] exact rational core",
            "semantic_role": "decorative",
            "measured_advantage": False,
        },
        "confidence": 1.0,
        "provenance": "lucas_pisot_research_closure",
    },
    {
        "concept": "grover_optimal_iterations",
        "category": "power_scaling",
        "definition": (
            "Grover's amplitude amplification gives O(sqrt(N)) search vs "
            "O(N) classical. The optimal iteration count is k* = pi/4 * "
            "sqrt(N/target_fraction). The repo computes this exactly via "
            "the Zeckendorf-spaced schedule. This is a quadratic speedup, "
            "not an exponential one."
        ),
        "properties": {
            "speedup": "quadratic",
            "classical": "O(N)",
            "quantum": "O(sqrt(N))",
            "k_star_formula": "pi/4 * sqrt(N/M)",
        },
        "confidence": 1.0,
        "provenance": "quantum_computing_fact",
    },
    # -- Safety boundaries ----------------------------------------------
    {
        "concept": "hashrate_cap",
        "category": "safety_constraints",
        "definition": (
            "PYTHIA's effective hashrate must never exceed the configured "
            "cap. Default cap: 20 EH/s (20 exahashes per second = "
            "2*10^19 H/s). This prevents PYTHIA from dominating the network "
            "and threatening blockchain decentralisation. The cap is "
            "adjustable from the frontend but defaults to 20 EH/s."
        ),
        "properties": {
            "default_cap_ehs": 20,
            "default_cap_hps": 20_000_000_000_000_000_000,
            "enforceable": True,
            "adjustable_from": "frontend",
            "reason": "blockchain_safety_paramount",
        },
        "confidence": 1.0,
        "provenance": "safety_policy",
    },
    {
        "concept": "never_two_consecutive_blocks",
        "category": "safety_constraints",
        "definition": (
            "PYTHIA must never mine two consecutive blocks. After mining "
            "a block, she must wait for at least one other miner to mine "
            "the next block before she mines again. This prevents "
            "selfish mining and centralisation. The constraint is "
            "enforced at the mining-bridge level: after a block is "
            "accepted, the bridge enters a COOLDOWN state that blocks "
            "new mining until an external block is observed."
        ),
        "properties": {
            "rule": "no_two_consecutive",
            "enforcement": "mining_bridge_cooldown",
            "cooldown_exit_condition": "external_block_observed",
            "adjustable": False,
            "reason": "anti_centralisation",
        },
        "confidence": 1.0,
        "provenance": "safety_policy",
    },
    {
        "concept": "one_block_then_wait",
        "category": "safety_constraints",
        "definition": (
            "PYTHIA mines one block, submits it to the network, and waits "
            "until it is accepted (confirmed by the network). Once "
            "accepted, she enters the consecutive-block cooldown. She does "
            "not continuously mine. This is the 'solve not search' "
            "protocol: the goal is to find one winning nonce for one block, "
            "not to dominate the hashrate."
        ),
        "properties": {
            "protocol": "solve_one_wait",
            "states": ["searching", "submitting", "waiting_acceptance", "cooldown"],
            "terminal_state": "cooldown",
            "reason": "blockchain_safety",
        },
        "confidence": 1.0,
        "provenance": "safety_policy",
    },
    # -- Solving vs searching -------------------------------------------
    {
        "concept": "solving_vs_searching",
        "category": "mining_philosophy",
        "definition": (
            "PYTHIA's goal is to SOLVE for the winning nonce, not to "
            "search for it. The ideal is O(1) — one prediction, one "
            "verification. The reality is that SHA256 is preimage-"
            "resistant, so O(1) prediction is not achievable by any known "
            "method. PYTHIA's predictive solver attempts to narrow the "
            "search space using learned structure from block data, but "
            "the honest baseline is O(sqrt(N)) via Grover, not O(1). "
            "Whether the predictive layer achieves better than O(sqrt(N)) "
            "is the emergence question."
        ),
        "properties": {
            "ideal": "O(1)",
            "honest_baseline": "O(sqrt(N))",
            "classical_baseline": "O(N)",
            "method": "predictive_solving_with_verification",
            "emergence_question": "can_learning_beat_grover",
        },
        "confidence": 1.0,
        "provenance": "repo_thesis",
    },
    {
        "concept": "block_acceptance",
        "category": "mining_protocol",
        "definition": (
            "After finding a winning nonce, PYTHIA submits the block to "
            "the network. The block is 'accepted' when it is confirmed by "
            "the network (included in the chain, not orphaned). PYTHIA "
            "waits for acceptance before transitioning to the cooldown "
            "state. If the block is orphaned, she returns to searching."
        ),
        "properties": {
            "submission": "stratum_v1_or_p2p",
            "acceptance": "network_confirmation",
            "orphan_handling": "return_to_searching",
        },
        "confidence": 1.0,
        "provenance": "mining_protocol",
    },
]

# ---------------------------------------------------------------------------
# Semantic associations — relationships between concepts
# ---------------------------------------------------------------------------

KNOWLEDGE_ASSOCIATIONS: List[Dict[str, Any]] = [
    {
        "from": "winning_nonce",
        "to": "block_header_structure",
        "relation": "found_within",
        "weight": 0.95,
    },
    {"from": "winning_nonce", "to": "target_threshold", "relation": "must_satisfy", "weight": 0.95},
    {"from": "winning_nonce", "to": "double_sha256", "relation": "verified_by", "weight": 0.95},
    {
        "from": "target_threshold",
        "to": "block_header_structure",
        "relation": "derived_from_nbits_in",
        "weight": 0.90,
    },
    {
        "from": "lucas_pisot_scaling",
        "to": "winning_nonce",
        "relation": "labels_projection_for",
        "weight": 0.20,
    },
    {
        "from": "grover_optimal_iterations",
        "to": "winning_nonce",
        "relation": "optimises_search_for",
        "weight": 0.85,
    },
    {"from": "hashrate_cap", "to": "lucas_pisot_scaling", "relation": "limits", "weight": 0.90},
    {
        "from": "never_two_consecutive_blocks",
        "to": "one_block_then_wait",
        "relation": "enforced_by",
        "weight": 0.95,
    },
    {
        "from": "one_block_then_wait",
        "to": "block_acceptance",
        "relation": "waits_for",
        "weight": 0.90,
    },
    {
        "from": "solving_vs_searching",
        "to": "winning_nonce",
        "relation": "attempts_to_predict",
        "weight": 0.75,
    },
    {
        "from": "solving_vs_searching",
        "to": "grover_optimal_iterations",
        "relation": "honest_baseline_is",
        "weight": 0.85,
    },
    {
        "from": "hashrate_cap",
        "to": "never_two_consecutive_blocks",
        "relation": "complements",
        "weight": 0.85,
    },
]


def seed_memory(memory_system) -> Dict[str, Any]:
    """Seed PYTHIA's semantic memory with domain knowledge.

    Loads all KNOWLEDGE_FACTS as semantic concepts and all
    KNOWLEDGE_ASSOCIATIONS as semantic associations. Returns a summary
    of what was seeded.
    """
    sem = memory_system.semantic
    concepts_added = 0
    associations_added = 0

    for fact in KNOWLEDGE_FACTS:
        try:
            sem.add_concept(
                fact["concept"],
                category=fact["category"],
                definition=fact["definition"],
                properties=fact.get("properties", {}),
                confidence=fact.get("confidence", 1.0),
                provenance=fact.get("provenance", "seeded"),
            )
            concepts_added += 1
        except Exception as e:
            logger.warning("Failed to seed concept %s: %s", fact["concept"], e)

    for assoc in KNOWLEDGE_ASSOCIATIONS:
        try:
            sem.add_association(
                assoc["from"],
                assoc["to"],
                relation=assoc["relation"],
                weight=assoc.get("weight", 0.5),
            )
            associations_added += 1
        except Exception as e:
            logger.warning("Failed to seed association %s→%s: %s", assoc["from"], assoc["to"], e)

    logger.info(
        "PYTHIA knowledge seed loaded: %d concepts, %d associations",
        concepts_added,
        associations_added,
    )
    return {
        "concepts_seeded": concepts_added,
        "associations_seeded": associations_added,
        "total_concepts": sem.n_concepts if hasattr(sem, "n_concepts") else concepts_added,
        "total_associations": (
            sem.n_associations if hasattr(sem, "n_associations") else associations_added
        ),
    }


__all__ = [
    "KNOWLEDGE_FACTS",
    "KNOWLEDGE_ASSOCIATIONS",
    "seed_memory",
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
