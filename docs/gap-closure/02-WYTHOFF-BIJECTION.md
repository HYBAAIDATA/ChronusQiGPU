# Wythoff bijection — closure of blocker 1

**Status:** DRAFT — closure specification, not implementation.
**Source of record:** `docs/EXACT_SUBSTRATE_FOUNDATIONS_REVIEW.md` §"Exact-only blockers", item 1.
**Baseline:** `3365bb3c28fe1aeb672e2309556d5979cb8f5d71`.

---

## 1. The defect as stated

> **Wythoff bijection**: the supplied formula gives W(0,1)=W(1,0)=1. Specify the
> intended standard array, row seeds and indexing before implementing the inverse.
> Beatty floors must use exact integer/algebraic comparisons, not PHI_INV decimals.

Two defects: a **collision** in the supplied formula (two distinct index pairs
mapping to the same value), and **float use in Beatty floors**.

No implementation exists in the repository at this baseline. `Wythoff` returns
zero hits across `claims.yaml`, `UNIVERSAL_PRINCIPLE_MAP.md`, and the tree.
This is a specification gap, not a code defect.

## 2. The canonical Wythoff array — declared

The **Wythoff array** (standard, as in Morrison's and OEIS A035513):

```
Row seeds:  (1, 2), (4, 7), (6, 10), (9, 15), (12, 20), ...
Row r:  W[r][0] = a_r,  W[r][1] = b_r,  W[r][k] = W[r][k-1] + W[r][k-2]
```

The row seeds are determined by the complementary Beatty sequences:

```
a_n = floor(n · φ)      b_n = floor(n · φ²) = a_n + n
```

The pairs (a_n, b_n) are the **Wythoff pairs**; the complementary Beatty
theorem guarantees {a_n} and {b_n} partition the positive integers.

**Indexing — declared:**
- Rows are 1-based: row 1 has seed (1, 2).
- Columns are 1-based: column 1 holds a_n, column 2 holds b_n.
- W(r, c) denotes row r, column c.
- The array is read as a sequence in **antidiagonal** order.

| r \ c | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| 1 | 1 | 2 | 3 | 5 | 8 |
| 2 | 4 | 7 | 11 | 18 | 29 |
| 3 | 6 | 10 | 16 | 26 | 42 |
| 4 | 9 | 15 | 24 | 39 | 63 |

## 3. Why the supplied formula collides

The colliding formula `W(0,1) = W(1,0) = 1` arises from a 0-based row/column
convention with no seed separation: row 0 and row 1 both reduce to the same
recurrence initialisation. The defect is **not** in the Wythoff construction —
it is in the indexing convention.

**Resolution:** the 1-based convention of §2 has distinct seeds (1,2) and
(4,7) at rows 1 and 2, and the collision cannot occur. The bijection
W: N × N → N is then well-defined as the standard array positions under
antidiagonal reading.

**Required proof obligation before implementation:** the antidiagonal read is a
bijection onto the positive integers, with no value appearing twice and none
omitted. This is a proof, not a test. Sampling cannot establish it — the same
standard the review applies to the covering radius.

## 4. Beatty floors — exact only

Declared inadmissible: `math.floor(PHI_INV * n)`, `int(n / PHI)`, or any
expression where φ or φ⁻¹ appears as a binary float. The review names this
directly: *"not PHI_INV decimals."*

**Admissible formulations, in order of preference:**

1. **Exact algebraic comparison.** a_n = floor(nφ) iff
   `n·(2a_n + n) <= 5·a_n² < n·(2a_n + 2n)`, i.e. an integer-only predicate
   in the ring Z[√5]. No float appears at any stage.
2. **Complementarity.** Compute a_n by exact integral recurrence where
   possible; obtain b_n = a_n + n and use the complementary-Beatty property to
   verify rather than recompute.
3. **Wythoff pair recurrence.** a_{n+1} and b_{n+1} derived from the
   differences between consecutive Wythoff pairs, entirely in integers.

Method 1 is canonical: it reduces the floor to a pair of integer inequalities
and cannot be defeated by rounding.

## 5. Inverse contract

```
wythoff_inverse(value: int) -> (row: int, col: int)
```

| Field | Type | Constraint |
|---|---|---|
| `row` | int | >= 1, 1-based per §2 |
| `col` | int | >= 1, 1-based per §2 |

**Rejection contract.** Rejects booleans, floats, decimal strings, negatives
and zero. Admission discipline mirrors `hilbert._frac` per
`docs/EXACT_OPERATOR_CLOSURE_REVIEW.md`.

**Round-trip law:** for all (r, c) in the declared domain,
`wythoff_inverse(wythoff(r, c)) == (r, c)`.
**Coverage law:** for every positive integer v, `wythoff_inverse(v)` is
defined — the bijection is total, so the inverse must be total. Any partiality
is a defect, not a domain restriction.

## 6. Declared verification standard

- **Proved:** bijectivity over N × N; totality of the inverse.
- **Not claimed:** any asymptotic or throughput property. Sampling and finite
  round-trips corroborate the contract; they do not prove bijectivity.

## 7. What this document does not do

No implementation, no tests, no code. No merge, release or mining activation.
`theorem_proven` remains False.

## 8. Next action

Approve the 1-based convention of §2 and exact-comparison method §4.1, then
state the bijectivity proof obligation as a formal target.
Owner: @EuclidUltimaPhi. Drafting: `pythiaphi`.
