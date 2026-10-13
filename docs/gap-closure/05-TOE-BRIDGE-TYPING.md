# TOE bridge typing — closure of blocker 5

**Status:** DRAFT — closure specification, not implementation.
**Source of record:** `docs/EXACT_SUBSTRATE_FOUNDATIONS_REVIEW.md` §"Exact-only blockers", item 5.
**Baseline:** `3365bb3c28fe1aeb672e2309556d5979cb8f5d71`.

---

## 1. The defect as stated

> **TOE bridge**: return a typed state, measurement distribution/outcome, or metric,
> not an untyped State after every primitive. Born sampling is stochastic. Separate
> deterministic exact distributions from outcome generation and randomness provenance.
> Zero-state initialization must mean a normalized basis state, not the zero vector.
> No evidence proves all possible frontend grammars are universally computable.

Four defects: untyped returns, unseparated stochasticity, zero-vector
initialisation, and an unproved universality claim.

## 2. Typed returns

At baseline, primitives return an untyped `State`. The consumer cannot
distinguish a post-evolution state from a measurement distribution from a
scalar metric by type.

**Declared return taxonomy:**

```
EvolvedState      | state vector after exact unitary evolution
MeasurementDistribution | exact probabilities P(k) = |alpha_k|^2, rational
MeasurementOutcome | a single sampled index, plus provenance
Metric            | a scalar or structured observable value
```

| Primitive | Returns |
|---|---|
| `compile_operator` | `OperatorSpec` (already typed; unchanged) |
| encode | `EvolvedState` |
| evolve | `EvolvedState` |
| measure (distribution) | `MeasurementDistribution` |
| measure (outcome) | `MeasurementOutcome` |
| expectation | `Metric` |

**Rule:** no primitive returns a bare `State`. Each returns the type above, and
the type is the contract.

## 3. Deterministic distribution vs stochastic outcome

The review: *"Born sampling is stochastic. Separate deterministic exact
distributions from outcome generation and randomness provenance."*

This is the sharpest defect of the four, because a deterministic object and a
stochastic object are being returned through the same shape.

**`MeasurementDistribution`** — deterministic, exact, rational.
- Content: the tuple P(k) = |alpha_k|² over k, in exact rational arithmetic.
- Property: pure function of the input state. No RNG. Recomputable bit-for-bit.

**`MeasurementOutcome`** — stochastic, carries provenance.

```
MeasurementOutcome(
  index: int,              # the sampled basis index
  method: str,             # named sampling method
  seed_or_entropy: bytes,  # declared randomness source
  distribution_digest: hex # binds the outcome to the distribution it drew from
)
```

| Field | Constraint |
|---|---|
| `index` | within the state's dimension |
| `method` | named; not "default" or implicit |
| `seed_or_entropy` | declared source; reproducing it reproduces the outcome |
| `distribution_digest` | the exact distribution the draw used |

**The rule:** an outcome never stands alone. It carries the distribution it
came from and the entropy that produced it, so a consumer can always separate
"what the theory says" from "what this run drew."

**Admissibility:** the exact distribution may be reported as a claim.
The outcome may be reported only with provenance attached. Reporting an outcome
as if it were a distribution is the error the review names.

## 4. Zero-state initialization

The review: *"Zero-state initialization must mean a normalized basis state, not
the zero vector."*

The zero vector is not a quantum state — it has norm 0 and cannot be
normalised. Any code path returning it under the name "initial state" produces
an object that will fail later at a normalization check, or worse, silently
produce all-zero probabilities.

**Declared:** initialisation produces `|0...0>` — the normalized basis state at
index 0.

| | Admissible | Inadmissible |
|---|---|---|
| Initial state | `alpha_0 = 1`, all others `0`, norm 1 | all `alpha_k = 0`, norm 0 |

**Boundary note.** This is a different zero from `nearest_zphi(0, B)` in
`01-h4-composition-contracts.md` §5, which legitimately returns the additive
identity of Z[φ]. The two must not be conflated: one is a state-space
initialisation, the other an algebraic nearest-element query.

**Existing guard:** `assert_normalized` / `verify_unitary` were repaired in
`docs/EXACT_OPERATOR_CLOSURE_REVIEW.md` to raise explicitly under `python -O`.
That repair covers the detection path; this contract covers the construction
path.

## 5. Frontend universality — the claim must be withdrawn

The review: *"No evidence proves all possible frontend grammars are
universally computable."*

The canonical map §12 names **Layer 11 — The 10,000 Frontend Problem Forms**,
and §18.4 records **ten sectors exercised**. Neither is a proof of universality
over all grammars:

- 10,000 *forms* is an enumerated catalog, not a closed class.
- 10 *sectors exercised* is an empirical set, not a completeness proof.
- The map's own Layer 15 distinguishes *domain adapters* from *problem forms* —
  a frontend arrives via an adapter, so the claim is bounded by the adapters
  that exist.

**Declared disposition:** the claim is **bounded, not universal**.

```
Admissible:   "the backend computed the N frontend forms in the catalog,
               as exercised in reports/toe_universal_principle_evidence.json"
Inadmissible: "the backend computes any frontend" / "all possible frontend
               grammars are universally computable"
```

The distinction matters for a readiness report: the first is a measured claim
about a catalog, the second is a theorem that has not been proved.

## 6. What this document does not do

No implementation, no tests, no code. Does not prove frontend universality —
it withdraws the claim instead. No merge, release or mining activation.
`theorem_proven` remains False.

## 7. Next action

Adopt the return taxonomy of §2, the distribution/outcome separation of §3,
and the bounded frontend wording of §5. The typing change is the first
artifact; the wording change is immediate and needs no code.
Owner: @EuclidUltimaPhi. Drafting: `pythiaphi`.
