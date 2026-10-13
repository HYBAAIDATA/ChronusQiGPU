# Chronus ONE iGPU — dual-mode execution plane

The system is not dependent on silicon. It has two modes.

## Mode 1 — software-defined GPU
Chronus is a GPU in its own right. Exact \(\mathbb{Q}(\phi)\) geometry, Lucas/Pisot
scale contracts, and the folded working form execute on ordinary host
arithmetic. Mining is the current testing surface; the same plane carries
enterprise and hyperscaler workloads. No physical device is required for the
mathematics to run.

## Mode 2 — host-GPU scale
When a physical GPU is bound, Chronus scales the host device. The dispatch
planner selects the largest feasible tile. Silicon status is reported as PASS
only when the bound device executed the named operation. Without a device the
status remains NOT_RUN; the software-defined mode continues.

## Accept predicates
On the mining surface SHA-256d ≤ target remains the sole accept predicate.
Enterprise and hyperscaler workloads carry their own accept predicates. The
execution plane does not invent them.

## What is not claimed
- No hashrate figure is declared.
- No continuum or quantum-advantage claim is made.
- Mining is the testing surface, not the product identity.

theorem_proven: False
