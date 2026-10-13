# Chronus iGPU Paradigm

**Home of the HYBA software-defined quantum-from-maths GPU and accelerated execution plane.**

License posture for claims: MIT · Python 3.10+ · Veritas Integritas · **Rule 7: Strict Honest Measurement** · 11D substrate active.

---

## Strategic thesis

> Modern enterprise computing pays a **Raw-State Tax** — repeated data movement,
> unnecessary materialisation, memory staging and brute-force re-embedding.
>
> HYBA thesis: **The Folded Form can be the Working Form** where the representation
> contract is exact and the workload can operate on it directly.
>
> Exact/invertible algebraic folding, structured search and evidence-backed execution
> can reduce work or movement without pretending that mathematical structure creates
> physical hardware that does not exist.

Chronus is HYBA's **software-defined GPU and heterogeneous execution plane**. It is
substrate- and hardware-agnostic: a CPU, iGPU, GPU or future accelerator may host a
Chronus run without becoming the Chronus product identity. Turing is the independent
HYBA Virtual Quantum Computer (VQC). Turing may use Chronus for authorised substrate
execution, but neither system owns or replaces the other.

Lucas/Pisot is the execution scale model of the whole system, including Chronus itself.
It is not a budget or sizing convention and not an assignment rule.

---

## Dual-mode product contract

The system is not dependent on silicon.

| Mode | Description |
|------|-------------|
| Native | Chronus is a GPU in its own right. Exact \(\mathbb{Q}(\phi)\) geometry and Lucas/Pisot scale contracts execute on ordinary host arithmetic. No physical device is required. |
| Climb | When a host GPU is bound, Chronus scales it. Silicon status is PASS only when the bound device executed the named operation. Without a device the status remains NOT_RUN; native mode continues. |

Mining is the testing surface. Enterprise and hyperscaler workloads carry their own accept predicates. The execution plane does not invent them.

---

## Dispatch geometry

The work-group planner selects the largest power-of-two tile that fits the device limits and halves down. It does not start at a fixed constant and only descend.

Lucas/Pisot remains the scale model for capacity and precision. It does not replace hardware-bound tile selection. A Lucas-indexed tile ladder is inadmissible: no Lucas value in range is a power of two, and the local-memory path requires power-of-two sizes.

The rung may later select the memory-contract envelope. That proposal is untested.

---

## The paradigm in one card

| # | Law |
|---|-----|
| 1 | Quantum / compute from **mathematics** may be substrate-agnostic, but the actual execution substrate must always be reported. |
| 2 | Intelligence and compute are separate authorities: EUCLID decides; Chronus executes; Turing is the VQC. |
| 3 | **Lucas/Pisot can structure scale** — memory budgets, batches, search windows, workers and other domains only where the implemented contract uses them. |
| 4 | Folded working representations must prove exactness/reconstruction and include all metadata in claimed density gains. |
| 5 | Speed claims come from measured reductions in work, movement, latency or convergence — never from the Lucas/Pisot name alone. |
| 6 | Native mode is complete without a host accelerator. Absence of a certified lane does not demote native Chronus. |
| 7 | Effective capacity is a maths-bounded envelope, not a throughput claim. Ladder stop is not TH/s. Hardware presence is not hardware execution. |

---

## Structural placement

| Plane | Where Lucas/Pisot is structural | Where it is not |
|-------|---------------------------------|-----------------|
| KELLOGG | \(\mathbb{Z}[\phi]\) ring; exact sign without floats; `_drift_step` without materialising \(L_m\) as float | — |
| TURING | Folded Grover Cassini witness; `fib(6)` FIFO; `PISOT_EXACT_N = 76` derived; backend admission before execution | `phi_vqc` Clifford skeleton is capability-demonstration only |
| CHRONUS | Dual-mode contract; digest-bound evidence gates; exact state-vector algebra; seam scale envelope | Dispatch tile size (hardware-bound, power-of-two) |

---

## What is not claimed

- No hashrate figure is declared.
- No continuum Yang–Mills mass gap is claimed.
- No quantum advantage is claimed.
- Mining is the testing surface, not the product identity.

`theorem_proven` remains `False`.


## TOE placement

TOE is the decision authority for lane selection. It is not a per-observation
telemetry annotator.

The Problem for lane selection is constructed in
`chronus/mla1517/mining/toe_lane_decision.py`:
- operators = declared M32 lane orders
- objective = marked-state probability
- query = (lane_order, share_yield)
- uncertain = declared plausible range on the effect
- reward bound only from real pool responses

The machine returns ACT only when the effect is identified, REFUSED when it
is not, and ACQUIRE_EVIDENCE when the model is contradicted. The rule-based
chooser remains the fallback. This is not yet wired into the production
call graph.

