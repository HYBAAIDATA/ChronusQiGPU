# Hendrix: exact structured-search primitives

`chronus.hendrix` ("Hendrix") is the Chronus namespace for structured-search building blocks whose behaviour can be stated and checked exactly. It provides:

1. **A Galois-field lookup primitive** (`chronus.hendrix.galois`): exact arithmetic in a small prime field F_p through discrete-logarithm tables, with a fixed number of table reads per query.
2. **Oracle objects** (`chronus.hendrix.oracles`): deterministic functions, built on those tables, that search and period-finding algorithms can query through the shared oracle protocol.
3. **A facade over the existing routines** (`chronus.hendrix.structured`): the closed-form F_257 phase formulas and the legacy finite-field search iterates, re-exported unchanged, with a one-line description of what each one computes.

Hendrix uses exact integer arithmetic only: no floating point, no complex numbers, no numpy, no pseudo-random numbers. It is not part of TURING and does not model physical quantum systems.

## The lookup primitive: `PrimeField`

```python
from chronus.hendrix import GF257, PrimeField

GF257.generator                 # 3
GF257.group_order               # 256 == 2**8
GF257.discrete_log(5)           # k with 3**k == 5 (mod 257)
GF257.zech_log(10)              # k with 3**k == 1 + 3**10 (mod 257)
PrimeField(65537).generator     # 3
PrimeField(2**127 - 1)          # ValueError: above the 2**20 table guard
```

`PrimeField(p, *, max_order=MAX_FIELD_ORDER)` validates that `p` is prime (deterministic trial division), finds the smallest primitive root `g` by checking its order against the prime factorisation of `p - 1`, and builds two tables once:

- `EXP[k] = g**k mod p` for `0 <= k < p - 1`;
- `LOG[y] = k` with `g**k = y`, for `1 <= y < p`.

The build also checks that the powers of `g` visit every nonzero residue exactly once and return to 1, so the cyclic structure is verified rather than assumed. Instances are immutable; two fields compare equal when their characteristics are equal.

| Member | Result | Table work per call |
|---|---|---|
| `p`, `generator`, `group_order`, `group_order_factors` | field parameters | none |
| `reduce(a)` | `a mod p` | none |
| `mul(a, b)`, `div(a, b)` | `a*b`, `a/b` in F_p | 2 LOG reads, 1 EXP read |
| `inverse(a)` | `a**-1` | 1 LOG read, 1 EXP read |
| `pow(a, e)` | `a**e` for any int `e` | 1 LOG read, 1 EXP read |
| `discrete_log(y)` | `k` in `[0, p - 1)` with `g**k = y` | 1 LOG read |
| `antilog(k)` | `g**k` (k reduced mod `p - 1`) | 1 EXP read |
| `zech_log(n)` | `k` with `g**k = 1 + g**n`, or `None` when `1 + g**n = 0` | 1 EXP read, 1 LOG read |
| `order(a)` | `(p - 1) // gcd(LOG[a], p - 1)` | 1 LOG read and one gcd |
| `is_quadratic_residue(a)` | `True` iff `a` is a nonzero square (`LOG[a]` even) | 1 LOG read |

Operands are ints interpreted modulo `p`. `bool` and non-int arguments raise `TypeError`; `inverse(0)`, `div(a, 0)` and `pow(0, e)` with `e < 0` raise `ZeroDivisionError`; `discrete_log(0)` and `order(0)` raise `ValueError`. `pow(0, 0)` is 1, as in Python's `pow(0, 0, p)`. The Zech logarithm turns addition into exponent arithmetic: `g**a + g**b = g**(a + zech_log(b - a))` whenever `zech_log(b - a)` is not `None`.

`GF257 = PrimeField(257)`: 257 = 2**8 + 1 is the Fermat prime F_3, its smallest primitive root is 3 and its multiplicative group has order 256 = 2**8.

### Complexity

- **Construction** of a field with characteristic `p`: trial division up to `sqrt(p)` for primality and for the factorisation of `p - 1` (about a thousand divisions at most under the guard); a scan for the smallest primitive root costing one modular power per distinct prime factor of `p - 1` per candidate (no bound on the scan length is claimed; the root is 3 for both 257 and 65537); then O(p) multiplications and O(p) memory for the two tables. The tables are `array` objects with 2-byte entries for `p <= 65536` and `unsigned long` entries (4 or 8 bytes, platform dependent) above that: about 1 KB for F_257 and at most about 16 MiB at the guard.
- **Each query** after construction: the fixed number of table reads listed above plus one reduction of an exponent modulo `p - 1`, independent of the elements involved. `pow` also multiplies the stored logarithm by the caller's exponent, whose cost grows with the number of digits of that exponent; `order` also computes one gcd.
- **Scope**: these statements concern one fixed, small field. Fields with `p > 2**20` are refused with `ValueError` before any primality test or table work (`max_order` can lower the guard for a caller but cannot raise it). A lookup table has to be built and stored before it answers anything, so tabulating a small field is not a general discrete-logarithm method, and Hendrix makes no statement about the field sizes used in cryptography.

## Oracles

### Protocol (shared with the TURING oracle work)

An oracle is any object with

- an `int` attribute `domain_size` (positive), and
- `__call__(x: int) -> int`, defined for `0 <= x < domain_size`.

A Boolean oracle returns the ints 0 or 1. The TURING team implements the same protocol in parallel. Hendrix matches it by duck typing: no Hendrix module imports `turing`, and `is_oracle(obj)` only checks the shape (an instance with a positive int `domain_size` that is callable); it does not evaluate the oracle. Hendrix oracles are classical, exact functions on integers. How an algorithm uses them (for example, to build a phase oracle in another library) is that algorithm's responsibility, and Hendrix does not depend on any such library.

Hendrix oracles validate each query: a non-int or `bool` input raises `TypeError` and an input outside `[0, domain_size)` raises `ValueError`. Their parameters are read-only.

| Oracle | `domain_size` | `f(x)` | Marked inputs | Cross-check helper |
|---|---|---|---|---|
| `DiscreteLogOracle(field, y)`, `y != 0` | `p - 1` | 1 iff `g**x == y` | exactly 1 | `marked()`: `{discrete_log(y)}`, one LOG read |
| `QuadraticResidueOracle(field)`, odd `p` | `p - 1` (exponents) | 1 iff `g**x` is a square, i.e. `x` even | `(p - 1) / 2` (128 in F_257) | `marked()`: the even exponents |
| `QuadraticResidueElementOracle(field)`, odd `p` | `p` (elements) | 1 iff `x` is a nonzero square; `f(0) = 0` | `(p - 1) / 2`, all in `[1, p)` | `marked()`: the even powers of `g` |
| `PeriodOracle(field, a)`, `a != 0` | `p - 1` | `a**x` (one LOG and one EXP read) | not Boolean | `period()`: `(p - 1) // gcd(LOG[a], p - 1)`; `validate_promise()` |
| `XorPeriodOracle(n, s)`, `0 < s < 2**n` | `2**n` | `x XOR (bit_t(x) * s)` with `t` the top bit of `s`, equal to `min(x, x XOR s)` | not Boolean | `period()`: `s`; `validate_promise()` |

`XorPeriodOracle` is GF(2)-linear with kernel `{0, s}`, so `f(x) = f(x XOR s)` and every output has exactly two preimages (Simon's promise). The Boolean oracles also expose `marked_count`.

`marked()` and `period()` return the answer that a search or period-finding routine should produce, read directly from the tables or the construction parameters. They exist to cross-check such routines. They are not search algorithms: an algorithm that queries the oracle still makes as many queries as it requires, and code that calls these helpers instead has not searched for anything. `validate_promise()` is an exhaustive check (`p - 1` queries for `PeriodOracle`; `2**n` queries for `XorPeriodOracle`, refused above `MAX_PROMISE_CHECK_BITS = 20`).

## Facade over the existing routines: `chronus.hendrix.structured`

`chronus.hendrix.structured` must be imported explicitly; `import chronus.hendrix` does not load the legacy `chronus.quantum` namespace. The module re-exports the identical objects (nothing is wrapped, renamed or modified) and `structured.CATALOG` maps each exported name to its source module and a one-line description:

- from `chronus.math.f257_search`: `mod_inv`, `f257_phases`, `f257_phases_multi`;
- from `chronus.quantum.statevector`: `StateVector`;
- from `chronus.quantum.grover`: `oracle_flip`, `diffusion`, `grover_iterate`, `grover_trajectory`;
- from `chronus.quantum.metallic_search`: `phase_iterate`, `phase_iterate_multi`, `one_shot_phases`, `one_shot_phases_multi`, `exact_search`, `exact_search_multi`, `jform_one_shot_phases`, `jform_iterate`, `generalized_iterate`, `run_search`, `scaling_sweep`, `algebraic_search`, `phase_matched_sweep`, `METALLIC_COEFFICIENTS`, `QSqrt2`, `SearchResult`;
- from `chronus.quantum.extension_search`: `phi_element_power`, `extension_norm`, `extension_one_shot_phases`, `exact_extension_search`, `ExtensionSubspaceState`;
- from `chronus.quantum.subspace`: `SubspaceState`, `uniform_subspace`, `subspace_iterate`, `jform_subspace_iterate`, `exact_subspace_search`, `exact_jform_subspace_search`.

How to read these routines:

- They are legacy finite-field and algebraic research code (see [`src/chronus/quantum/README.md`](../src/chronus/quantum/README.md) and [`docs/system-update/quantum-package-taxonomy.md`](system-update/quantum-package-taxonomy.md)), not TURING and not conventional complex-Hilbert-space quantum mechanics. Amplitudes are elements of F_257, of F_257[phi], or exact numbers in Q(sqrt(2)); the finite-field iterates are not unitary; there is no Born rule and no measurement. The catalogue is not a validation.
- `f257_phases` computes closed-form field parameters `(alpha, mu, beta)` from a given seed in a constant number of field operations. It does not locate an unknown marked item; neither does `f257_phases_multi`.
- "One-shot" means closed-form parameters followed by one algebraic iterate. Every routine that involves marked items receives the marked index, the marked set or the marked count as an input; none of them locates an unknown marked item. The dense routines (`exact_search`, `exact_search_multi`) return a vector of `N = 2**n` amplitudes, so reading the marked set back from it takes `N` reads. The rank-2 routines (`exact_subspace_search`, `exact_extension_search`, `exact_jform_subspace_search`) use only the count and do not identify which indices are marked. Obtaining a marked set from a Boolean oracle takes one query per input of its domain.

Not included: `ExactGaloisOracleF257` in `chronus.execution.geometric_galois_miner`. It takes the marked set as an argument, and the miner finds that set by a sequential double-SHA-256 scan of candidate nonces before the closed-form step runs, so the step is not a search primitive.

## Tests

| File | Covers |
|---|---|
| `tests/test_hendrix_galois.py` | Tables against `pow()` for every element of F_p, p in {2, 3, 5, 7, 11, 13, 17, 97, 257}; generator 3 and group order 2**8 for F_257 and 3 and 2**16 for F_65537; inverse, logarithm and antilogarithm round trips; Zech identity; zero handling; refusal above the guard (including 2**127 - 1 and 2**255 - 19). |
| `tests/test_hendrix_oracles.py` | Protocol shape; marked counts (1 for `DiscreteLogOracle`, 128 for quadratic residues in F_257) by querying every input; `period()` against brute-force orders for every `a` in F_257*; Simon's promise for every `s` with `n <= 8` and GF(2) linearity for `n <= 5`; promise checks rejecting broken functions. |
| `tests/test_hendrix_structured.py` | Facade names resolve to the same objects as the source modules and cover their public routines; descriptions do not repeat overclaims; the table inverse matches `mod_inv`; oracle marked sets match the supports produced by `exact_search` and `exact_search_multi`; Hendrix sources pass the purity-gate rules, use integer arithmetic only, do not import the legacy namespace into the core, and contain no claim-gate tokens. |

Run them with:

```
python -m pytest -q tests/test_hendrix_galois.py tests/test_hendrix_oracles.py tests/test_hendrix_structured.py
```

While the namespace was written, these tests were run locally on Python 3.12 without pytest (a standard-library runner calling each test function). That is a development check, not CI evidence; the CI run for the exact commit is the record of whether they pass. `scripts/ci/purity_gate.py` does not list `src/chronus/hendrix` among its packages, which is why `tests/test_hendrix_structured.py` applies the gate's `scan_file` to the Hendrix sources directly.
