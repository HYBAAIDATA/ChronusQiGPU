# No-simulator semantics — closure of blocker 7

**Status:** DRAFT — closure specification, not implementation.
**Source of record:** `docs/EXACT_SUBSTRATE_FOUNDATIONS_REVIEW.md` §"Exact-only blockers", item 7.
**Baseline:** `3365bb3c28fe1aeb672e2309556d5979cb8f5d71`.

---

## 1. The defect as stated

> **No-simulator semantics**: the attachment and repository include software
> amplitude/tableau execution examples while the mandate bans simulators. Clarify
> the admissible exact execution representation rather than renaming a simulation.
> Exact quantum algebra on a classical host does not by itself prove physical-QPU
> execution or asymptotic quantum advantage.

The mandate and the repository appear to conflict. The review's instruction is
precise: **clarify the admissible representation** — do not rename.

## 2. The two texts in tension

**The mandate** (`OWNER_DECLARATIONS.md`, D6, quoted verbatim):

> "NO SIMULATIONS, NO APPROXIMATION, HEURISTICS, CLASSICAL DRESSED S QUANTUM.
> THEN YOU SEE PERFORMANCE. OBVIOUSLY IF YOU =HAVENT IMPLEMENTED IT WONT RUN"

**The repository** contains software amplitude/tableau execution:
`kellogg/quantum_tensor.py` (state vectors, Born probabilities),
`kellogg/exact_tensor.py` (`ExactTOETensor`, Clifford+T), and the statevector
execution in the quantum-library family.

## 3. The distinction the mandate is actually drawing

Read against the preceding sentence — *"CLASSICAL DRESSED S QUANTUM"* — the
prohibition targets **misrepresentation**, not execution on a host. Three
separate things are being conflated by the single word "simulation":

| Thing | Description | Status under the mandate |
|---|---|---|
| **Exact algebraic execution** | exact arithmetic over a declared algebraic domain; every result bit-reproducible; no float at any stage | **admissible** — this is *implementation*, not simulation |
| **Floating-point emulation** | complex128 statevector evolution with accumulated rounding | **prohibited** — approximation, per D6 |
| **Physical QPU execution** | a certified device performing the evolution | **a separate claim**, requiring device evidence |

**The admissible representation is the first.** Its defining property is that
every intermediate is exact: a Fraction, an element of Q(√2)+iQ(√2), a Z[φ]
element, or an exact rational Born weight. Nothing is approximated, so nothing
is being simulated. What the host does is *execute exact algebra*.

**Existing machinery already in this shape:**
- `kellogg/exact_tensor.py:ExactTOETensor` — Clifford+T over Q(√2) + iQ(√2),
  Fraction amplitudes, fail-closed gates, deterministic Born weights
- `docs/EXACT_OPERATOR_CLOSURE_REVIEW.md` — repaired float-promotion paths, so
  inexact inputs are *rejected* rather than silently admitted
- `l_hras/foundations/complexity.py` — declares memory bounded by the
  fail-closed cap `MLA1517_MAX_AMPLITUDES` (default 2²⁰)

## 4. The vocabulary ruling

Declared, and to be applied consistently:

| Term | Use it for | Do not use it for |
|---|---|---|
| **exact execution** | exact algebraic evaluation on any host | a floating-point statevector run |
| **simulation** | floating-point emulation, or a mock standing in for a device | exact algebraic evaluation |
| **device execution** | a certified device performing the evolution | work done on a CPU/GPU in exact arithmetic |

**Rule:** the word "simulation" must not be used to describe exact algebraic
execution, and exact algebraic execution must not be described as device
execution. Both mislabellings are prohibited — the first understates the work,
the second overstates it.

## 5. What exact execution on a classical host does not prove

The review: *"Exact quantum algebra on a classical host does not by itself prove
physical-QPU execution or asymptotic quantum advantage."*

**Two claims that remain unestablished, however exact the arithmetic:**

| Claim | Requires |
|---|---|
| Physical-QPU execution | device identity, certification, measurement provenance |
| Asymptotic quantum advantage | a cost model and an oracle cost, neither of which exact arithmetic supplies |

**Existing boundary to preserve:** `docs/EXACT_OPERATOR_CLOSURE_REVIEW.md` states
of its Grover work — *"Removing numerical selection does not establish an
asymptotic speedup for this controller or an oracle cost model."* That is the
correct disposition and applies to the whole substrate.

**Also binding:** `claims.yaml` **PROHIBITED** entries
(`p-throughput-eh`, `p-gpu-equivalence`, `p-exponential-speed`) and
`r-lucas-pisot-speedup` **REFUTED**. No exact-execution result may be reported
in terms that touch these.

## 6. Memory bounds

For the semantics to hold, exact execution must declare its resource boundary —
otherwise exactness is bought with an unbounded amplitude table.

**Declared:** a fail-closed cap, already present as `MLA1517_MAX_AMPLITUDES`
(default 2²⁰). Requests beyond the cap are refused, not silently truncated.
The cap is a declared parameter, and `docs/test_voyage_plan.md` and
`tests/test_mining_fault_tolerant_asic.py` families exercise the refusal path.

## 7. The ten-sector evidence and its correct label

`reports/toe_universal_principle_evidence.json` carries per-item
`evidence_class`. The relevant entries:

- `MEASURED` — executed observation, e.g. the covering-radius probe
- `VERIFIED` — per `claims.yaml` §12.8, requires a passing test command, a
  matching artifact hash and a baseline
- `REFUTED` — requires a negative results log

**Rule:** an exact-execution result is filed `MEASURED` unless it meets the full
`VERIFIED` bar. Exactness of arithmetic is not by itself the release gate.

## 8. What this document does not do

No implementation, no tests, no code. Does not rename anything — it declares
which existing object falls under which word. Does not claim device execution
or quantum advantage. No merge, release or mining activation.
`theorem_proven` remains False.

## 9. Next action

Adopt the three-way distinction of §3 and the vocabulary ruling of §4. This is
the lowest-cost closure in the set: it is a wording decision that resolves an
apparent contradiction, and needs no code.
Owner: @EuclidUltimaPhi. Drafting: `pythiaphi`.
