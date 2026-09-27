---
name: solve-nonce
description: Predict and verify a winning nonce for a block header using the predictive solver, with safety enforcement.
version: 1.0.0
tags: [mining, predictive, safety]
---

# Solve Nonce

## When to use

Use this skill when PYTHIA needs to find a winning nonce for a single block.

## Instructions

1. **Safety check first** — call `orchestrator.check_mining_allowed(effective_hashrate_hps)`.
   If `allowed=False`, do NOT mine. Report the reason (hashrate cap exceeded or
   consecutive-block cooldown).

2. **Predictive solve** — call `orchestrator.solve(header, target, block_context)`.
   This attempts O(1) prediction from learned structure, then verifies by
   double-SHA256. If the prediction wins, return the nonce immediately.

3. **Fallback to structured search** — if the prediction misses, the solver
   automatically falls back to the agentic controller (polyhedral mapping +
   Grover/annealing/swarm dispatch).

4. **Report the winner** — once a verified winner is found, call
   `orchestrator.on_winner_found()` to transition to SUBMITTING state.

## Safety rules

- **Hashrate cap**: default 20 EH/s. Adjustable from frontend.
- **Never two consecutive blocks**: after a block is accepted, wait for an
  external block before mining again. NOT adjustable.
- **One block then wait**: mine one block, submit, wait for acceptance,
  enter cooldown. Do not continuously mine.

## Honest assessment

SHA256 is preimage-resistant. O(1) prediction is not achievable by any known
method. The predictive solver is a hypothesis machine — it generates candidates
from learned structure and verifies them. The honest baseline is O(sqrt(N))
via Grover. Whether the predictive layer beats Grover is the emergence question.

## Tools

- `Intelligence.predictive_solver.PredictiveSolver`
- `Intelligence.agentic_controller.AgenticController`
- `Intelligence.safety_constraints.SafetyController`
- `turing_core.PythiaMiningEngine.double_sha256`
