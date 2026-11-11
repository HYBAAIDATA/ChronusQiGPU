# TURING exact algorithms

`turing.algebra` and `turing.algorithms` evaluate standard quantum algorithms
exactly. Amplitudes are elements of cyclotomic fields Q(zeta_n), which are
subfields of the complex numbers, so this is mathematics over complex Hilbert
spaces with exact coordinates. Every result carries zero rounding:

- coefficients are `fractions.Fraction` values and Python ints;
- normalisations such as 1/sqrt(Q) are kept symbolic (an integer D with
  amplitude v / sqrt(D)) or cancel exactly;
- probabilities are exact rationals or exact elements of the real subfield of
  Q(zeta_n), compared with an exact zero test;
- there is no floating point, no `numpy`, no randomness, no truncation and no
  lossy compression on any algorithm path. Uniform measurement outcomes are
  never sampled: the caller chooses the branch.

The new modules do not import the floating-point modules of this package
(`state.py`, `operator.py`, `gates.py`, `measurement.py`, `tensor.py`) and do
not import `chronus`. Importing the top-level `turing` package still executes
the unchanged `turing/__init__.py`, which loads those modules.

## Conventions

- Qubit q is bit q of a basis index (bit 0 is the least significant).
- An oracle is any object with an int attribute `domain_size` and a method
  `__call__(x) -> int` for 0 <= x < domain_size; a Boolean oracle returns 0
  or 1. Duck typing is enough; no base class is required.
- Folding means an exact, lossless reduction of a state by symmetry. It never
  discards information, and the tests compare folded and unfolded results
  wherever both are computable.

## What each module computes

| Module | Exact computation | Invariant proved by the tests |
| --- | --- | --- |
| `algebra.cyclotomic` | Q(zeta_n) in the power basis modulo Phi_n; Phi_n = (x^n - 1) / prod_{d \| n, d < n} Phi_d by integer division; inverse by the extended Euclidean algorithm on Q[x]; conjugation zeta^k -> zeta^-k; lifting Q(zeta_m) -> Q(zeta_n) for m \| n; \|sum of roots of unity\|^2 by counting pairwise differences | field axioms on fixed samples, conjugation and Galois maps are automorphisms, zeta^n = 1, the n-th roots sum to 0 (n > 1), deg Phi_n = phi(n) for n = 1..30, \|zeta^k\|^2 = 1, helper = a * conj(a) |
| `algebra.reduction` | ring homomorphism Z[zeta_256] -> F_257 with zeta -> 3, used only as an exact checksum | Phi_256(3) = 0 mod 257, homomorphism laws, conjugation corresponds to zeta -> 3^-1 = 86, QFT/Shor/QPE residues agree with independently computed residues |
| `algorithms.walsh`, `algorithms.gf2` | integer Walsh-Hadamard transform with exact 1/2^n; GF(2) elimination, null spaces, affine solution sets | inverse(transform(v)) = v, Parseval; elimination agrees with exhaustive enumeration |
| `deutsch_jozsa` | amplitude (1/2^n) sum_x (-1)^(f(x) + x.y) | P(0^n) is exactly 1 (constant) or 0 (balanced) for n = 1..6; promise violations raise `ValueError` |
| `bernstein_vazirani` | the same transform for f(x) = s.x xor b | every s for n = 1..6 is returned with probability exactly 1; non-affine oracles raise `ValueError` |
| `simon` | P(y) = (1/4^n) sum_d K(d) (-1)^(d.y), K(d) counting collisions at XOR difference d (folding by f-value); s by GF(2) elimination over the exact support | uniform 1/2^(n-1) on the orthogonal complement of s (n = 2..5), uniform 1/2^n when f is injective, folded = unfolded |
| `grover` | marked and unmarked amplitudes A/sqrt(N), B/sqrt(N) with exact A, B (folded); the full N-vector (unfolded) | folded = unfolded for every N <= 32 and every M; probabilities sum to exactly 1; `optimal_iterations` maximises the exact success probability over k = 0..isqrt(N)+1; one marked item among 256: 12 iterations with the exact probability |
| `qft` | QFT over Z_Q in Q(zeta_Q) with 1/sqrt(Q) symbolic; canonical (squarefree D) representation | QFT * QFT^dagger = I exactly for Q in {1, 2, 3, 4, 5, 6, 8}; inverse_qft(qft(v)) = v; QFT^2 is the index reversal |
| `qpe` | P(y) = \|(1/2^t) sum_j zeta_b^(a j) zeta_(2^t)^(-j y)\|^2 in Q(zeta_lcm(b, 2^t)) from closed-form difference counts; multiplication by g on F_p^* | dyadic phases recovered with probability exactly 1 for t = 1..8; non-dyadic distributions sum to exactly 1 and include irrational values such as (2 + sqrt 2)/8; all 256 eigenphases k/256 of multiplication by 3 on F_257 recovered exactly with an 8-qubit register computed from p - 1 |
| `shor` | f(x) = a^x mod N by square-and-multiply; folding x by f-value; P(y) = (1/Q^2) sum_v \|S_(y,v)\|^2 with Q = 2^t >= N^2; exact continued fractions over the exact support; candidates verified by modexp | N = 15, a = 7: order 4, P(y) = 1/4 exactly at y in {0, 64, 128, 192} and 0 elsewhere; N = 21, a = 2: order 6 from the exact support; distributions sum to exactly 1; folded = per-class sums = direct multiplication; `factor(15)` = (3, 5), `factor(21)` = (3, 7) |
| `clifford` | Aaronson-Gottesman tableau over GF(2) with H, S, CNOT, X, Y, Z; Z measurement classified as deterministic (probability 1) or uniform (1/2 each); stabilizer membership, commutation, GF(2) rank, joint outcome supports | GHZ at 1,000 and 2,500 qubits (register size read from the circuit); every qubit's outcome follows from Z_i Z_(i+1) in the stabilizer group; agreement with a dense Q(zeta_8) evaluation for n <= 3 |
| `structured` | Deutsch-Jozsa, Bernstein-Vazirani and Simon as Clifford circuits; dyadic phase estimation with the semiclassical inverse QFT | 2,500-qubit instances: verdicts and P(0^n) exact; a 2,499-bit s with probability 1; Simon support = orthogonal complement of s with 2^-(n-1) each; a 2,500-bit phase numerator recovered with probability 1 |

## Clifford tableau

The tableau holds 2n generators (destabilizers and stabilizers), each a signed
Hermitian Pauli (-1)^r i^|x & z| X^x Z^z. It is bit-packed in Python ints: one
column bitset per qubit for x and for z over the 2n rows, so a gate costs a
constant number of big-int operations, plus one int for the phase bits. Rows
are extracted on demand to multiply generators, and the product phase is
computed with popcounts:
P(x1, z1) P(x2, z2) = i^e P(x1 ^ x2, z1 ^ z2) with
e = |x1 & z1| + |x2 & z2| + 2 |z1 & x2| - |(x1 ^ x2) & (z1 ^ z2)| mod 4.

The tableau occupies 2n(2n + 1) bits, about 3 MiB at n = 2,500. The joint
Z-basis outcome distribution of any set of qubits is uniform over an affine
subspace of GF(2)^k; `outcome_support` derives it by eliminating the
stabilizer generators that are not Z-type on that set.

## Residue checksums in F_257

Phi_256(x) = x^128 + 1, and 3 has multiplicative order 256 modulo 257, so
3^128 = -1 (mod 257) and zeta_256 -> 3 defines a ring homomorphism
Z[zeta_256] -> F_257. The odd powers of 3 are the 128 roots of x^128 + 1
modulo 257, so 257 splits completely. Elements of Q(zeta_m), m | 256, are
lifted first: zeta_32 -> 3^8 = 136 (order 32) and zeta_16 -> 3^16 = 249 = -8
(order 16); the integer 2 also has order 16 modulo 257. The map is
many-to-one, so a residue is a checksum of an amplitude and never replaces
it; F_257 is never the amplitude field.

## Scale boundary

The 2,500-qubit instances are Clifford circuits or dyadic-phase circuits.
That is exactly why they evaluate at that size: a stabilizer state is fixed
by its 2n(2n + 1)-bit tableau, and a dyadic phase a / 2^t is carried as an
integer exponent modulo 2^t (the semiclassical inverse QFT reads one bit per
step with probability exactly 1, never evaluating a root of unity).

The following are not claimed at that size:

- Shor's modular exponentiation does not fold this way. Order finding for an
  n-bit modulus needs an exact sum over Q = 2^(2n) terms; for a 1024-bit
  modulus that is 2^2048, about 10^616.5 terms. The exact evaluation here is
  limited to `shor.MAX_REGISTER_QUBITS` = 12 register qubits.
- Optimal Grover search over N = 2^2500 items needs about
  (pi/4) * 2^1250, roughly 2^1249.65 iterations.
- General (non-Clifford) circuits are evaluated by the dense modules, whose
  cost doubles with every added qubit; dense oracle tables are limited to
  `oracles.MAX_DENSE_DOMAIN` = 2^20 inputs.

Everything in this package is a classical, exact evaluation of the
mathematics. Nothing is executed on quantum hardware, and no comparison with
or advantage over other methods is claimed.

## Running the tests

Each `test_turing_*.py` module puts `packages/turing/src` first on `sys.path`,
because the repository root also contains a different `src/turing` package
that the root pytest configuration (`pythonpath = ["src"]`) would otherwise
import. From the repository root:

```bash
python -m pytest -q packages/turing/tests/test_turing_*.py
```

Collecting the whole directory from the root also collects the existing
`test_axioms.py`, which imports the top-level `turing` before these modules and
therefore resolves to the root `src/turing`.

Measured runtime (measured on 2026-11-11 in a shared sandbox, CPython 3.12.16,
pure Python, one process; indicative only): the 84 `test_turing_*` tests ran
in 7 to 18 s across repeated runs on the shared machine. Best of three runs for
the 2,500-qubit
tests: GHZ 0.12 s, Deutsch-Jozsa (four oracles) 0.11 s, Bernstein-Vazirani
0.02 s, Simon 0.03 s, dyadic phase estimation 0.005 s. The 1,000-qubit GHZ
test, including all 499,500 pairwise commutation checks, took 0.19 s.
