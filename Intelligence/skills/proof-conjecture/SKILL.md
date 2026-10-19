---
name: proof-conjecture
description: Formal mathematical conjecture tracking and lemma dependency DAG evaluation with strict separation between numerical experimentation and formal proof.
version: 1.0.0
tags: [mathematics, conjecture, formal_proof, proof_tracker]
---
# Formal Mathematical Conjecture Tracking

Call `engine.execute_skill("proof-conjecture", action="register"|"get"|"experiment", conjecture_id=..., ...)`

Adheres to Section 12 Scientific and Mathematical Protocol:
- Conjectures are formally represented with explicit domains and assumptions.
- Numerical experiments provide empirical evidence, NOT formal proof.
- Lemma dependency DAGs track logical derivation without circular reasoning.
- Never claim a problem is solved or proved without formal verification of all lemmas and zero unresolved steps.
