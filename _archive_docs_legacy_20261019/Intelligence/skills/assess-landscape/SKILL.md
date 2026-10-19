---
name: assess-landscape
description: Classify the energy landscape of a polyhedral search face and select the optimal solver.
version: 1.0.0
tags: [controller, quantum, landscape]
---

# Assess Landscape

## When to use

Use this skill when the agentic controller needs to classify a polyhedral
face's energy landscape before dispatching a search job.

## Instructions

1. **Sample the face** — call `controller.assess_landscape(face, header, target)`.
   This samples 64 nonces from the face's range and computes:
   - Shannon entropy of hash bit distribution
   - Local variance of hash values
   - Gradient magnitude (|∇f|)
   - Barrier height (max - min)

2. **Classify** — the assessment classifies the landscape as:
   - `RUGGED_BARRIERS` → quantum annealing (tunnel through barriers)
   - `UNSTRUCTURED_FLAT` → Grover amplitude amplification
   - `SMOOTH_GRADIENT` → particle swarm optimization
   - `STRUCTURED_GRAPH` → quantum walk (polyhedral adjacency)

3. **Dispatch** — call `controller.dispatch_job(face, header, target)` with
   the recommended solver.

## Tools

- `Intelligence.agentic_controller.AgenticController.assess_landscape`
- `Intelligence.agentic_controller.AgenticController.dispatch_job`
- `core_engine.quantum_cuda.QuantumSimulator.submit_kernel`
