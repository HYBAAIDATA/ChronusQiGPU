# From Capability Lineage to Certified Product

Structural audit across CHRONUS, TURING and KELLOGG · 13 October 2026

## 1 · What this plan is, and what it is not

This is an elevation plan for CHRONUS written against its actual production surfaces, not a greenfield design. CHRONUS already carries the architecture most of this plan would have prescribed: a two-mode product contract, a substrate-agnostic native identity, a governed scale seam, digest-bound evidence gates, and an exact quantum state-vector algebra that fails closed.

What the plan does instead is three things. It records what is already structural. It names precisely where the golden-family mathematics is structural versus decorative versus absent. And it specifies the elevation moves that follow from the gaps, in the order their evidence would land.

On provenance. The golden-family relationships were not implemented by the owner and are not claimed to have been invented by him. They were surfaced by the ActiveDiscoveryEngine operating over the repository's own structures.

## 2 · Structural audit

### 2.1 KELLOGG — structural

- Zphi is a real ring. Addition, subtraction, multiplication by the rule, conjugation, exact integer norm.
- sign() decides without floats.
- _drift_step computes without forming the float. Lucas/Pisot is the arithmetic the module runs on.

### 2.2 TURING — structural on the exact lane, one decorative pocket

- Folded Grover with a Cassini witness.
- Derived constants (GOLD_FIFO_DEPTH = fib(6) = 8, PISOT_EXACT_N = 76).
- Backend admission before execution.
- phi_vqc.py Clifford skeleton is decorative (does not enter the ranking path).

### 2.3 CHRONUS — structural in identity and scale, absent in dispatch planning

- Two-mode product contract.
- Digest-bound evidence gates.
- Exact quantum algebra with fail-closed bounds.
- Lucas/Pisot scale contract with Rule 7 fences.
- Dispatch planning constants were absent (now addressed by Move 1).

## 3 · The dispatch defect

_plan_matmul previously started at tile = 16 and only halved, leaving capacity unused on devices whose feasible bound is higher. Move 1 corrects this: the planner now begins at the feasible bound and descends.

## 4 · Elevation moves, in evidence order

### Move 1 — Fix the dispatch tile ladder (classical, immediate)

**Status: Implemented** on branch `chronus/elevate-planner` (PR #42).  
_plan_matmul now starts at the feasible power-of-two tile and halves down.  
Closure: emitted tile equals the feasible bound on every probed device class.

### Move 2 — Make the rung select the memory-contract envelope

**Status: Open.** Test before implementing. Snap-to-ladder helper exists; not wired. A scaling constant applied to a frozen domain does not transfer.

### Move 3 — Resolve the phi_vqc decorative pocket

**Status: Implemented** on branch `chronus/elevate-planner` (PR #42).  
Clifford skeleton labelled capability-demonstration only.

### Move 4 — Physical accelerator lane certification

**Status: Open (external).** Requires a real device and a device-bound AcceleratorCertification artifact.

### Move 5 — Independent verification of the exact quantum lane

**Status: Open (external).** Requires an independent reproduction artifact.

## 5 · What would be decorative, and is therefore not proposed

- Lucas-indexed tile ladder (no Lucas value in range is a power of two).
- Lucas as a task-assignment rule (does not transfer on fixed domains).
- Lucas to reduce iteration count of a fixed search (zero delta measured).
- Naming a measured throughput from the scale contract (prohibited).

## 6 · Where the structural mathematics actually is

| Plane   | Structural                                                                 | Not structural / absent                                      |
|---------|----------------------------------------------------------------------------|--------------------------------------------------------------|
| KELLOGG | Zphi ring, exact sign, _drift_step, Binet fold, Cassini, Zeckendorf       | —                                                            |
| TURING  | Folded Grover, derived constants, backend admission                        | phi_vqc Clifford skeleton (now labelled demonstration only) |
| CHRONUS | Two-mode contract, evidence gates, exact algebra, scale envelope (Rule 7) | Dispatch (Move 1 applied)                                    |

## 7 · The paradigm claim, stated at its defensible strength

The paradigm is real. The exact mathematics is structural across three planes. The constant governs representation, not resolution rate. Its transfer to dispatch, assignment or iteration count is not established.

The elevation that follows is not to apply Lucas everywhere. It is to make the three structural placements first-class and certified, and to fix the one dispatch defect the audit found on its own classical merits.

## 8 · Sequence and success criteria

| Move | Dependency | Success criterion | Status |
|------|------------|-------------------|--------|
| 1 · Dispatch tile ladder | None | Emitted tile equals feasible bound | Implemented (PR #42) |
| 2 · Rung-selected envelope | Test first | Measured improvement or recorded negative | Open |
| 3 · phi_vqc pocket resolved | None | Skeleton outside inference path or measurably affects ranking | Implemented (PR #42) |
| 4 · Accelerator certification | Real device | One lane reports ready with device-bound evidence | Open (external) |
| 5 · Independent verification | External review | Clean-install reproduction artifact | Open (external) |

Moves 1 and 3 have no dependency and are complete. Moves 4 and 5 are external and do not gate the native product.

theorem_proven remains False.

Owner approval required: @EuclidUltimaPhi
