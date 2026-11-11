# TURING canonical algorithm suite: implementation specification

**Package:** `packages/turing` (distribution `hyba-turing`, import name `turing`)
**Version:** 1.0, 11 November 2026
**Owner:** HYBA Data. Internal and confidential: TURING reaches participants only as a black-box capability (section 8), never as code they can read.
**Status:** specification. A capability below counts as delivered only when its tests pass in CI at a recorded commit.

This document is the build contract for the TURING workstream. It replaces the draft circulated on 11 November 2026; section 9 lists what changed and why.

## 1. Scope and invariants

The suite covers Deutsch–Jozsa, Bernstein–Vazirani, Simon, Grover, the quantum Fourier transform (QFT), quantum phase estimation (QPE) and Shor's order finding and factoring, plus a stabilizer (Clifford) evaluation path for structured instances at 2,500 qubits.

Five invariants apply to every module and are enforced by tests:

1. **Exactness.** Every amplitude and probability is an exact element of a cyclotomic field Q(ζ_m) or of Q. No IEEE-754 value appears in state evolution, measurement or post-processing. Normalisation factors such as 2^(−n/2) and Q^(−1/2) are carried symbolically as integer exponents or denominators, so nothing is divided into an irrational number and nothing is rounded.
2. **Lossless folding.** A folded representation is an exact change of coordinates onto a subspace that the circuit provably never leaves (a symmetry orbit, a coset decomposition, a stabilizer group). Folding never discards amplitude. Wherever the full state is small enough to compute, a test proves that the folded and unfolded results are identical.
3. **Determinism.** No randomness anywhere. Measurement returns the exact outcome distribution; where a run must continue on one branch, the branch is chosen explicitly by the caller.
4. **Dependency direction.** `turing` imports nothing from `chronus`. Chronus may depend on TURING, never the reverse. Oracles are plain objects that satisfy the protocol in section 3.
5. **Computed sizes.** Register sizes, qubit counts and iteration counts are computed from the circuit or the oracle. None is a constant in code or documentation.

TURING is not a quantum computer and not a device simulator. It evaluates the mathematics of these algorithms exactly on classical hardware. Its distinctive guarantee is zero numerical error: every result is exact, exactly normalised and reproducible bit for bit.

## 2. Algebraic substrate (`turing.algebra`)

### 2.1 Cyclotomic fields

`CyclotomicField(n)` represents Q(ζ_n) in the power basis 1, ζ, …, ζ^(φ(n)−1) modulo the cyclotomic polynomial Φ_n, which is computed exactly by dividing x^n − 1 by Φ_d for every proper divisor d of n. Elements support addition, multiplication, exact zero tests, complex conjugation (ζ^k ↦ ζ^(−k)), the squared modulus a·ā, inversion by the extended Euclidean algorithm modulo Φ_n, and lifting from Q(ζ_n) to Q(ζ_m) when n divides m. A dedicated routine returns |Σ_i ζ^(e_i)|² by counting pairwise exponent differences, which is the inner loop of Shor and QPE.

### 2.2 Dyadic fields

For m = 2^k, Φ_m(x) = x^(2^(k−1)) + 1, so Q(ζ_(2^k)) ≅ Q[x]/(x^(2^(k−1)) + 1) and any power folds losslessly by ζ^(p + 2^(k−1)) = −ζ^p. This is the field of QFT and QPE amplitudes on a 2^k register.

### 2.3 F_257 is an exact reduction map, not an amplitude field

257 = 2^8 + 1 is a Fermat prime, so F_257^× is cyclic of order 256. The generator 3 has order 256 and 3^128 ≡ −1 (mod 257). Because 257 ≡ 1 (mod 256), Φ_256(x) = x^128 + 1 has 128 distinct roots in F_257, so the prime 257 splits completely in Q(ζ_256) and, for each root r (for example r = 3), the map Z[ζ_256] → F_257 with ζ ↦ r is a ring homomorphism.

`turing.algebra.reduction` implements this map. It is used as an exact checksum: reducing a QFT or Shor amplitude and comparing it with the same computation carried out in F_257 detects arithmetic faults at negligible cost. It may also support number-theoretic transforms for exact integer convolution when coefficient sizes are bounded (or combined by the Chinese remainder theorem across further primes p ≡ 1 mod 2^k).

It is never the amplitude field. F_257 has no ordering and no absolute value, so Born probabilities cannot be formed in it, and the map is many-to-one: distinct amplitudes share residues. All amplitudes therefore live in characteristic zero.

### 2.4 Walsh–Hadamard transform

H^(⊗n) acts on integer vectors by the fast butterfly (additions and subtractions only). Each application contributes a factor 2^(−n/2), recorded as an exponent; two applications give the exact rational 2^(−n).

## 3. Oracle contract (`turing.algorithms.oracles`)

An oracle is any object with an integer attribute `domain_size` and a method `__call__(x) -> int` defined for 0 ≤ x < `domain_size`. A Boolean oracle returns 0 or 1. TURING accepts any object with this shape and does not require subclassing. `BooleanOracle` and `FunctionOracle` build oracles from predicates, dictionaries or lists, and promise validators raise `ValueError` with a precise message when a promise (constant or balanced, linear, two-to-one with a hidden period) does not hold.

Hendrix (`chronus.hendrix`) supplies exact F_p oracles that satisfy this contract: discrete-logarithm, quadratic-residue, period and XOR-period oracles built on lookup tables. Each query is a table lookup after a one-time table build of size p − 1 for a fixed small prime (Hendrix refuses fields above 2^20). That is a per-query cost statement for a small field; it does not make discrete logarithms in cryptographic groups tractable. TURING never imports Hendrix; the integration tests that drive TURING algorithms with Hendrix oracles live in the Chronus test suite.

## 4. Algorithms (`turing.algorithms`)

Each algorithm states the exact formulation, the folding used, what it returns and what it costs to evaluate exactly. On quantum hardware several of these algorithms need a single oracle query; an exact classical evaluation of a black-box oracle must read the oracle on every input. The guarantee here is exactness, not query count. Where the oracle is structured (affine or linear), the circuit is a Clifford circuit and the stabilizer path in 4.8 evaluates it at 2,500 qubits.

### 4.1 Deutsch–Jozsa

The amplitude of |0^n⟩ after H^(⊗n) U_f H^(⊗n) is S / 2^n with S = Σ_x (−1)^(f(x)), an integer. `run(n, oracle)` returns the exact probability (S / 2^n)², which is 1 for a constant f and 0 for a balanced f, and raises `ValueError` if S is neither ±2^n nor 0 (promise violated). Cost: 2^n oracle reads. Affine oracles f(x) = a·x ⊕ b evaluate on the stabilizer path with 2,499 data qubits and one ancilla.

### 4.2 Bernstein–Vazirani

For f(x) = s·x ⊕ b the output state is ±|s⟩ exactly, so s is returned with probability exactly 1. `run` verifies that the oracle has this form and raises otherwise. Cost: one Walsh–Hadamard transform of the truth table (n·2^n additions). Linear oracles with a 2,499-bit s evaluate on the stabilizer path.

### 4.3 Simon

For f with f(x) = f(y) exactly when x ⊕ y ∈ {0, s}, the inputs fold into cosets {x, x ⊕ s}. Each coset contributes 2^(−n)·(−1)^(x·y)·(1 + (−1)^(s·y)) to the amplitude of y, which is zero when s·y = 1. The exact distribution is P(y) = 2^(−(n−1)) on the orthogonal complement of s and zero elsewhere (uniform 2^(−n) when f is injective). s is recovered by GF(2) elimination over the exact support; nothing is sampled. Linear oracles f(x) = Ax with kernel {0, s} evaluate on the stabilizer path with 1,250 qubits per register (2,500 in total), the support being read from the tableau.

### 4.4 Grover

The state never leaves the span of the uniform superposition over the M marked items and the uniform superposition over the N − M unmarked items. Writing the per-item amplitudes as A_k/√N and B_k/√N with A_0 = B_0 = 1, one iteration is the rational recurrence

m = (−A_k·M + B_k·(N − M)) / N, A_(k+1) = 2m + A_k, B_(k+1) = 2m − B_k,

and the success probability after k iterations is the exact rational M·A_k²/N, equal to sin²((2k + 1)θ) with sin²θ = M/N (for N = 256 and M = 1 it is 36481/1048576 after one iteration). The optimal iteration count is chosen by exact comparison of these rationals, with no use of π. An unfolded evaluation for N ≤ 32 proves folding is lossless. `search(oracle)` returns the marked items, the iteration count and the exact success probability. Evaluating the optimal count for N = 2^2500 would need about 2^1249.65 iterations, so large-N Grover is evaluated only for small iteration counts.

### 4.5 Quantum Fourier transform

The QFT on Z_Q maps |x⟩ to Q^(−1/2) Σ_y ζ_Q^(xy) |y⟩ with amplitudes in Q(ζ_Q) and the factor Q^(−1/2) carried symbolically. Tests prove QFT·QFT† = I exactly for small Q and that the inverse transform recovers its input.

### 4.6 Quantum phase estimation

For an eigenphase φ = a/b and a t-qubit register, P(y) = |2^(−t) Σ_(j<2^t) ζ_(b·2^t)^(j·(a·2^t − y·b))|², an exact element of the real subfield of Q(ζ_(b·2^t)). When φ·2^t is an integer the outcome y = φ·2^t occurs with probability exactly 1. For large registers with dyadic phases, the semiclassical inverse QFT processes one qubit at a time on exact integer phase exponents modulo 2^t, so a 2,500-bit numerator is recovered with probability exactly 1 without evaluating any root of unity.

The F_257 instance takes U as multiplication by g = 3 on F_257^×, a permutation of 256 basis states. Its eigenvectors are the Fourier states of the cyclic group, with eigenphases k/256, so with t = 8 every k is recovered with probability exactly 1.

### 4.7 Shor's order finding and factoring

For N and a with gcd(a, N) = 1, choose Q = 2^t ≥ N². The function f(x) = a^x mod N is computed by explicit square-and-multiply. Inputs fold by function value into classes C_v, and P(y) = Σ_v |Σ_(x∈C_v) ζ_Q^(xy)|² / Q², evaluated with the pairwise-difference routine; the true order is never used inside this computation. Classical post-processing applies exact continued fractions to every y in the exact support and confirms candidate orders by modular exponentiation; factors come from gcd(a^(r/2) ± 1, N). For N = 15 and a = 7 the order is 4 and P(y) = 1/4 exactly at y = 0, 64, 128 and 192. `factor(N)` tries bases 2, 3, 4, … deterministically.

The exact evaluation reads all Q = 2^(2n) inputs for an n-bit modulus. That is practical for small moduli (Q = 256 for N = 15, Q = 512 for N = 21) and far beyond any classical computer for cryptographic moduli: for a 1,024-bit modulus Q is about 10^616.5. TURING does not factor cryptographic moduli and no such capability is claimed.

### 4.8 Stabilizer (Clifford) path

`turing.algorithms.clifford` evaluates Clifford circuits (H, S, CNOT and Paulis) exactly with an Aaronson–Gottesman tableau stored as integer bitsets: 2n(2n + 1) bits, about 3 MiB at 2,500 qubits. Z-basis measurement returns a deterministic outcome with probability 1 or two outcomes with probability exactly 1/2 each. This path carries the 2,500-qubit instances: a GHZ state, Deutsch–Jozsa with affine oracles, Bernstein–Vazirani with linear oracles, Simon with linear oracles and dyadic QPE. The qubit count is read from the register each circuit allocates.

## 5. What 2,500 qubits means in TURING

| Instance class | Exact at 2,500 qubits | Reason |
|---|---|---|
| Clifford circuits (stabilizer states, GHZ, code encoders, affine DJ, linear BV and Simon) | Yes | Tableau of O(n²) bits |
| QPE with dyadic eigenphases | Yes | Semiclassical inverse QFT on exact phase exponents |
| Grover, small iteration counts, any N | Yes | Two-term rational recurrence |
| Grover at the optimal iteration count, N = 2^2500 | No | About 2^1249.65 iterations |
| Shor for an n-bit modulus | Small n only | Sum over 2^(2n) inputs; about 10^616.5 for n = 1,024 |
| General non-Clifford circuits | No | Dimension 2^n (about 10^752.6 at n = 2,500) with no structure to fold |
| Physical-model Hamiltonians (Hubbard, lattice gauge theories) | No | Same dimension argument; on quantum hardware these need QPE on fault-tolerant logical qubits |

Published resource estimates in the 2,000–2,500 qubit range concern logical qubits on fault-tolerant quantum hardware. For example, Roetteler, Naehrig, Svore and Lauter (2017) bound the elliptic-curve discrete logarithm over an n-bit prime field at 9n + 2⌈log₂ n⌉ + 10 logical qubits, which is 2,330 for n = 256, with at most 448n³log₂n + 4090n³ Toffoli gates, about 1.29 × 10^11. Those figures describe quantum machines and do not transfer to exact classical evaluation.

## 6. Interfaces with Hendrix, Hermes and the iGPU

- **Hendrix** supplies oracles through the contract in section 3; integration tests live on the Chronus side.
- **Hermes** (`chronus.hermes`, the bounded Fourier and state modules) works in floating point with a stated tolerance. It may be used to cross-check exact TURING results converted to floating point, never inside an exact path.
- **iGPU tensor** (`chronus.igpu.tensor`) is a numerical tensor network with explicit truncation records. TURING does not import it: doing so would put IEEE-754 values into the exact path and create a dependency cycle between the two distributions.

## 7. Test requirements

Every module ships tests in `packages/turing/tests/` whose file names start with `test_turing_`, covering at least: the field axioms and deg Φ_n = φ(n) for n = 1 to 30; the reduction homomorphism (Φ_256(3) ≡ 0 mod 257, products and sums preserved); Deutsch–Jozsa and Bernstein–Vazirani for every case with n ≤ 6; Simon for n = 2 to 5; Grover folded against unfolded for every N ≤ 32 and every M; QFT unitarity for Q in {1, 2, 3, 4, 5, 6, 8}; QPE for dyadic phases with t = 1 to 8, a non-dyadic phase and the F_257 instance; Shor for N = 15 and N = 21 and the factoring of both; and the 2,500-qubit stabilizer instances in 4.8. Tests also scan the package for floating-point use and for any import of `chronus`. The whole suite runs in under a minute. Test evidence is recorded with commit, environment, command and result, as README.md requires.

## 8. Delivery boundary

TURING is internal. Its distribution carries the classifier `Private :: Do Not Upload`, and it reaches participants only as a black box: results returned by HYBA's hosted service or, where a site cannot connect, a sealed appliance whose contents the participant cannot access. No source, wheel or compiled module of TURING is delivered in a form a participant can read; see `docs/distribution/partner-distribution.md`.

## 9. Changes from the 11 November draft

| Draft statement | Specification | Reason |
|---|---|---|
| "ω₁₆ = 3^16 ≡ 136 (mod 257)" | 3^16 ≡ 249 (= −8) has order 16; 136 = 3^8 has order 32 | Computed |
| Phase kicks and amplitudes carried in F_257 | Amplitudes in Q(ζ_m); F_257 is a reduction used for checksums | F_257 has no absolute value and the reduction is many-to-one |
| `FoldedRegister.tensor_state: EnhancedTensorRepresentation` imported from `chronus.igpu.tensor` | Algorithm-specific exact folded representations inside `turing` | The tensor network is floating point with truncation records, and the import would create a cycle |
| Package `chronus.turing` | Package `turing` | Matches the distribution and the dependency direction |
| "O(1)" folded evaluation of DJ, BV and Simon | One query on quantum hardware; exact evaluation reads every input unless the oracle is affine or linear, when the stabilizer path applies | Cost statement made precise |
| "11D 600-cell polytope" | The 600-cell is 4-dimensional with 120 vertices, as the code's own invariants assert | Mathematical fact |
| "Every qubit intrinsically fault-tolerant"; "no difference between physical and mathematical qubits" | "Zero numerical error: exact amplitudes, exactly normalised, reproducible bit for bit" | Fault tolerance describes physical quantum devices under noise; TURING runs on classical hardware and has no noise to tolerate |
| 2,500-qubit cryptanalysis and open-problem applications | Section 5 envelope | Not reachable by exact classical evaluation and not claimed |
