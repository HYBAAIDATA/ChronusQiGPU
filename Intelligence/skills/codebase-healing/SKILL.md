---
name: codebase-healing
description: Autonomous codebase AST audit, drift detection, phi-resonance evaluation, and zero-trust mathematical healing.
version: 1.0.0
tags: [salamander, agentic, healing, quantum, anti-drift, pythagoras]
---

# Codebase Healing & Autonomous Substrate Engineering

## When to use

Use this skill when Salamander operates as the autonomic codebase governor to inspect,
diagnose cognitive drift or fake quantum simulations, and safely apply first-principles
algebraic repairs across the repository.

## Instructions

1. **Scan AST & Audit Cognitive Drift**:
   - Call `SalamanderCodebaseScanner.scan_codebase()` or `scan_directory()`.
   - Inspect for discarded operator expressions, simulation fallbacks, cosmetic heuristics,
     and hardcoded parameters.
   - Evaluate $\phi$-structural resonance using `pythagoras.phi_resonance.PhiResonanceCalculator`.
   - Calculate the unified Substrate Health Index (SHI).

2. **Audit Imports** (`SalamanderCodebaseScanner.audit_imports()`, `scripts/import_audit.py`):
   - Every local import must resolve, down to the imported name.
   - An import inside `try/except` that swallows the failure hides a broken wire from
     every test; each finding is CRITICAL.
   - Never re-point an import automatically: check what the new target actually does.

3. **Formulate First-Principles Repairs**:
   - Call `SalamanderAgenticOptimizer.propose_repair(diagnostic)`.
   - Ensure every repair cites exact Hilbert space axioms ($U \in \mathcal{U}(\mathcal{H})$),
     exact group characters $F_N$ over $\mathbb{C}$, or $l_1$-norm density matrix coherence.

4. **Execute Zero-Trust Healing**:
   - Call `SalamanderAgenticOptimizer.apply_repair_sandboxed()`.
   - Create atomic `.bak` snapshots.
   - Validate AST syntax and execute the isolated verification test suite.
   - Trigger immediate atomic rollback on any regression or test failure.

5. **Verify Homeostasis**:
   - Re-evaluate Substrate Health Index: ensure $\text{SHI} \ge 0.85$ and 0 drift violations.

## Tools

- `Intelligence.salamander_agentic.SalamanderCodebaseScanner.scan_directory`
- `Intelligence.salamander_agentic.SalamanderAgenticOptimizer.apply_repair_sandboxed`
- `Intelligence.salamander_agentic.SalamanderAgenticController.run_autonomic_cycle`
- `Intelligence.first_principles_quantum`
- `pythagoras.phi_resonance.PhiResonanceCalculator`
- `pythagoras.pythagoras_mutation.PythagorasMutator`
