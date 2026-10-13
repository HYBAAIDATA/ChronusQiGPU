# Chronus ONE iGPU — enterprise and hyperscaler surface

Mining is the testing surface. The iGPU path is the delivery plane.

## Role
Chronus ONE iGPU is the software-defined execution plane that will carry
enterprise and hyperscaler workloads. The current mining path (Hendrix
structured search, golden-stride schedule, SHA-256d accept predicate) is the
adversarial test bed: it exercises exact geometry, integer scheduling,
fail-closed silicon gates, and measured throughput under a fixed proof boundary.

## What is elevated
- Exact \(\mathbb{Q}(\phi)\) geometry and Lucas/Pisot scale contracts are the
  working representation.
- The dispatch planner selects the largest feasible tile; it does not start at
  a fixed constant and only descend.
- Silicon status is reported as PASS only when a bound device executed the
  named operation. Without a device the status remains NOT_RUN.
- SHA-256d remains the sole accept predicate on the mining surface. Enterprise
  workloads will carry their own accept predicates; the execution plane does
  not invent them.

## What is not claimed
- No hashrate figure is declared. 10 EH/s is a measured floor once physical
  ASIC or iGPU channels pass the silicon self-check.
- No continuum or quantum-advantage claim is made.
- Mining is not the product identity. It is the current test surface.

theorem_proven: False
