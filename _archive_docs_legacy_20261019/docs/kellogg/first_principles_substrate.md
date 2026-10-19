# First-principles substrate

The probes below are mathematics. They do not select a CPU, a GPU, or a
quantum device. Aethel records the declared overhead of a traversal. It
does not convert that overhead into a throughput.

Implementation: `kellogg/first_principles.py`.
Overhead: `aethel/overhead.py`.
Tests: `tests/test_first_principles.py` (17 checks).

## P4 — the standard map, instead of `std(p)`

The Chirikov standard map is

```text
p' = p + (K / 2π) sin(2π θ)
θ' = θ + p'    (mod 1)
```

`std(p)` is small both on a KAM torus and inside a mode-locked island, so
it cannot separate them. Three diagnostics replace it.

**Lyapunov.** The maximal exponent is the average logarithmic stretch of
a renormalized tangent vector. At `K = 0` a generic tangent grows
linearly, so the finite-time exponent falls toward 0 as the horizon
grows (measured: about `1.2e-2` at 500 steps and below `1e-3` at 20 000).
At `K = 5` it stays above `0.5`. At `K = 0.5`, on the golden momentum,
it stays below `0.01`. Chaos is the positive exponent. Both regular
regimes sit near 0, so Lyapunov alone does not finish the separation.

**Greene residue.** The Jacobian of the integrable map is the shear
`[[1, 1], [0, 1]]`. Its `q`-th power is `[[1, q], [0, 1]]`, trace 2, so

```text
R = (2 − Tr) / 4 = 0
```

exactly, for every period. For `K > 0` the minimizing orbit of rotation
number `F_n / F_{n+1}` is continued from that uniform advance by a
configuration Newton solver. Greene's residue of those orbits:

| K | Fibonacci periods | what the residue does |
|---|---|---|
| 0.5 (below the golden breakup) | 8 … 89 | `|R| < 1/4` and the last one is below `1e-9` |
| 0.971635406 (Greene's critical probe) | 13 … 144 | `|R|` stays inside `(0.24, 0.26)` |
| 1.5 (above the breakup) | 8 … 34 | `|R|` increases and the last one exceeds 10 |

The critical value is a literature probe, not a constant derived here.
The period-1 elliptic point `(θ, p) = (1/2, 0)` has residue `K/4`
exactly (`0.125` at `K = 0.5`). That residue does not follow the
Fibonacci collapse. That is the distinction `std(p)` missed: the island
is a fixed rational orbit; the torus is the limit of approximants whose
residue dies.

**Action.** The lifted momentum is an action. At `K = 0` its variance is
0. At `K = 0.5` on the golden turn the variance at 20 000 steps is less
than twice the variance at 200 steps: it has saturated, which is a
transport barrier. At `K = 2.5` the variance grows by more than ten
times over the same horizons.

## P3 — continuous gaps, instead of a degree grid

The golden angle is `360/φ² ≈ 137.507764°`, not `137°`. The turn
`137/360` is a coprime rational. On a 20-bin grid with 50 points the
occupancy standard deviations of the two turns are equal. That tie is
the discretization artifact.

On the circle the Delaunay edges are the gaps, and the Voronoi cells are
the adjacent half-gaps. For `137/360`:

- at 360 points every gap is exactly `1/360`;
- once the count meets or exceeds 360, the maximum gap remains `1/360`
  and the covering excess `N · max gap` equals `N/360` exactly.

For the golden turn the same excess stays below 2 at
`N ∈ {10³, 10⁴, 10⁵}`. The rational excess keeps growing. The golden
ratio pulls ahead because the grid has been removed, not because a
finer grid was tuned.

## P1 — higher-dimensional low discrepancy

The generator in dimension `d` is the positive root of

```text
x^{d+1} = x + 1
```

and the sequence is `({n/g}, {n/g²}, …, {n/g^d})`.

| d | number | polynomial | role |
|---|---|---|---|
| 1 | golden ratio φ | `x² = x + 1` | one coordinate |
| 2 | plastic number ψ ≈ 1.324717957 | `x³ = x + 1` | two coordinates |
| 3 | φ₃ ≈ 1.220744085 | `x⁴ = x + 1` | the unit 3-cube |

ψ is the degree-3 member of this family. It is the constant used for
three-fold packing. It is not a generator of three independent cube
coordinates: `ψ⁻² + ψ⁻³ = 1`, so `({n/ψ}, {n/ψ²}, {n/ψ³})` lies in a
plane. On the corner `[0, 1/2)³` that sequence's integration error stays
above `0.1` at 4000 points. The cube sequence is φ₃, and at the same
count its corner error is below the median of 25 Monte Carlo draws.
Which other uses of ψ survive is surveyed in
`docs/kellogg/plastic_number_applications.md`.

A second, exact, two-dimensional rule is the Fibonacci–Korobov lattice
`(k/F_n, {k F_{n-1}/F_n})` with coordinates in `Fraction`. This is not
`({k/φ}, {k/φ²})`. Those two turns sum to 1, so that sequence is a line
and does not fill the square. At `F_18 = 2584` the lattice's error on
`∫ xy = 1/4` is exactly `1621/13354112` below the integral. The power
construction in dimension 3 collapses; see
`docs/kellogg/fibonacci_korobov.md`.

Non-smooth integrands:

- The golden turn puts `|#{kα < 1/2} − N/2| ≤ 1` for the counts checked
  through 4096. A Monte Carlo draw of the same interval is not that tight.
- `∫₀¹ x^{−1/2} dx = 2`. The golden samples beat the median of 30
  Monte Carlo estimates at both 1 000 and 10 000 points. The singularity
  is where low discrepancy is supposed to matter, and here it does.

## Execution, without a device

`{n φ}` in IEEE-754 is a diagnostic. At `n = 2⁵³ + 17` it differs from
the 40-digit product by more than `10⁻³`. The replacement is integer
arithmetic: `(n · F_k) mod F_{k+1}` as a `Fraction`, which matches itself
at that same `n`. For a power-of-two modulus the low bits
`(n · a) & (2^b − 1)` equal the modulus reduction exactly. That is the
whole content of the "fixed-point / bitwise" step. There is no SIMD
timing and no GPU kernel.

Z-order is the integer bit-interleave of a grid coordinate. On the
`256 × 256` grid it is a bijection. Walking every cell in Morton order
and walking them with stride 137 touch the same set of row-major
addresses. Aethel prices both walks as

```text
miss_cost = Σ |address_{i+1} − address_i|
```

The Morton walk is the cheaper one. The ledger does not alter a sample:
pricing an exact generator leaves the `Fraction` unchanged, charges
`2n` arithmetic operations, and charges miss cost 0 because no address
stride was declared.

Deleting the ledger would not change a residue, a gap, or a point. Adding
a device measurement would be a different claim and is not made here.
