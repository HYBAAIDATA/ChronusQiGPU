# Turing structural-research claim gates

**Status:** research specification; not production evidence  
**Claim posture:** define → implement → falsify → benchmark/prove → promote  
**Default:** `theorem_proven = false`, `measured_qpu = false`

This document is the claim boundary for four proposed Turing research directions:

1. FoldGap: measuring description-length reduction from an explicit fold;
2. orbit collapse beyond the stabilizer frontier;
3. a Pisot-indexed transform benchmarked against the cyclic QFT;
4. the meaning and justification of the repository's `11D` construction.

The governing rule is simple: **large claims are settled by theorem or benchmark, not by names.** No statement in this document promotes a research direction to a production capability. The machine-readable status lives in `docs/turing_structural_research_gates.json`.

## 0. Vocabulary and non-claims

Turing must distinguish mathematical objects that are often collapsed into one rhetorical label.

- **Gottesman–Knill / stabilizer simulation** is an exact, efficient description of the Clifford/stabilizer class. Turing does not "refute" it. A stronger Turing claim would have to exhibit a precisely defined state/circuit family outside that class which Turing evaluates exactly and efficiently on a declared representation.
- **Shannon entropy is not wrong.** It is an ensemble quantity attached to a declared source distribution, and source-coding theorems constrain expected code length under their hypotheses. Per-instance structural compression is a different question and must account for the model/decoder used to exploit structure.
- **Kolmogorov complexity** is a theoretical per-object notion and is not computable in general. Repository receipts therefore must report concrete encoded lengths under named, replayable codecs rather than claiming to have measured `K(x)`.
- **QFT/Fourier methods remain canonical** where the relevant symmetry is cyclic/abelian. A Pisot-indexed transform is a proposed alternative for a declared structured workload, not a replacement by vocabulary.
- **Poincaré, Ricci, Yang–Mills, and 11D** are not interchangeable labels. Any use of them must name the mathematical object, equation, domain, and evidence class.

Two corrections are normative for future text:

- Fibonacci anyons are associated with the Fibonacci category, commonly realised in the `SU(2)_3` setting; do not label them `SU(2)_2`.
- `phi = (1 + sqrt(5))/2` is a quadratic Pisot unit, but it is **not** the smallest Pisot number. Exact arithmetic in Turing must come from an explicitly represented algebraic number field/ring and exact algorithms; the Pisot property alone does not make floating-point arithmetic exact.

---

# 1. FoldGap — a receipt-level structural compression metric

## 1.1 What is being measured

The useful idea is not "beating Shannon". It is measuring how many bits a named, reversible structural model removes relative to a named baseline representation.

For an individual execution object `x`, define the auditable receipt metric

```text
FoldGap_bits(x; B, F) = L_B(x) - L_F(x)
```

where:

- `B` is a declared baseline codec/representation;
- `L_B(x)` is the exact number of bits emitted by `B` for `x`;
- `F` is the declared folded representation plus the information required to reconstruct `x` under the stated accounting policy;
- `L_F(x)` is the exact number of charged bits in that folded description.

Also report:

```text
FoldGain_ratio = L_B(x) / L_F(x)              # only when L_F(x) > 0
FoldSavings_pct = 100 * FoldGap_bits / L_B(x) # only when L_B(x) > 0
```

A receipt must identify whether decoder/model cost is:

- charged per object;
- amortised across a declared cohort; or
- fixed by a versioned protocol already shared by both sides.

No result is comparable unless that accounting policy matches.

## 1.2 Shannon-facing metric

If a source model `P` is explicitly declared, Turing may additionally record:

```text
self_information_bits(x; P) = -log2 P(x)
```

and, over a cohort sampled from a declared source,

```text
H(P) = E_P[-log2 P(X)]
expected_fold_gap = E[L_B(X) - L_F(X)]
```

`H(P)` is an ensemble baseline, not the literal bit length of one execution object. A per-receipt field must therefore not write `H(x)` unless the schema defines exactly what distribution and estimator that symbol denotes.

## 1.3 Required receipt fields

A future FoldGap receipt must bind at least:

```text
object_digest
baseline_codec_id
baseline_codec_version
baseline_bits
fold_codec_id
fold_codec_version
folded_bits
model_cost_bits
decoder_cost_policy
fold_gap_bits
fold_gain_ratio
lossless_reconstruction
reconstructed_digest
benchmark_corpus_id
```

The fold is accepted as **lossless** only when replay reconstructs an object whose canonical digest equals `object_digest`.

## 1.4 Promotion gate

No production claim such as "compression beyond Shannon", "information below entropy", or "Shannon was wrong" is permitted.

Promotion requires a benchmark corpus, codec definitions, exact bit accounting, replayable reconstruction, and comparison against appropriate general-purpose and structure-aware baselines. The publishable claim is then workload-scoped, e.g.:

> On corpus C under accounting policy A, fold F reduced the measured encoded description by N bits relative to baseline B, with bit-exact replay.

That claim is stronger because it is directly auditable.

---

# 2. Orbit collapse and the stabilizer frontier

## 2.1 Existing floor

The stabilizer formalism is an exact representation of stabilizer states and Clifford evolution. Turing's tableau backend already treats that class as a first-class exact state class. Nothing in this research programme weakens that fact.

The target research statement is instead:

> There exists a declared non-stabilizer family `S` with an exact compact representation derived from a finite/algebraic symmetry action, for which Turing's representation and operations are exact and asymptotically or empirically more efficient than dense state-vector simulation on the supported domain.

This statement is currently **unproven**.

## 2.2 Group action

For a finite group `G` acting on a state family `S`, define

```text
G × S -> S
(g, psi) -> g · psi
Orbit(psi) = { g · psi : g in G }
Stab(psi) = { g in G : g · psi = psi }
```

An "orbit collapse" representation is legitimate only if Turing provides a lossless map

```text
psi <-> (canonical_orbit_representative, orbit_coordinate, residual_data)
```

and proves or exhaustively verifies on the supported finite domain that decoding recovers the exact state, including relative phase.

The phrase "the orbit is the fold" is therefore an implementation hypothesis, not yet a theorem.

## 2.3 Icosahedral/dodecahedral vocabulary

If used, name the exact group and representation:

- `H3`: the rank-3 non-crystallographic Coxeter group with icosahedral symmetry;
- `H4`: the rank-4 non-crystallographic Coxeter group associated with 4D golden-ratio geometry such as the 600-cell.

A circuit/state does not gain compression merely because an icosahedron or dodecahedron is named. The code must specify the action of the group on the state representation and the invariant(s) that make orbit quotienting lossless.

Golden-ratio/quasicrystalline analogies may motivate candidate transforms, but the exact projection, lattice/module, action, and reconstruction law must be written down before they become capability claims.

## 2.4 Strict-extension falsification test

A claim that a folded family **strictly exceeds the stabilizer class** requires one worked witness satisfying all of:

1. prove or independently certify that the state/circuit is outside the stabilizer cone/class;
2. execute it through the proposed folded backend without dense fallback;
3. reconstruct or query the result exactly on the declared domain;
4. compare tractable instances against an independent exact dense reference;
5. compare the Clifford overlap against Stim or another trusted stabilizer reference;
6. report time and memory against dense and stabilizer references where both are meaningful;
7. record every discrepancy, including zero-discrepancy seeds.

A reference simulator "choking" is not itself evidence of scientific correctness. The meaningful claim is exactness plus a measured resource advantage on a declared family/domain.

## 2.5 Promotion gate

Until such a witness exists:

```text
strictly_exceeds_stabilizer = false
orbit_collapse_theorem_proven = false
production_claim_allowed = false
```

---

# 3. Pisot-basis machine and transform benchmark

## 3.1 The precise algebraic basis

A Pisot number is a real algebraic integer greater than 1 whose other Galois conjugates have modulus strictly less than 1.

The golden ratio satisfies

```text
phi^2 - phi - 1 = 0
conjugate(phi) = 1 - phi = -1/phi
abs(conjugate(phi)) < 1
```

so `phi` is a quadratic Pisot unit.

This property is relevant to self-similarity and near-integer behaviour of powers, but **does not by itself make a numerical implementation exact**. Exact Turing operations must identify their number field/ring (for example `Q(sqrt(5))`, `Z[phi]`, or another declared algebraic extension), canonical representation, normalization law, and equality algorithm.

Zeckendorf numeration is the canonical Fibonacci representation for integers. Ostrowski numeration generalises continued-fraction-based numeration for irrational slopes; it must not be described as "Zeckendorf in any Pisot base" without a proved construction for the base in question.

## 3.2 Candidate Pisot-indexed transform

The proposed research object must be defined as an actual transform, not a name. A minimum specification is:

```text
input space
output space
index set / module
kernel K(j, k)
normalisation
inverse transform
exactness domain
complexity model
```

If the transform is claimed to be a quantum/unitary transform, additionally prove

```text
T† T = I
```

on the declared finite domain using exact arithmetic or a formal proof artifact. Approximate numerical orthogonality cannot satisfy an `EXACT` capability.

## 3.3 Fourier/QFT baseline

The cyclic QFT remains the control:

```text
QFT_N |x> = 1/sqrt(N) * sum_k exp(2 pi i x k / N) |k>
```

The Pisot transform earns a separate capability only by beating a relevant cyclic/Fourier baseline on a workload that actually has the proposed aperiodic/Pisot structure.

Candidate benchmarks include:

- diagonalisation error/resource cost for a declared Fibonacci/Pisot-indexed operator;
- phase estimation on a declared Fibonacci lattice/module;
- convergence or query count for a Grover-like iterate whose spectrum is provably adapted to the Pisot basis;
- exact reconstruction and transform-domain sparsity on a versioned structured corpus.

Report both wins and losses. A transform that is better only on one structured family is still useful; it need not replace Fourier globally.

## 3.4 Promotion gate

Until definition, inverse, exactness proof/tests, and comparative benchmark exist:

```text
pisot_transform = RESEARCH_ONLY
supersedes_qft = false
fourier_retired = false
production_claim_allowed = false
```

---

# 4. What `11D` means in this repository

## 4.1 Current executable meaning

The repository currently implements an 11-coordinate real vector geometry in `toe.poincare_golden_11d`:

```text
x in R^11
||x||_phi^2 = sum_{i=0}^{10} phi^{-(i+1)} x_i^2
B_phi^11 = { x : ||x||_phi^2 < 1 }
```

with a Klein/Poincaré-style contraction into that open weighted ball.

Therefore, in current executable vocabulary, **11 counts coordinates in a software-defined weighted manifold representation.** It is not, by that fact alone:

- eleven spacetime dimensions;
- an M-theory claim;
- eleven physical degrees of freedom;
- eleven hardware qubits;
- a theorem that eleven is optimal;
- a universal quantum width.

Separately, the repository also contains `VIRTUAL_QUANTUM_QUBITS = 11` as a default execution/lane width. That constant is not evidence that the manifold dimension and the qubit default have a common mathematical derivation.

## 4.2 The unanswered question: why eleven?

The code defines eleven coordinates; it does not yet establish that eleven is necessary or optimal for the proposed fold.

A theoretical significance claim therefore requires one of:

- a derivation from the rank/dimension of an invariant space;
- a minimal sufficient-statistic argument;
- an exact representation theorem;
- an independent physical theory mapping (if a physical claim is actually intended);
- or an empirical model-selection result showing that dimension 11 is selected by a predeclared criterion.

The engineering benchmark should include dimensional ablations around 11 (for example 4, 8, 10, 11, 12, 16 where meaningful) and report reconstruction error, FoldGap, runtime, memory, and downstream task quality under identical accounting.

Until then the only allowed wording is equivalent to:

> `11D` denotes the eleven-coordinate `B_phi^11` software manifold used by this implementation; the choice of eleven is a research parameter whose optimality/theoretical necessity is not yet established.

## 4.3 Poincaré / Ricci / Yang–Mills boundary

The repository already contains multiple mathematical objects carrying these names. They must remain separated.

A future Ricci-flow claim must specify a metric `g(t)` and evolution equation, normally of the form

```text
∂g/∂t = -2 Ric(g)
```

or an explicitly named modified flow. A scalar called `ricci` is not a Ricci flow.

A future Yang–Mills claim must specify the gauge group, base manifold, connection/field, action/operator, boundary conditions, and whether the result is finite/discrete or continuum. A finite-model spectral gap must never be promoted to the continuum Yang–Mills mass-gap claim.

Likewise, the Poincaré homology sphere and an 11D hyperbolic/Poincaré ball are distinct spaces and must never be merged because they share a name.

---

# 5. Cross-cutting evidence contract

Every one of the four research gates must carry:

```text
claim_id
status
implementation_ref
exactness_class
state_class
supported_domain
reference_implementation
benchmark_spec
benchmark_artifacts
proof_artifacts
theorem_proven
measured_qpu
limitations
production_claim_allowed
```

Allowed statuses are:

```text
SPECIFIED
IMPLEMENTED_UNVERIFIED
FALSIFIED
BENCHMARKED
PROVEN
EVIDENCED
UNAVAILABLE
```

A benchmark result may justify `BENCHMARKED`; it does not automatically justify `PROVEN`. A proof artifact may justify `PROVEN`; it does not automatically establish a runtime performance advantage. `EVIDENCED` requires all evidence demanded by the particular external claim.

## Promotion rule

A research claim may enter the production capability matrix only when:

1. its machine-readable gate names the exact implementation;
2. all required falsification tests pass on the declared domain;
3. all reference discrepancies are explained;
4. receipts/replay bind the result to code and inputs;
5. the wording is no stronger than the evidence;
6. `theorem_proven` and `measured_qpu` remain false unless their independent evidence contracts are satisfied.

Until then, these are research programmes, not product features.
