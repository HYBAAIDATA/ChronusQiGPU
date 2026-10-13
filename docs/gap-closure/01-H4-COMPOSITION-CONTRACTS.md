# H4 composition contracts — closure of blocker 3

**Status:** DRAFT — closure specification, not implementation.
**Source of record:** `docs/EXACT_SUBSTRATE_FOUNDATIONS_REVIEW.md` §"Exact-only blockers", item 3.
**Baseline:** `3365bb3c28fe1aeb672e2309556d5979cb8f5d71`.
**Authority:** owner declarations govern (`OWNER_DECLARATIONS.md`). `theorem_proven` remains False.

---

## 0. Scope

This document closes the sub-items of review blocker 3 that are resolvable by
contract specification. It does **not** claim closure of the covering radius,
which remains blocked on an owner decision recorded in §7.

Blockers referenced: `nearest_zphi` discreteness, `z_to_qsqrt5`,
`qsqrt5_to_vec4`, DphiT wiring under `h4_hash_complete`, the Zeckendorf index
decrement, and Cassini verification semantics.

## 1. The defect as stated

The review records, verbatim:

> **H4 composition**: missing `z_to_qsqrt5` and `qsqrt5_to_vec4` contracts;
> DphiT is defined but not actually called by `h4_hash_complete`. Z[phi] is
> dense in its single real embedding, so `nearest_zphi` needs a discrete
> embedding or restricted admissible coefficient set. Supply termination, tie
> rules, zero handling and a rigorously derived covering radius. Sampling
> cannot prove universal coverage. Computing and then discarding F(h) still
> costs Theta(h) output bits for UInt64 h. Cassini verification must compute
> the identity, not merely return its expected sign. The extra Zeckendorf
> index decrement can skip valid terms; existing canonical implementations
> should be reused once integration is designed.

Six sub-items are named. Five close here. The sixth is deferred with its
precondition stated.

## 2. Admissible coefficient set (discreteness)

`Z[φ]` = { a + bφ : a, b ∈ Z }. Its single real embedding φ ↦ (1+√5)/2 is
**dense** in R. A nearest-point search over a dense set has no covering radius:
for any candidate radius r > 0 and any point x, there exist elements of Z[φ]
outside every ball of radius r around x. This is why the review requires
discreteness *before* any radius can be derived.

**Admissible set:**

```
A(B) = { a + bφ : a, b ∈ Z, |a| <= B, |b| <= B }
```

for a declared bound B ∈ N. A(B) is finite, of cardinality (2B+1)².

| Property | Value |
|---|---|
| Cardinality | (2B+1)² |
| Convex hull in the real embedding | the interval [ −B − Bψ, B + Bφ ] |
| Symmetry | closed under conjugation φ ↦ ψ = 1 − φ |
| Contains | Z ∩ A(B) for |n| <= B (b = 0); and φ-powers up to index where coeffs fit |

**Required at the call boundary:** B is an explicit, caller-supplied,
bit-length-limited parameter. Mathematical totality over unbounded B does not
imply bounded service latency (review, "Test evidence and release
limitations"). A default is not admissible; a declared maximum is.

## 3. `z_to_qsqrt5` contract

Maps an exact element of Z[φ] into Q(√5) representation.

```
z_to_qsqrt5(z: Zphi) -> QSqrt5
```

| Field | Type | Constraint |
|---|---|---|
| `p` | int | exact, arbitrary precision |
| `q` | int | exact, arbitrary precision |

**Semantics.** a + bφ = a + b·(1+√5)/2 = ((2a + b) + b√5) / 2.
Two encodings are admissible; the implementer declares which:

- **halved form:** value = (p + q√5)/2 with p = 2a + b, q = b
- **integral form:** value = p + q√5 with p, q ∈ Z[1/2], rejected if p or q
  is non-integral

The canonical choice is **halved form**, because it is total over all of Z[φ]
— every element maps, none is rejected. The integral form is partial and must
not be selected without an admissibility proof.

**Rejection contract.** Rejects: booleans, floats, decimal strings,
`None`, and any input not constructed as a `Zphi`. Mirrors the admission
discipline established in `docs/EXACT_OPERATOR_CLOSURE_REVIEW.md` for
`hilbert._frac`.

**Round-trip law:** for all z ∈ Z[φ], `qsqrt5_to_z(z_to_qsqrt5(z)) == z`.

## 4. `qsqrt5_to_vec4` contract

Maps a Q(√5) element to a 4-coordinate exact vector. Pace the review's
statement that the H4 composition needs this contract; the *specific* vector
it must produce is not fixed by the review and is an owner decision (§7).

```
qsqrt5_to_vec4(q: QSqrt5, ctx: Vec4Context) -> Vec4
```

| Field | Type | Constraint |
|---|---|---|
| `v` | tuple[int, int, int, int] | exact integer coordinates |

**Required properties, whatever the geometric realisation:**
1. **Injectivity on the declared domain.** Distinct inputs produce distinct
   vectors over the declared bound.
2. **Determinism.** No float intermediate at any stage.
3. **Totality over the declared bound.** No input within B raises.

**Open parameter — `Vec4Context`.** The review does not specify the target
4-space. Candidates: the 4 coordinates of a quaternion basis (H4 as the
600-cell lives in the 4-dimensional quaternionic representation), or the 4
integer coefficients of a φ-basis expansion. This selection is a canonical
decision and must be recorded before implementation. Recorded in §7.

## 5. `nearest_zphi` — termination, tie rules, zero handling

With A(B) finite, nearest-point search is a well-posed finite problem.

```
nearest_zphi(x: float_or_exact, B: int) -> Zphi
```

**Termination.** With A(B) finite, brute enumeration terminates in (2B+1)²
candidate evaluations. A branch-and-bound refinement must declare its pruning
rule and prove the pruning never discards the true nearest element; absent such
a proof, enumeration is the admissible default.

**Tie rules.** Declared, not incidental:
- Compare by exact distance; if two elements are equidistant, select the one
  with the **smaller |a|**; if still tied, the **smaller b**; if still tied,
  the **smaller a** (ordering it as an integer, negatives before positives).
- Rationale: total, deterministic, and independent of iteration order.

**Zero handling.** `x = 0` returns `Zphi(0, 0)`. The review records a parallel
requirement for the TOE bridge: *"Zero-state initialization must mean a
normalized basis state, not the zero vector."* That is a different zero and
must not be conflated: `nearest_zphi(0, B)` is an algebraic nearest-element
query and legitimately returns the additive identity of Z[φ].

**Distance metric.** Declared explicitly and used consistently. Exact
comparison of |x − (a + bφ)| requires either an exact representation of x in
Q(√5) or a declared one-way float boundary in the sense of
`kellogg/scales.py:Zphi.to_float()`. Floats must not be promoted back.

## 6. DphiT wiring, the Zeckendorf decrement, and Cassini semantics

**6.1 DphiT under `h4_hash_complete`.** The review states DphiT is defined but
not called. Required: `h4_hash_complete` invokes DphiT on the hashed input
before nearest-element resolution, and the call is on the live path — not
behind a flag, not in a dead branch. Verification is by trace on an executed
input, not by reading the source.

**6.2 The Zeckendorf index decrement.** *"The extra Zeckendorf index decrement
can skip valid terms; existing canonical implementations should be reused once
integration is designed."* Required: remove the local decrement and call the
canonical implementation. Canonical sites, per the universal principle map
§4.2: `kellogg/scales.py:zeckendorf`, `aethel/zeckendorf.py:HardenedZeckendorfCodec`,
`toe/poincare_golden_11d.py:encode_zeckendorf`. The non-adjacency predicate is
the canonical one: `(mask & (mask << 1)) == 0`.

**6.3 Cassini verification semantics.** *"Cassini verification must compute the
identity, not merely return its expected sign."*
Required: `L_n² − 5F_n²` is computed and compared against `4·(−1)ⁿ`; returning
`(−1)ⁿ` or a boolean derived from parity is not verification.
Canonical site: `aethel/cassini.py:CassiniVerifier.verify` — already
machine-checked against the Lean theorem `Guardian.Cassini.cassini`
(`proofs/VERIFICATION.md`), which proves the identity **∀ n**. Any H4-side
check should call this rather than re-derive.

## 7. Deferred sub-item and its precondition

**Covering radius — NOT closed by this document.**

`A(B)` supplies the discreteness the review requires, but the radius itself is
unwritten, and the review is explicit that *"sampling cannot prove universal
coverage."* The 40k-probe `m32_covering_deg` measurement in
`reports/toe_universal_principle_evidence.json` is filed `evidence_class:
MEASURED` and cannot be promoted to a certificate by this route.

Order of operations, forced:

```
admissible set A(B)  ->  B declared and bounded
                     ->  termination + tie rules declared   [§5, done here]
                     ->  covering radius DERIVED            [open]
                     ->  certificate                        [open]
```

**Two owner decisions block the derivation:**

| Decision | Blocks | Options |
|---|---|---|
| `Vec4Context` target space | §4 implementation | quaternionic 4-basis vs φ-basis 4-coefficients |
| Admissible bound B | §2, §5, and the radius | declared maximum, bit-length limited |

Until both are recorded, the covering radius section of any H4 certificate
must remain **empty and explicitly marked awaiting decision**, not filled with
the sampled value.

## 8. What this document does not do

- No implementation. No tests. No code.
- Does not close the covering radius.
- Does not claim universal H4 coverage.
- Does not promote any `MEASURED` result to `VERIFIED`.
- Does not authorize merge, release, deployment or mining activation.

## 9. Next action

Record the two §7 decisions, then derive the radius against `A(B)`.
Owner: @EuclidUltimaPhi (canonical decision). Drafting: `pythiaphi`.
