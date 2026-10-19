---
name: feed-block-data
description: Feed real block data into PYTHIA's memory for predictive training and pattern learning.
version: 1.0.0
tags: [training, block-data, predictive]
---

# Feed Block Data

## When to use

Use this skill when feeding real block headers into PYTHIA so she can learn
patterns from historical block data. This is the environment-driven teaching
that replaces static dataset training.

## Instructions

1. **Extract features** — for each block header, extract:
   - Header seed (SHA256 of 80-byte header)
   - Lucas/Pisot projections (seed mod L_n for each scale)
   - Zeckendorf decomposition of the seed
   - Phi-phase alignment
   - Dual-overlay node mapping (seed mod 32)
   - Block height, difficulty, timestamp

2. **Store in episodic memory** — record each block as an episodic event
   with the winning nonce, the block height, and the features. This builds
   PYTHIA's historical knowledge base.

3. **Consolidate to semantic memory** — after feeding multiple blocks,
   call `memory.consolidate_task()` to abstract general rules from the
   episodic history. This is where PYTHIA learns patterns (if any exist).

4. **Train the predictive solver** — the predictive solver's memory-guided
   strategy retrieves similar past episodes when predicting nonces for
   new blocks. More block data = better retrieval = potentially better
   predictions.

## Honest assessment

Bitcoin nonces are NOT phi-structured (verified by the repo's von Neumann
entropy test: S_nonce = 4.991548 ≈ S_random = 4.991803). This means there
is no known mathematical structure in winning nonces that PYTHIA can learn.
The predictive solver's hit rate against real difficulty targets is expected
to be near zero. This is the honest scientific outcome.

## Data sources

- Bitcoin block headers via RPC (getblockheader)
- Stratum V1 mining.notify messages
- Historical block data from blockchain explorers

## Tools

- `Intelligence.pythia_memory.PythiaMemorySystem`
- `Intelligence.predictive_solver.PredictiveSolver`
- `Intelligence.pythia_knowledge` (domain knowledge seed)
- `src/lib/stratum_protocol.StratumV1ProtocolEngine`
