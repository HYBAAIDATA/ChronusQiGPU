---
name: isolated-repair
description: Execute a verified 12-stage closed-loop repair inside a disposable isolated temporary workspace with defect pre-reproduction and outcome probe.
version: 1.0.0
tags: [repair, verified_healing, sandbox, outcome_probe]
---
# Isolated Trusted Repair

Call `engine.execute_skill("isolated-repair", target_file=..., replacement_code=..., defect_probe=..., validator_fn=..., authorization_token=...)`.

This capability executes only under `internal` research profile with valid operator authorization. It creates an isolated temporary directory, proves the defect reproduces on baseline, applies the candidate, verifies the defect is cleared in the candidate, runs regression validation in isolation, and publishes atomically to the source tree only upon unanimous verification.

Repairs are recorded in `RepairLearningLedger` to empirically refine future repair ranking based on verified outcomes.
