# Quantum arsenal embedding — closure of blocker 4

**Status:** DRAFT — closure specification, not implementation.
**Source of record:** `docs/EXACT_SUBSTRATE_FOUNDATIONS_REVIEW.md` §"Exact-only blockers", item 4.
**Baseline:** `3365bb3c28fe1aeb672e2309556d5979cb8f5d71`.

---

## 1. The defect as stated

> **Quantum arsenal**: 32 real amplitudes cannot represent 120 indexed vertices
> or general complex states. A 120-dimensional logical space or an explicit
> 128-dimensional qubit embedding is required, with all operator behavior defined.
> Continuous exp(-iHt) at generic algebraic times has transcendental entries;
> the proposed algebraic field is not closed under it. Use a certified symbolic
> functional calculus or an approved exact discrete gate/phase domain, not floats.
> Mean mixing, gradient descent and golden-section search are classical/nonunitary;
> no quantum relabeling is acceptable. VQE and QAOA also require an explicit
> optimization contract; exact circuit arithmetic does not remove variational search.

Four distinct defects. Each is addressed separately.

## 2. Dimensional insufficiency

The 600-cell has **120 vertices** (universal principle map §8: V=120, E=720,
F=1200, C=600, Euler=0). The substrate's octet is identified as a 32-dimensional
Hilbert space (`kellogg/quantum_tensor.py:QuantumState`, map §9.1). The
dimension is the source, not the trivial gap: a state indexed by H4 vertices
needs 120 amplitudes. Thirty-two real components can represent neither 120
indexed vertices nor a general complex state on 120 vertices.

**Two candidate resolutions, both requiring an owner choice:**

| Option | Space | Amplitudes | Exactness trade |
|---|---|---|---|
| **A — 120-dim logical** | 120 complex | 240 reals | Logical only; not a qubit count. No canonical gate set acts on it |
| **B — 128-dim qubit embedding** | 2⁷ = 128 | 256 reals | Admits a qubit gate set; 8 qubits; 8 amplitudes unused or reserved |

**Option B is recommended** on one ground: a qubit embedding has a defined
gate set, and the review requires *"all operator behavior defined."* Option A
has no canonical operator family — a 120-dimensional space admits unitaries but
not a named, certified gate algebra. Option B also aligns with the review's own
wording, which lists it explicitly.

**Required either way:** the embedding map `H4 vertex index -> basis index`
is declared, injective, and its image is stated. The 8 spare dimensions in
Option B are declared reserved, not silently zero.

## 3. `exp(-iHt)` closure — the field does not close

At generic algebraic t, `exp(-iHt)` has transcendental entries. The proposed
exact algebraic field is not closed under the exponential map. This is a
mathematical fact, not an implementation gap: no amount of exact arithmetic
makes a transcendental number algebraic.

**Two admissible resolutions:**

**3.1 Certified symbolic functional calculus.** Keep `exp(-iHt)` symbolic;
evaluate only at committed times; carry a certificate of the evaluation method.
Admissible when the operator family is small and diagonalisable with known
spectrum — which is the case for the 2I quantum-group Laplacian, whose
spectrum is the Casimir spectrum (map §8, character table: 9 irreps,
dims [1,2,2,3,3,4,4,5,6], Σd²=120).

**3.2 Exact discrete gate/phase domain.** Restrict evolution to a discrete set
of certified phases, so every reachable operator is exactly representable. The
existing exact substrate is already in this shape:
`kellogg/exact_tensor.py:ExactTOETensor` — Clifford+T over Q(√2) + iQ(√2) with
Fraction amplitudes, fail-closed gates, deterministic Born weights.

**3.2 is recommended**, because the machinery exists and is tested. The review's
own boundary is respected: *"Use a certified symbolic functional calculus or an
approved exact discrete gate/phase domain, not floats."*

**Explicitly inadmissible:** float evaluation of `exp(-iHt)`, or any route that
computes in float and re-labels the result exact.

## 4. Classical operators must not carry quantum labels

Named by the review: **mean mixing**, **gradient descent**, **golden-section
search**. These are classical, nonunitary procedures. *"No quantum relabeling
is acceptable."*

**Required disposition for each:**

| Procedure | True classification | Admissible role |
|---|---|---|
| Mean mixing | classical, nonunitary | classical control; label as such |
| Gradient descent | classical, nonunitary | classical optimisation |
| Golden-section search | classical, nonunitary | classical 1-D search |

Each may remain in the system as a classical component. None may be described
as a quantum operator, a quantum gate, or a quantum algorithm. The label
*"quantum"* attaches to exact unitary evolution and exact measurement only.

**Existing precedent to follow:** `docs/EXACT_OPERATOR_CLOSURE_REVIEW.md`
records that *"Existing QAOA/VQE grid scans are classical control over exact
evaluations; this patch does not relabel them as globally exact optimization."*
That is the correct disposition and should be applied to the three named
procedures.

## 5. VQE / QAOA — the optimisation contract

The review's point: *"exact circuit arithmetic does not remove variational
search."* A variational algorithm has two parts — an exact circuit evaluation
and a classical search over parameters. Making the first exact does not make
the second exact.

**Declared contract:**

```
variational_contract(
  ansatz,                  # exact circuit family
  parameter_domain,        # declared, bounded
  classical_optimiser,     # named, with its own convergence claim
) -> VariationalResult
```

| Field | Constraint |
|---|---|
| `parameter_domain` | bounded and declared; unbounded search is not admissible |
| `classical_optimiser` | named, and its convergence property stated separately |
| `VariationalResult` | carries circuit exactness AND optimiser convergence as **two distinct** claims |

**The rule:** the result must never report a single "exactness" field covering
both. Circuit exactness is a theorem about the ansatz. Optimiser convergence is
a property of the classical method. Conflating them is the defect the review
names.

**Existing artifacts:** `quantum_compute_substrate/variational_eigensolver.py`
and the QAOA family regressions (`14 passed`, per
`docs/EXACT_OPERATOR_CLOSURE_REVIEW.md`) are exact-evaluation components. The
optimiser half is unclaimed.

## 6. The ten methods — honest disposition

The reviewed ten: tunnelling, annealing, swarming, superposition,
precompute, collapse, Grover, VQE, QAOA, phi-structured search.

| Method | Presence at baseline | Disposition |
|---|---|---|
| Superposition | `kellogg/quantum_tensor.py` | exact, bound |
| Collapse | `born_probabilities` | exact; Born sampling stochastic — separate distribution from outcome (review item 5) |
| Grover | `grover_search.py`, `test_a_grover_exact.py` | exact; first-peak contract certified in `EXACT_OPERATOR_CLOSURE_REVIEW.md` |
| VQE | `variational_eigensolver.py` | circuit exact; optimiser contract open (§5) |
| QAOA | present in quantum-library family | as VQE (§5) |
| Phi-structured search | φ-resonance R_φ (map §8.2) | present; label as structured search, not a quantum speedup |
| Tunnelling | **0 hits** | absent — declared, not implemented |
| Annealing | **0 hits** | absent — declared, not implemented |
| Swarming | **0 hits** | absent — declared, not implemented |
| Precompute | **0 hits** | absent; note `docs/M32_TENSOR_BRIDGE.md` §6 declares O(1) precompute + O(1) submit for the *TypeScript* bridge, which that document states is **not in this repository** |

**Four of the ten have no implementation.** This must be stated as absence, not
as pending readiness. Declaring them canonical requirements is an owner
decision; implementing them is separate work.

## 7. What this document does not do

No implementation, no tests, no code. Does not claim quantum advantage
(`claims.yaml` lists `p-exponential-speed` as **PROHIBITED**). No merge,
release or mining activation. `theorem_proven` remains False.

## 8. Next action

Record the §2 dimensional choice (A or B), the §3 evolution domain, and the
§6 disposition of the four unimplemented methods. Then the embedding map is
the first artifact.
Owner: @EuclidUltimaPhi. Drafting: `pythiaphi`.
