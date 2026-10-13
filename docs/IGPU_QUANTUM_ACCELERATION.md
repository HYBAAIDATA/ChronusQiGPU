# iGPU acceleration

The acceleration comes from the quantum-from-maths plane. The iGPU is the software-defined execution surface.

## What is implemented

- Exact \(\mathbb{Q}(\phi)\) geometry and Lucas/Pisot scale contracts execute on ordinary host arithmetic.
- Dual-mode product contract: native (Chronus is a GPU in its own right) and climb (scales a bound host GPU when one is present).
- Dispatch planner starts at the feasible bound.
- Scale model and coprimality guard are executable.
- Silicon status is PASS only when a bound device executed the named operation. Without a device the status remains NOT_RUN; native mode continues.

## What the acceleration is not

- It is not dependent on a certified physical accelerator lane.
- It is not a hashrate claim.
- It is not a continuum or quantum-advantage claim.

The quantum mathematics is the acceleration. The iGPU is the surface that carries it. Mining is the testing surface.

theorem_proven: False
