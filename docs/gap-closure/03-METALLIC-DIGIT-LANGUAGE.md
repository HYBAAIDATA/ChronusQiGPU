# Metallic decomposition — closure of blocker 2

**Status:** DRAFT — closure specification, not implementation.
**Source of record:** `docs/EXACT_SUBSTRATE_FOUNDATIONS_REVIEW.md` §"Exact-only blockers", item 2.
**Baseline:** `3365bb3c28fe1aeb672e2309556d5979cb8f5d71`.

---

## 1. The defect as stated

> **Metallic decomposition**: binary non-adjacent digits are insufficient for n>1.
> For n=3, recurrence weights 1,3,10,... cannot represent 2 with binary digits.
> Approve an Ostrowski/generalized digit language and prove uniqueness first.

The metal `mu_n` satisfies `mu_n² = n·mu_n + 1`. The existing module
`chronus/metallic.py` implements `a + b·mu_n` with exact integer coefficients,
nonnegative powers, conjugate and norm. Its review-recorded outstanding scope:
*"generalized legal digit language; negative powers and rational coefficients."*

## 2. Why binary digits fail

Recurrence weights for n = 3 are 1, 3, 10, 33, 109, … (`w_k = 3w_{k-1} + w_{k-2}`
with seeds 1, 3). The smallest gap between adjacent weights is 2 (between w_0 = 1
and w_1 = 3), yet the weight w_1 = 3 exceeds the gap. Therefore **2 is
unrepresentable** in {0,1} digits over these weights: 2 < 3 and 2 is not in
the span of {1}. The failure is structural, not an edge case: for every n >= 2,
w_1 = n >= 2, and the value 2 is representable only if n <= 2.

**Conclusion:** a binary ({0,1}) non-adjacent digit language is admissible only
for n <= 2. For n >= 3 a *generalized* digit language is required.

## 3. The admissible digit language — Ostrowski

Given the recurrence weights w_0 < w_1 < w_2 < … for the chosen metal n, any
nonnegative integer has an **Ostrowski representation** with respect to the
associated numeration system.

**Declared alphabet.** For each position k, the admissible digit set is

```
D_k = { 0, 1, ..., n_k }
```

where n_k is the ratio bound implied by the recurrence: for a metal-n sequence
obeying `w_k = n·w_{k-1} + w_{k-2}`, the admissible digit at position k is
bounded by **n** (the metallic parameter), not by 1.

| Position k | Weight w_k (n=3) | Admissible digits |
|---|---|---|
| 0 | 1 | 0..3 |
| 1 | 3 | 0..3 |
| 2 | 10 | 0..3 |
| 3 | 33 | 0..3 |

Under this alphabet the failing case resolves: 2 = 2·w_0, a single digit of
value 2 at position 0.

## 4. Legality and non-adjacency

With a generalized alphabet, the naive binary non-adjacency rule becomes
insufficient. The declared legality predicate:

```
legal(digits)  iff  ( max k such that d_k > 0 ) is well-formed
                and  for consecutive positions j = k-1:
                     d_k <= n  and  d_{k-1} <= n
                and  d_k · w_k + d_{k-1} · w_{k-1} < w_{k+1}
```

The final inequality is the **greedy-remainder condition**: a legal
representation never carries enough weight at two adjacent positions to
overflow into the next weight. This is the generalized analogue of binary
non-adjacency.

**For n = 1** the predicate reduces to `d_k, d_{k-1} ∈ {0,1}` with
`d_k·w_k + d_{k-1}·w_{k-1} < w_{k+1}` — which is exactly Zeckendorf
non-adjacency. The generalization is therefore consistent at n = 1 and must
be shown to coincide with the canonical Zeckendorf predicate there.
Canonical predicate, per universal principle map §4.3:
`(mask & (mask << 1)) == 0`.

## 5. The proof obligation — stated first, as required

The review requires this **before** implementation: *"Approve an
Ostrowski/generalized digit language and prove uniqueness first."*

**Uniqueness obligation, metallic case.** For every nonnegative integer v and
every admissible metal n >= 1, there exists **exactly one** legal digit string
representing v in the alphabet §3 under the legality predicate §4.

Status of this obligation at the baseline:
- `proofs/VERIFICATION.md` lists **Zeckendorf uniqueness** as explicitly
  *"not proved in Lean and not claimed."*
- The machine-checked Lean results are `Guardian.Cassini.cassini` (∀ n),
  `Guardian.Zeckendorf.encodeIdxs_correct` (∀ n), and
  `Guardian.Zeckendorf.encodeFuel_nonAdjacent` (∀ n).

Note the precise boundary: `encodeIdxs_correct` and `encodeFuel_nonAdjacent`
establish that **the codec's encoding is correct and non-adjacent**. They do
**not** establish uniqueness of the representation. The metallic generalization
cannot claim uniqueness while the narrower n = 1 case does not.

**Order of operations, forced:**

```
n = 1 uniqueness proved            [open — the narrower case]
        |
metal-n uniqueness proved          [open — depends on the above]
        |
digit language implemented         [blocked until both above]
```

Proving uniqueness for n >= 3 while leaving n = 1 open would be a stronger
claim resting on a weaker one, and is not admissible.

## 6. Contract surface (deferred until §5 clears)

```
metallic_digits(v: int, n: int) -> list[int]
metallic_value(digits: list[int], n: int) -> int
```

| Field | Type | Constraint |
|---|---|---|
| `v` | int | >= 0, arbitrary precision |
| `n` | int | >= 1, the metallic parameter |
| `digits` | list[int] | each in 0..n, legality predicate §4 |

**Round-trip law:** `metallic_value(metallic_digits(v, n), n) == v` for all
admissible v, n.
**Uniqueness law:** `metallic_digits(v, n)` is the only legal string with that
value — the §5 obligation, restated as a callable contract.

**Rejection contract.** Rejects booleans, floats, decimal strings, negative v,
and n < 1. `chronus/metallic.py` already rejects booleans, floats and invalid
domains explicitly; the new surface must match.

## 7. Negative powers and rational coefficients

The review records these as outstanding for `chronus/metallic.py`. They are
**out of scope** for this document: they require the full metallic field
`Q(mu_n)`, not the integer ring, and the uniqueness argument in §5 does not
extend to a field without a separate treatment.

Recorded as a follow-on blocker, not closed here.

## 8. What this document does not do

No implementation, no tests, no code. Does not claim uniqueness. Does not
extend to negative powers. No merge, release or mining activation.
`theorem_proven` remains False.

## 9. Next action

Approve the alphabet of §3 and the legality predicate of §4, then nominate the
n = 1 uniqueness proof as the first formal target — it is the prerequisite for
the metallic case, and it is currently unproved.
Owner: @EuclidUltimaPhi. Drafting: `pythiaphi`.
