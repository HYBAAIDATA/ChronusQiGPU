# Grover in O(1): Exact Rational Two-Amplitude Symmetry Folding over Hensel-Lifted GL(2, Z/2^k Z) Rings

### Quantum Is the Mathematics: substrate- and hardware-agnostic exact algebraic amplitude folding

*HYBA AI DATA — ChronusQiGPU. Technical report, draft of 18 November 2026. Markdown twin of
`grover_in_o1_exact_ring_folding.tex`; both files carry the same content.*

## Abstract

**Thesis: quantum is the mathematics.** The quantum mechanics that quantum algorithms use is a mathematical
structure: state vectors, unitary evolution, phase inversion, interference, and reduction by symmetry. It is not a
cryostat or a particular piece of silicon. This is one instance of the authors' architectural law, stated in their
`unified_quantum_engine.py` (§1.2). Its first part is that quantum mechanics is the operator algebra. Its second
part is "no royal road to geometry": every problem class passes through one three-layer channel, and a new domain
is declarative data, never new core algebra. The engine's own tests verify the second part for the domains they
exhibit; universality is a design principle. We make the first part concrete, and exact, for Grover amplitude
amplification.

When the state space carries the symmetry of a single marked class (M of N states), the unitary dynamics restrict
exactly to a two-dimensional invariant subspace [1, 2, 3]. With amplitudes scaled by √N, those dynamics are a
rational recurrence on (α_t, β_t) ∈ ℚ². We execute that recurrence exactly on an ordinary CPU: phase inversion,
then inversion about the mean, with norm conservation asserted at every step. There is no floating point, no π
and no truncation, and for N < 64 the full 2^N-amplitude vector is stepped alongside and agrees at every step.

The peak is found by exact stepping and certified by an independent π-free Chebyshev criterion: N = 16 → 3
iterations with P = 63001/65536, N = 4096 → 50, N = 65536 → 201. **"O(1)" means precisely O(1) amplitude state per
step, made possible by the symmetry.** It is memory per step. The iteration count is still Θ(√(N/M)), and the
rationals' bit length grows linearly in t·log N, so it does not mean O(1) time or O(1) bit operations.

**The thesis is only as strong as its separation, so we measure both sides.** The amplitude algebra runs exactly
on any substrate. The oracle is the problem's interface, and its cost is set by the oracle's structure, not by the
algebra. On classical hardware the marked count must be learned by evaluating the oracle on all W candidates, so
oracle cost is Θ(W). Exact amplitude algebra therefore gives **no query speed-up** on classical hardware; that
needs a coherent quantum oracle.

The production pipeline has four parts:

* the Hensel-lifted matrix M_k ∈ Γ(2) ≤ GL(2, ℤ/2^kℤ), of order 2^(k−1), with inverse M_k − tr(M_k)·I because det M_k = −1;
* a factored O(N) register that folds, and never truncates, 2^N states;
* a bijective Lucas–Pisano schedule;
* SHA-256 hash-chained THESEUS receipts.

On 500 Bitcoin mainnet headers at k = 32, it finds and re-verifies every winner at W = 4096 and W = 65536, using
W SHA-256d evaluations per window. That is about twice a linear scan's expected cost.

Beyond mining, M_k ≡ I + 2Q (mod 4), where Q is the Fibonacci matrix. This makes orbit, trace, order-finding and
polynomial oracles 2-adically continuous, so generator collapse performs Hensel lifting and cuts oracle
evaluations from W to a few dozen. That saving is classical: Hensel lifting and Pohlig–Hellman match or beat it.
SHA-256d and dense subset-sum oracles lack the structure.

**The mathematics is golden by construction.** Each golden identity does a specific job:

* Binet gives M15 = Q¹⁵ mod 256;
* Cassini gives det = −1 and so the inverse M − tr·I, which is OVID's unfold map ((135, 98), (98, 37));
* Lucas gives tr M15 = L15 ≡ 84 and the odd schedule strides;
* Pisano gives the period 3·2^(D−1) and ord M_8 = 384/gcd(15, 384) = 128;
* Pisot makes L_n the exact integer anchor of φ^n.

The Grover iterate and the Fibonacci matrix obey the same Dickson trace recurrence. The Grover iterate is elliptic
(det 1, a rotation), while Q is hyperbolic (det −1, the Pisot regime). That is an exact identity, not a speed-up.

We sweep S = 10^7 … 10^76. The production register runs at every ring k = ⌈log₂ S⌉ up to 253, with exact custody.
The Grover peak for N = S is known three ways:

* by exact stepping, at 10^7;
* by an exact integer Chebyshev certificate, at 10^7, 10^10 and 10^12;
* by a π-free rational-interval angle certificate, at all nine scales, up to t* = 78539816339744830961566084581987572104
  at 10^76.

A quantum query advantage requires quantum hardware.

## 1. Thesis: Quantum Is the Mathematics

### 1.1 Statement

A quantum algorithm is specified by algebra: a state space, unitary operators, and the Born rule. Grover's
algorithm [1] on N states uses two reflections:

* the phase inversion O = I − 2Π_marked, which flips the sign of the M marked amplitudes;
* the diffusion D = 2|s⟩⟨s| − I, which inverts every amplitude about the mean. This is where interference happens.

Both are real orthogonal matrices. Let |good⟩ and |bad⟩ be the normalised uniform superpositions over the marked
and the unmarked states. The two-dimensional subspace span{|good⟩, |bad⟩} is invariant under O and D, and the
start state lies in it [2, 3]. In the scaled coordinates (α, β), where the amplitude is α/√N on each marked state
and β/√N on each unmarked one, the iterate G = D·O is the rational map of §6:

  μ = (Uβ − Mα)/N,  α′ = 2μ + α,  β′ = 2μ − β.

The dynamics are therefore defined over ℚ. Any machine that performs exact rational arithmetic executes them
exactly: a CPU, an integrated GPU, or a quantum device. That is the sense in which we say the mathematics is the
quantum part, and it is substrate- and hardware-agnostic. Our implementation (`triad_grover.py:36`) asserts the
unitarity invariant Mα² + Uβ² = N exactly at every step (:59). For N < 64 it steps the full 2^N-dimensional
rational vector alongside and checks equality, so the fold and the unfolded dynamics agree exactly, not
approximately.

### 1.2 The authors' architectural law

The thesis is one instance of an architectural law that the authors state, and partly test, in their engine
`unified_quantum_engine.py`. That engine is a user-supplied file of 4,434 lines, SHA-256 `2656ba4d…735eb`, and it
is not part of this repository. Line numbers below refer to that file.

> **Law (a). Quantum mechanics is the operator algebra.** State preparation, decoherence written as Kraus channels,
> measurement as a POVM, and exact rational or ring symmetry folding are mathematical operations. They do not depend
> on a cryostat or on any particular silicon. The engine's docstring (lines 58–59) puts it this way: "Quantum
> mathematics is mathematics. Computing U|ψ⟩ on a CPU is evaluating a function on Hilbert space. The substrate is
> irrelevant to the algebra."
>
> **Law (b). There is no royal road to geometry.** Every problem class collapses into the same three-layer channel:
>
> 1. the surface algebra of states, operators, fidelity kernels and the Born rule;
> 2. "the code beneath the code", which reads a data pipeline as state preparation, basis selection, decoherence
>    and POVM measurement;
> 3. exact golden arithmetic (`GoldenArithmetic`, line 2231; `StateCheckpoint`, line 2392) as the integrity
>    backbone.
>
> A new domain is declarative data, never new core algebra. It is a `DomainProfile` (line 1130) that declares
> required columns, primary signals, informative absence, extractors, and a series or cross-sectional mode. It is
> registered in `DomainRegistry` (line 1167).

**What is verified in code.** We ran the engine's own suites on CPython 3.13.5 with numpy 2.5.5, pandas 3.1.1 and
scikit-learn 1.9.1. `RegressionSuite` passed 43/43 and `TheoremVerificationSuite` passed 11/11. Three results bear
on the law:

* **`RegressionSuite.new_domain_is_data_not_code` (line 4165).** A domain that does not exist in the code,
  `retail_test`, is declared as a `DomainProfile` and registered. It is then fitted and queried through
  `UnifiedAnalyticsSession` with no change to the engine. Violating its required-column contract or its width
  contract raises `DataContractError`.
* **`RegressionSuite.two_domains_one_session` (line 4194).** Fintech (cross-sectional) and supply chain (series)
  run on one engine in one session. Each gets its own derived feature layout and mode. On each one, the 95%
  accuracy interval clears the majority-class rate, on the engine's synthetic demo data.
* **The golden backbone is exact.** `GoldenArithmetic` is pure integer arithmetic, with the Pisano period
  3·2^(k−1) and Cassini and Lucas certificates on every fold matrix. Our test
  `test_engine_golden_arithmetic_matches_chronus_exactly` (`tests/test_paper_claims.py`) checks three things
  exactly, for bits ∈ {8, 16, 64, 256} and step counts up to 10^76:
  * the engine's `fold_matrix` equals Q^n mod 2^bits as computed here;
  * `fold_matrix(15, 8)` is M15;
  * `unfold_matrix` is an exact inverse.

**What is a design principle.** The claim that *every* problem class reduces to this channel is an architectural
principle, not a theorem. The tests exhibit four domains (hr, fintech, supply_chain, retail_test). They do not, and
cannot, prove universality. The engine scopes itself in its docstring (lines 61–69): numbers must exist first
(text, images, audio and graphs need an encoder), and "No speedup is claimed".

**What is an interpretation.** The Layer-2 identifications are the engine's stated readings:

* median fill as a depolarising channel;
* zero fill as amplitude damping;
* absence flags as which-path records;
* completeness as purity;
* the model ensemble as a POVM.

They are exact as definitions. They are computed in floating-point numpy, so they are not exact-arithmetic
computations. The exact-arithmetic parts of the law are the engine's Layer 3 and, in this paper, the two-amplitude
fold.

**How this paper instantiates it.** The Grover pipeline here (CHRONUS, OVID, THESEUS) does not import the engine or
`DomainProfile`. It is a separate, exact instance of law (a). Its problem classes, Bitcoin headers and the eight
stress families of §7.2, enter only as oracles; the amplitude algebra is unchanged between them. That is the
paper's own, narrower form of law (b). The separation in §1.3 applies unchanged: Θ(W) oracle cost and no query
speed-up on classical hardware.

### 1.3 The rigorous separation, and why it strengthens the thesis

A thesis about mathematics should be stated with mathematical precision about what it does and does not imply.

1. **What is O(1).** The state per step is two rationals, and that is a consequence of symmetry. A generic quantum
   state without such symmetry needs up to 2^N amplitudes. The fold is a symmetry reduction, not a general
   compression of quantum computation. **O(1) is memory per step; the number of steps is Θ(√(N/M))**, the same as
   Grover's query count, so the classical run time is never below Θ(√N) steps (§10).
2. **Bit growth.** The rationals' denominators grow: 17, 1013 and 5645 bits at the peaks for N = 16, 4096 and
   65536 (§6). The cost per step in bit operations grows linearly in t·log N.
3. **The oracle is not the algebra.** The marked set enters only through Π_marked. To instantiate the fold, M must
   be known. On classical hardware that costs W oracle evaluations, Θ(W) for an unstructured oracle such as
   SHA-256d (§7.1). A quantum device queries the oracle coherently, about (π/4)√(N/M) times. That query advantage
   is a property of a physical, coherent oracle, and it is not reproduced, or claimed, on classical hardware.
4. **Prior work.** The two-dimensional reduction is classical knowledge [1, 2, 3]. Our contribution is the exact,
   π-free and attested realisation inside a production pipeline, and the measured boundary below.
5. **Structure is classical.** Where an oracle has 2-adic structure (Corollary 3.5), generator collapse prunes
   by successive binary reductions of the admitted search domain. Classical algorithms (Hensel lifting, Pohlig–Hellman) achieve the same pruning, so it is not
   evidence that quantum hardware would do better (§7.2, §8).

Separating the substrate-agnostic amplitude algebra from the substrate- and structure-dependent oracle cost is
what makes the thesis checkable. Every claim on the algebra side is an exact identity that we test. Every claim on
the oracle side is an exact count that we measure.

### 1.4 Evidence

* **Exact dynamics.** Peaks are 16 → 3 with P = 63001/65536 exactly, 4096 → 50 and 65536 → 201. They are
  certified by the exact Chebyshev form P_t = (1 − T_(2t+1)(1 − 2M/N))/2 at every step (§6).
* **Mining.** At k = 32 on 500 verified mainnet headers, every winner is found and re-verified at W = 4096 and
  W = 65536. The pure two-amplitude loop takes 1.608 ms and 28.725 ms, and the full attested pipeline 143.015 ms and
  433.841 ms. The pipeline uses W SHA-256d evaluations per window (§7.1).
* **Structured-oracle stress test.** At k = 32 the structure-exploiting pipeline needs 32 / 40 oracle evaluations
  for the orbit hidden shift and for order finding, against 4096 / 65536 for the triad as built. Classical
  structured methods need 25 / 33 and 11 / 15. On SHA-256d and dense subset sum the 2-adic structure is absent
  (§7.2).
* **Golden structure and scale.** Binet, Cassini, Lucas, Pisano and Pisot each carry an exact identity that the
  code uses (§9). The ring, register and custody run exactly at k = 24…253, and t* is certified for N up to 10^76
  (§10).

## 2. Scope and claims

We claim four things:

* **C1.** Exact execution of Grover's two-amplitude dynamics in ℚ², with an exact peak and an exact success probability, and
  no floats or π anywhere in the computation.
* **C2.** Exact algebra of the Hensel-lifted M_k and of the Lucas–Pisano schedule, with proofs (§3–5).
* **C3.** An end-to-end, attested implementation that is correct on real data (§6–7).
* **C4.** A measured boundary between structured and unstructured oracles (§7.2, §8).

We do **not** claim a quantum speed-up, sub-linear oracle cost on classical hardware, or novelty of the
two-dimensional reduction. All code references are to branch `exp/attractor-stress`, based on
`feat/grok-triad-grover` @ `3072a50d`. Every proposition below is checked exactly by
`tests/test_paper_claims.py` (37 tests), `tests/test_golden_scales.py` (50 tests) and
`tests/test_attractor_stress.py` (101 tests).

## 3. The Hensel-lifted matrix M_k

**Definition 3.1.** `hensellift_m15(k)` (`src/chronus/kernels/gl2_transform.py:60`) returns
M_k = [[219, 98], [98, c_k]] with c_k = (98² − 1)·219⁻¹ mod 2^k, for every k ≥ 8. `FoldedRegisterN` accepts
8 ≤ k ≤ 255 (§10). Then
c_8 = 121, and M_8 = M15 = Q¹⁵ mod 256, where Q = [[1, 1], [1, 0]] and Q^n = [[F_{n+1}, F_n], [F_n, F_{n−1}]].
The values F_16 = 987, F_15 = 610, F_14 = 377 reduce to 219, 98, 121. The construction gives
det M_k = 219·c_k − 98² ≡ −1 (mod 2^k), M_k ≡ M15 (mod 256), and tr M_8 = 340 ≡ 84 = L_15 (mod 256).

**Proposition 3.2 (level-2 congruence subgroup).** M_k ≡ I (mod 2). Moreover **M_k = I + 2A with A ≡ Q (mod 2)**,
i.e. M_k ≡ I + 2Q (mod 4).

*Proof.* (219 − 1)/2 = 109 and 98/2 = 49 are odd. The value c_k is odd because det ≡ −1 forces 219·c_k odd, and
(c_k − 1)/2 is even because M_k ≡ M15 (mod 256) forces c_k ≡ 121 (mod 256), hence c_k ≡ 1 (mod 4), for every k ≥ 8. So A mod 2 = [[1, 1], [1, 0]] = Q. ∎

So M_k lies in Γ(2) := ker(GL(2, ℤ/2^k) → GL(2, ℤ/2)). Note that Γ(2) is taken in GL₂, because det M_k = −1.

**Lemma 3.3 (squaring).** If X = I + 2^j B with j ≥ 2 and B ≡ I (mod 2), then X² = I + 2^(j+1) B′ with B′ ≡ I (mod 2).

*Proof.* X² = I + 2^(j+1)(B + 2^(j−1) B²), and 2^(j−1) B² ≡ 0 (mod 2) for j ≥ 2. ∎

**Theorem 3.4 (order 2^(k−1)).** For k ≥ 3, M_k has multiplicative order exactly 2^(k−1). More precisely,
M_k^(2^t) = I + 2^(t+1) B_t with B_t ≡ I (mod 2) for t ≥ 1.

*Proof.* M² = I + 4(A + A²), and A + A² ≡ Q + Q² = 2Q + I ≡ I (mod 2), using Q² = Q + I. Lemma 3.3 then gives the
form of M^(2^t) for every t ≥ 1. For t = k − 2 we get M^(2^(k−2)) = I + 2^(k−1) B with B having odd diagonal, so
it is not I mod 2^k. For t = k − 1 we get M^(2^(k−1)) ≡ I. Since Γ(2) is a 2-group, the order is a power of 2,
hence exactly 2^(k−1). ∎

(Checked for k = 8, 16, 32, 64, and at the nine scale rings k = 24…253; for k = 8 the order is 128.)

**Corollary 3.5 (2-adic continuity).** M_k^(x + m·2^t) ≡ M_k^x (mod 2^(t+1)) for all x, m, t ≥ 0. Hence
x ↦ M_k^x v is continuous with shift 1: its residue mod 2^(t+1) depends only on x mod 2^t. If v ≡ 0 (mod 2^s),
the shift is 1 + s. This is the structural property exploited in §7.2.

**Proposition 3.6 (Cayley–Hamilton inverse).** Every M ∈ GL(2, ℤ/2^k) satisfies M² − tr(M)·M + det(M)·I = 0, so
M⁻¹ = det(M)⁻¹ (tr(M)·I − M). **With det M = −1 this becomes M⁻¹ = M − tr(M)·I.**

The code implements exactly this formula. `invert_gl2_mod2k` (`gl2_transform.py:74`) tests `det == mask`
(i.e. det ≡ −1) and returns ((m00 − tr, m01), (m10, m11 − tr)) at lines 88–93. That matrix equals
[[−c, b], [b, −a]] = −adj(M), consistent with det⁻¹ = −1. Other units use det⁻¹·adj(M) (lines 94–99), and the
result is verified by an explicit product M·M⁻¹ = I (lines 101–106). The sign is therefore handled correctly:
writing M⁻¹ = tr(M)·I − M would be wrong by a factor −1 when det = −1.

## 4. FoldedRegisterN: an O(N) factored register ("we fold, we never truncate")

`FoldedRegisterN` (`gl2_transform.py:740`) represents the 2^N states

  s(i) = base + Σ_j bit_j(i)·g_j ∈ (ℤ/2^k)², i ∈ [0, 2^N),

by the N + 1 vectors (base, g_0, …, g_(N−1)), plus a resolved mask and resolved bits.

* **Folding** (`fold_mk`, :814) applies M_k to the N + 1 vectors. By linearity this folds all 2^N states, at a cost
  of N + 1 matrix–vector products.
* **Unfolding** (:817) applies the Cayley–Hamilton inverse.
* **Evaluation** (`evaluate_index`, :821) costs O(N) additions per index.
* **Collapse** (`collapse_generator`, :842) absorbs g_j into the base when the bit is 1, zeroes g_j and records the
  bit. Collapse commutes with folding.
* **Serialisation** (`to_wire_bytes`, :873) is lossless: an 18-byte header plus 2⌈k/8⌉(N + 1) bytes, inside a
  `GL2\x01` v2 frame with CRC-32C. For k = 32 and N = 12 the frame is 142 bytes.

There is no truncating code path. The lossy lane-0 projection exists only in a test-only audit fixture.

## 5. The Lucas–Pisano geodesic schedule

The visit order at epoch e (`src/chronus/geodesic/scheduler.py:80, :100`) is built as follows:

* π = π(2^D) and phase = e mod π;
* idx = 3·phase + 1;
* stride = L_idx mod 2^D and off = F_idx mod 2^D;
* order[t] = gray((stride·t + off) mod 2^D), where gray(x) = x ⊕ (x >> 1).

**Proposition 5.1.** L_n is even if and only if 3 | n. Hence gcd(L_(3m+1), 2^D) = 1.

*Proof.* L_n mod 2 runs 0, 1, 1, 0, 1, 1, … (L_0 = 2, L_1 = 1), with period 3. ∎

**Theorem 5.2 (Pisano period).** π(2) = 3 and π(2^D) = 3·2^(D−1) for D ≥ 2 [9].

*Proof.* π(m) is the order of Q mod m. Q³ = [[3, 2], [2, 1]] = I + 2Q, so Q⁶ = I + 4(Q + Q²) = I + 4(I + 2Q).
Lemma 3.3 with B = I + 2Q ≡ I gives Q^(3·2^(D−1)) = I + 2^D B′ ≡ I and Q^(3·2^(D−2)) ≢ I (mod 2^D). For D = 2,
Q³ = I + 2Q ≢ I (mod 4). The order mod 2 is 3, so the order mod 2^D is 3·2^j for some j, and the two facts force
j = D − 1. ∎ (Checked for D = 1..20.)

**Proposition 5.3 (bijection).** An affine map t ↦ stride·t + off with odd stride is a bijection of ℤ/2^D, and gray
is a bijection of [0, 2^D). The schedule is their composition, so it visits every state exactly once.

**The Hamming spread, stated truthfully.** Gray coding gives single-bit steps only between consecutive integers.
The measured step histograms are exact for D = 12 and D = 16:

* **Epoch 0** (stride L_1 = 1): {1: 2^D − 1}, a pure Gray walk. This is the epoch the pipeline uses, because staged
  handles have version 0.
* **Epoch 1** (stride L_4 = 7): {1: 2^(D−2) − 1, 3: 3·2^(D−2)}.
* **Epoch 2** (stride L_7 = 29): {1: 2^(D−4), 3: 36863, 5: 24576} at D = 16.

The schedule is a permutation, so it cannot change the expected position of a uniformly placed winner.

## 6. Exact two-amplitude Grover

Write the state as (1/√N)(α on each of the M marked states, β on each of the U = N − M unmarked states), starting
from (α_0, β_0) = (1, 1). One Grover iterate is an oracle sign flip followed by inversion about the mean
(`src/chronus/quantum/triad_grover.py:36`):

  μ = (U·β − M·α)/N,  α′ = 2μ + α,  β′ = 2μ − β.

**Invariant.** Mα² + Uβ² = N; it is asserted exactly at every step (:59). P_t = Mα_t²/N.

**Theorem 6.1 (closed form, π-free).** Let c = 1 − 2M/N ∈ ℚ, which is cos 2θ for sin²θ = M/N, and let T_n be the
Chebyshev polynomials. Then P_t = (1 − T_(2t+1)(c))/2, and the recurrence agrees with this at every step.
In particular P_3 = 63001/65536 for N = 16, M = 1 (with α_3 = 251/64, β_3 = −13/64), which equals
(7s − 56s³ + 112s⁵ − 64s⁷)² for s = 1/4.

*Proof sketch.* The iterate acts on span{|good⟩, |bad⟩} as a rotation by 2θ [2, 3], so P_t = sin²((2t+1)θ) =
(1 − cos((4t+2)θ))/2, and cos(nφ) = T_n(cos φ) with φ = 2θ. The identity is verified in exact rationals for every
step of every trajectory in the test suite. ∎

**Theorem 6.2 (exact peak by stepping).** For M ≤ N/2, `exact_grover_two_amplitude_trajectory` (:46) stops at the
first t with P_(t+1) ≤ P_t. That t equals t* = min{t ≥ 0 : T_(t+1)(c) ≤ 0}, which is the iteration where (2t+2)θ
first reaches π/2. It is the maximiser of P over the first rising run.

*Proof.* With φ_t = (2t+1)θ, we have P_(t+1) ≤ P_t ⇔ |φ_(t+1) − π/2| ≥ |φ_t − π/2| ⇔ φ_t + φ_(t+1) ≥ π ⇔
cos((2t+2)θ) = T_(t+1)(c) ≤ 0. ∎

Both criteria are exact rational tests. The certified values are:

| N | M | t* | P_(t*−1) | P_(t*) | P_(t*+1) | bits in denominator of P_(t*) |
|---|---|---|---|---|---|---|
| 16 | 1 | 3 | 0.908447265… | **63001/65536 = 0.961318969…** | 0.581704139… | 17 |
| 4096 | 1 | 50 | 0.999430885… | 0.999945346… | 0.998507371… | 1013 |
| 65536 | 1 | 201 | 0.999980762… | 0.999988259… | 0.999873691… | 5645 |

Decimals are truncations of the exact Fractions. The isqrt(N/M) + 2 step bound never binds for N = 2^D,
D ≤ 24, M ∈ {1, 2, 3, 5}. For N < 64 the full 2^D Fraction vector is stepped alongside the two-amplitude state and matches it exactly.

**Cost.** Each step manipulates O(1) rationals: O(1) memory per step, Θ(√(N/M)) steps. Their bit length grows linearly in t, as the last column shows, so
"O(1)" refers to state, not to bit operations. To run Grover at all, the pipeline must know M. On classical
hardware M is obtained by evaluating the oracle on all W states.

## 7. Implementation, attestation and measurements

The pipeline is `ProductionTriad.exact_grover_search` (`src/chronus/triad.py:119`) calling
`run_triad_exact_grover_search` (`triad_grover.py:105`):

1. CHRONUS builds `FoldedRegisterN` over (ℤ/2^32)², with lane 0 = ntime and lane 1 = nonce.
2. OVID (the real `OvidTransformService`) folds the `GL2\x01` frame and materialises it with SHA-256 checks.
3. THESEUS (the real SQLite-WAL `DurableTheseusService`) stores every version under shard id `{artifact}:v{n}` and
   appends canonical-JSON receipts carrying their own CRC-32C and SHA-256 to a hash-chained journal
   (`src/chronus/ovid/folded_custody.py:173–242`).
4. The oracle is evaluated on every materialised state.
5. The exact Grover runs to its peak.
6. The winner is collapsed generator by generator, with one THESEUS shard per step.
7. A `GROVER_TARGET_VERIFIED` receipt is appended, and the winner is re-verified with a fresh SHA-256d.

A correctness fix was made while writing this paper, at `triad_grover.py:174` (`:172` on `3072a50d`). The winner
index omitted generators collapsed before the search. That path is not used by `ProductionTriad`, so §7.1 is
unaffected.

### 7.1 Bitcoin mining benchmark (k = 32, 500 verified mainnet headers, offline)

This comes from `benchmarks/triad_grover_k32/RESULTS.md` on `feat/grok-triad-grover`.

| | W = 4096 (N = 12) | W = 65536 (N = 16) |
|---|---|---|
| correct winner (nonce and block id), fresh SHA-256d re-verification | 500/500 | 500/500 |
| marked states per window | exactly 1 | exactly 1 |
| Grover iterations (exact peak) | 50 | 201 |
| **SHA-256d evaluations, triad** (oracle on every state) | **4096** | **65536** |
| linear scan, mean evaluations to first hit | 2030.312 | 31537.896 |
| winner position, Lucas–Pisano order (mean) | 2037.726 | 32183.096 |
| headers where the geodesic position beats the linear one | 243/500 | 249/500 |
| wall time (ms, mean): pure two-amplitude loop | 1.608 | 28.725 |
| wall time (ms, mean): full pipeline | 143.015 | 433.841 |
| wall time (ms, mean): linear scan to first hit | 3.113 | 50.220 |
| THESEUS shards / receipts / bytes per header | 13 / 14 / 1846 | 17 / 18 / 2958 |
| journal continuity verified; restored after restart | 500/500; 500/500 | 500/500; 500/500 |

### 7.2 Attractor stress test (k = 32; k = 16 and 64 in the companion report)

This comes from `docs/papers/attractor_stress_results.md`. The cost unit is one oracle evaluation, i.e. one
evaluation of F(state). The columns are:

* (i) linear scan to first hit;
* (ii) the triad as built, which evaluates all W states;
* (iii) the structured triad: graded residue tests drive `collapse_generator` (Hensel lifting through OVID/THESEUS),
  then exact Grover runs on a 16-state residual per branch;
* (iv) the best classical method;
* (q) the ideal Grover query count, **a quantum-machine count that was not run**.

| family (W = 4096 / 65536) | 2-adic continuity | (i) | (ii) | (iii) | (iv) best classical | (q) |
|---|---|---|---|---|---|---|
| orbit hidden shift M_k^x v₀ = w | 100% | 3790 / 57038 | 4096 / 65536 | 32 / 40 | 25 / 33 (Pohlig–Hellman lift [5]) | 50 / 201 |
| trace fibre tr(M_k^x) = τ | 100% | 578 / 12866 | 4096 / 65536 | 360 / 488 | ≤ 248 / ≤ 376 (bit lift) | 50 / 201 |
| order finding (4 targets) | 100% | 1024 / 16384 | 4096 / 65536 | 32 / 40 | **11 / 15** (repeated squaring) | 25 / 100 |
| triangular linear congruence | 100% | 2246 / 14534 | 4096 / 65536 | 32 / 40 | **1 / 1** (back-substitution) | 50 / 201 |
| quadratic, simple roots | 100% | 334 / 12622 | 4096 / 65536 | 62 / 78 | **1 / 1** (Newton–Hensel [4]) | 50 / 201 |
| x² = r, non-simple roots | 100% | 26 / 57370 | 4096 / 65536 | 106 / 138 | 78 / 110 (2-adic sqrt lift) | 50 / 201 |
| dense subset sum | 1.4% / 1.0% | 1322 / 17706 | 4096 / 65536 | target lost | 128 / 512 (meet-in-the-middle [10]) | 50 / 201 |
| SHA-256d point target | 10.0% / 7.2% (chance) | 897 / 54145 | 4096 / 65536 | target lost | 897 / 54145 (scan) | 50 / 201 |

Ensembles of 481–500 instances per row:
- **Structured families:** the target was found in 100% of instances.
- **Dense subset sum:** 0 / 481 and 0 / 499.
- **SHA-256d over 500 real headers:** 1 / 500 at each window size, which is chance level.

## 8. Boundary and limitations

1. **Classical oracle cost.** The two-amplitude recurrence needs M. Classically, M costs W oracle evaluations, so
   on unstructured oracles such as SHA-256d the pipeline is Θ(W), about 2× a linear scan's expected first-hit cost
   (§7.1). The exact recurrence removes floating-point drift and π; it does not remove oracle work.
2. **Structure pruning is classical.** Where Corollary 3.5 makes the oracle 2-adically continuous, generator
   collapse is Hensel lifting [4], and it cuts W evaluations to tens. The same saving, often a larger one, comes
   from classical algorithms with no amplitude stage: Pohlig–Hellman in the 2-group ⟨M_k⟩ [5], Newton–Hensel,
   back-substitution, and repeated squaring. The quantum part of the architecture contributes nothing to these wins.
3. **Ideal Grover versus classical.** Black-box Grover ignores structure, so (q) is identical for structured and
   unstructured instances. Classical structured methods beat (q) except in three places:
   * trace fibres, where our classical figure is an upper bound and a polynomial-in-k route exists [citation needed];
   * x² = r at W = 4096 only;
   * dense subset sum. Here quantum walks are known to improve the exponent over the best classical algorithms:
     2^(0.241n) [6] and 2^(0.226n) [7], against 2^(0.291n) [8].

   That advantage requires a fault-tolerant quantum computer and was not exercised here.
4. **Any gain from quantum search needs quantum hardware.** Nothing in this work runs on, or simulates beyond bookkeeping, a
   quantum device. The two-amplitude state is the exact classical description of what such a device would do on
   the 2D subspace.
5. **Reproducibility.** Receipt bodies and their SHA-256 values are deterministic. Journal entry hashes include the
   THESEUS wall-clock timestamp, so they differ between runs.

## 9. Golden structure: what each member does, and where

The golden objects are not decoration. Each one carries a specific exact identity that some part of the code
relies on. The table names the identity, the place it is proved here, the code that uses it, and the test that
checks it. Tests are in `tests/test_golden_scales.py` (50 tests) and `tests/test_paper_claims.py` (37 tests).

| member | exact identity | role in the system | code (file:line) |
|---|---|---|---|
| Binet | φ^n = F_(n−1) + F_n·φ = (L_n + F_n√5)/2 in ℤ[φ] | gives Q^n = [[F_(n+1), F_n], [F_n, F_(n−1)]], hence M15 = Q¹⁵ mod 256 | `math/binet_lucas.py:133–146`, `security/al_haras/golden.py:39–56`, `backends/lattice.py:68` |
| Cassini | det Q^n = F_(n+1)F_(n−1) − F_n² = (−1)^n | det M15 = −1, lifted to det M_k = −1, so M_k⁻¹ = M_k − tr·I | `kernels/gl2_transform.py:74, :88`, `storage/phyllotaxis.py:73`, `core/scaling.py:47` |
| Lucas | tr Q^n = L_n = φ^n + ψ^n | tr M15 = L15 = 1364 ≡ 84; schedule stride L_(3m+1) is odd | `geodesic/scheduler.py:34, :80`, `core/scaling.py:43, :74` |
| Pisano | π(2^D) = 3·2^(D−1) = ord(Q mod 2^D) | the schedule's period; ord M_8 = π(256)/gcd(15, π(256)) = 128 | `geodesic/scheduler.py:69`; census `tests/test_gl2_review.py:95` |
| Pisot | ψ^n = L_n − φ^n, abs(ψ^n) = φ^(−n) ≤ 1/F_(n+1) | L_n is the exact integer anchor of φ^n; PVScale scales by index | `core/scaling.py:21–66`, `backends/pv_field.py:19` |
| Zeckendorf | every n ≥ 1 is a unique sum of non-consecutive F_i | storage descriptors and an optional nonce order; **not used in the triad Grover path** | `execution/structural.py:4, :21, :37`, `storage/connectors.py:340, :423`, `execution/mining.py:102` |

The OVID byte map is exactly M15: `fold_pair` (`execution/structural.py:72`) computes
(219x + 98y, 98x + 121y) mod 256, and OVID calls it at `ovid/transform.py:54`. Its inverse `unfold_pair`
(`structural.py:82`, used at `ovid/transform.py:78`) is ((135, 98), (98, 37)) = M15 − 84·I, which is Cassini
(det = −1) and Lucas (tr = L15 ≡ 84) together.

**Proposition 9.1 (Binet in ℤ[φ]).** φ^n = F_(n−1) + F_n·φ for n ≥ 1, and φ^n + ψ^n = L_n, where ψ = 1 − φ.

*Proof.* φ¹ = 0 + 1·φ. If φ^n = F_(n−1) + F_nφ, then φ^(n+1) = F_(n−1)φ + F_n(φ + 1) = F_n + F_(n+1)φ. The same
induction holds for ψ, since ψ² = ψ + 1, and φ + ψ = 1 gives φ^n + ψ^n = 2F_(n−1) + F_n = L_n. With
√5 = 2φ − 1 this is (L_n + F_n√5)/2. ∎ (Checked in ℤ[φ] up to n = 364.)

**Corollary 9.2 (Q^n, M15, Cassini).** Q^n = [[F_(n+1), F_n], [F_n, F_(n−1)]], because Q acts on ℤ[φ] as
multiplication by φ in the basis (φ, 1). Hence det Q^n = (−1)^n, tr Q^n = L_n, and
Q¹⁵ = [[987, 610], [610, 377]] ≡ [[219, 98], [98, 121]] = M15 (mod 256), with det −1 and trace 1364 ≡ 84.

**Proposition 9.3 (Lucas traces of M15).** tr(M15^n) ≡ L_(15n) (mod 256) for all n ≥ 1.

*Proof.* M15 ≡ Q¹⁵ (mod 256), so M15^n ≡ Q^(15n), whose trace is L_(15n). ∎ (Checked for n < 64.)

**Proposition 9.4 (Pisano order of M_8).** ord(M_8) = π(256)/gcd(15, π(256)) = 384/3 = 128 = 2^7.

*Proof.* M_8 ≡ Q¹⁵ (mod 256) and ord(Q mod 256) = π(256) = 384 (Theorem 5.2). The order of g^15 in a cyclic group
of order 384 is 384/gcd(15, 384). Theorem 3.4 gives the same value, 2^(k−1). ∎ The orbit census of
(ℤ/256)² under M15 is {1: 4, 2: 6, 4: 12, 8: 24, 16: 48, 32: 96, 64: 192, 128: 384} orbits
(`tests/test_gl2_review.py:95`).

**Proposition 9.5 (Pisot residual).** abs(ψ^n) = φ^(−n) ≤ 1/F_(n+1). So L_n is the nearest integer to φ^n for
n ≥ 2, and this needs no rounding operation.

*Proof.* φ·ψ = −1 gives abs(ψ^n) = φ^(−n). And φ^n = F_(n−1) + F_nφ ≥ F_(n−1) + F_n = F_(n+1), because φ > 1. ∎
The audit computes ψ^n exactly in ℤ[φ] and checks the norm φ^n·ψ^n = (−1)^n at every scale.

**Proposition 9.6 (one recurrence, two regimes).** Let G be the Grover iterate acting on (α, β). Then

  G = [[1 − 2M/N, 2U/N], [−2M/N, 2U/N − 1]], with tr G = 2c, det G = 1, c = 1 − 2M/N.

Hence tr G^n = 2T_n(c). By comparison, tr Q^n = L_n with tr Q = 1 and det Q = −1. Both sequences obey the Dickson
recurrence x_(n+1) = t·x_n − d·x_(n−1), with (t, d) = (2c, 1) for Grover and (1, −1) for Lucas.

*Proof.* Expand α′ = 2μ + α and β′ = 2μ − β. The determinant is
(1 − 2a)(2u − 1) + 4au = 2(a + u) − 1 = 1, where a = M/N and u = U/N. Cayley–Hamilton gives
X^(n+1) = tX^n − dX^(n−1), so traces obey the same recurrence. With x_0 = 2 and x_1 = 2c it is 2T_n(c). ∎
(Checked exactly for n < 40 at three (N, M).)

This is the exact connection between the golden side and the Grover side, and also the exact difference between
them. Q is hyperbolic: its eigenvalues are φ and ψ, real, with |φ| > 1 > |ψ|. That is the Pisot regime, where
powers grow. G is elliptic: its eigenvalues are e^(±2iθ), on the unit circle. That is a rotation, and the peak
comes after Θ(√(N/M)) turns. The golden structure gives exact, invertible, hash-free arithmetic for addressing,
scheduling and folding. It does not shorten the Grover rotation.

**Remark 9.7 (Lucas traces and closed geodesics; exact part).** This remark comes from
`TheoremVerificationSuite.modular_geodesics_from_lucas` in the authors' engine (line 3412), which checks it in
floating point.

Q has det −1, so it lies in GL(2, ℤ) but not in SL(2, ℤ). Its even powers do lie in SL(2, ℤ): Q^(2k) has det +1 and
trace L_(2k) ≥ 3, so it is hyperbolic. A hyperbolic element of trace t translates along its axis in ℍ² by
2·arccosh(t/2). Here the identity is exact. L_(2k)² − 4 = 5F_(2k)², so the larger eigenvalue is
(L_(2k) + F_(2k)√5)/2 = φ^(2k), which is Proposition 9.1. Hence

  L_(2k) = φ^(2k) + φ^(−2k),  and  2·arccosh(L_(2k)/2) = 2·ln φ^(2k) = 4k·ln φ.

`test_lucas_trace_geodesic_identity_exact` checks the integer and ℤ[φ] parts exactly for k ≤ 200:

* trace L_(2k) and det +1;
* L² − 4 = 5F²;
* φ^(2k) = (L − F)/2 + F·φ;
* φ^(2k)·ψ^(2k) = 1.

At k = 1 the trace is 3, the least hyperbolic trace in SL(2, ℤ), so it gives the shortest closed geodesic of
ℍ²/SL(2, ℤ), of length 4·ln φ. For k > 1, Q^(2k) = (Q²)^k traverses that same primitive geodesic k times. It is not a
new primitive geodesic. This is a geometric fact about the golden matrix. It has no algorithmic consequence here:
the Lucas–Pisano schedule (§5) uses L_(3m+1) mod 2^D only as an odd stride.

**Storage (THESEUS).** `phyllotaxis_coordinate` (`storage/phyllotaxis.py:52`) assigns record n the golden turn
n·F_64/F_66 mod 1. This is an exact rational convergent of 1/φ², and Cassini gives F_64·F_66 − F_65² = −1. Lanes use
the Knuth constant ⌊2^64(φ − 1)⌋ = 0x9E3779B97F4A7C15 (`:18`, `:23`). It is reproduced from integer square roots by
`metallic_conjugate_64(1)` (`:87`). `DurableTheseusService` stores and verifies these coordinates at
`storage/durable.py:165, :216, :291, :409`.

**PV scaling.** `PVScale(i).field_factor()` (`core/scaling.py:57`) is φ^i in 𝔽₂₅₇[φ]. Since 257 ≡ 2 (mod 5), the
polynomial x² − x − 1 is irreducible over 𝔽₂₅₇, so the Frobenius map sends φ to ψ. Then φ^258 = φψ = −1 and
φ^516 = 1, which is the "period-516" reduction at `backends/pv_field.py:19`. This is checked at every scale.

## 10. Scaling from 10^7 to 10^76

For each scale S = 10^d with d ∈ {7, 10, 12, 15, 18, 20, 31, 50, 76}, we take N = S for Grover and
k = ⌈log₂ S⌉ ∈ {24, …, 253} for the ring. Full tables are in `docs/papers/golden_scales_results.md`. The raw data
is `benchmarks/golden_scales/results.json`, produced by `scripts/benchmarks/golden_scales.py` in 36 s on a CPU, of
which 34 s is the exact stepping at 10^7.

**Production register at any k.** `FoldedRegisterN` previously accepted k ∈ {8, 16, 32, 64}. It now accepts any
integer 8 ≤ k ≤ 255 (`gl2_transform.py:723–735`). The lower bound is where `hensellift_m15` is defined; the upper
bound is the one-byte k field of the frame header. Lane width on the wire is ⌈k/8⌉ bytes, so k not divisible by 8
never truncates. The patch is `benchmarks/golden_scales/foldedregistern_any_k.patch`. At every scale, a
16-generator window [S, S + 2^16) completes these steps exactly:

* folds by M_k;
* round-trips its CRC-32C wire frame (140 bytes at k = 24, 1126 bytes at k = 253);
* unfolds by M_k − tr·I;
* commutes collapse with fold;
* is staged by OVID and restored from THESEUS after reopening the database, with a verified journal.

At k = 253 the tests also check det M_k = −1, M_k^(2^252) = I ≠ M_k^(2^251) (order exactly 2^252), the inverse
M_k − tr·I, and the absence of truncation.

| S | k | Lucas idx | Zeckendorf terms | Pisot bound | ring checks | register + custody | t* (N = S, M = 1) | how t* is known |
|---|---|---|---|---|---|---|---|---|
| 10^7 | 24 | 33 | 9 | 2^−22 | ✓ | ✓ | 2483 | exact-stepped; exact-certified; angle |
| 10^10 | 34 | 48 | 16 | 2^−32 | ✓ | ✓ | 78539 | exact-certified; angle |
| 10^12 | 40 | 57 | 15 | 2^−39 | ✓ | ✓ | 785398 | exact-certified; angle |
| 10^15 | 50 | 72 | 18 | 2^−49 | ✓ | ✓ | 24836470 | angle only (Chebyshev 1.2·10^9 bits) |
| 10^18 | 60 | 86 | 27 | 2^−59 | ✓ | ✓ | 785398163 | angle only |
| 10^20 | 67 | 96 | 24 | 2^−66 | ✓ | ✓ | 7853981633 | angle only |
| 10^31 | 103 | 148 | 40 | 2^−102 | ✓ | ✓ | 2483647066449025 | angle only |
| 10^50 | 167 | 239 | 64 | 2^−165 | ✓ | ✓ | 7853981633974483096156608 | angle only |
| 10^76 | 253 | 364 | 97 | 2^−252 | ✓ | ✓ | 78539816339744830961566084581987572104 | angle only |

"Ring checks" means that π(2^k) is the exact order of Q, and that M_k has det −1, order 2^(k−1), the CH inverse
and M_k ≡ M15 (mod 256). The register and custody steps take 27–56 ms per scale. The ring and golden columns take
at most 2 ms each.

**Three levels of knowing t\*.**

1. **Exact-stepped.** The Fraction recurrence runs to the first t with P_(t+1) ≤ P_t (Theorem 6.2). This was
   done at 10^7: t = 2483 in 34 s. It is infeasible beyond about 10^8 here, because there are Θ(√N) steps on numbers
   of O(t·log N) bits.
2. **Exact-certified.** The two integers N^m·T_m(1 − 2/N), for m = t* and t* + 1, have signs (+, ≤ 0). By
   Theorem 6.2 that is equivalent to t* being the peak. There is no π and no enclosure. This was done at 10^7, 10^10
   and 10^12; the last took 1.2 s with 3.1·10^7-bit integers. From 10^15 the integers exceed 10^9 bits, and the
   attempt at 10^15 was stopped.
3. **Angle-certified.** t*·θ < arctan(1) ≤ (t* + 1)·θ, where θ = arctan(1/√(N − 1)) is the Grover angle
   (sin²θ = 1/N). Both sides are rational intervals: θ from integer square roots and the alternating arctan series,
   and arctan(1) = 4·arctan(1/5) − arctan(1/239) (Machin's identity, used as an identity of arctans). The two strict
   inequalities are checked in Fractions. No numerical π and no floating point are used, but this is a rigorous
   rational-interval proof, not a closed form. It certifies the integer t* at every scale in at most 14 ms. It does
   not compute P(t*), whose exact denominator has about (2t* + 1)·log₂N ≈ 4·10^40 bits at 10^76. The certificate
   agrees with exact stepping at N = 4, 16, 100, 4096, 12345, 65536, 10^5 and 10^7. It rejects t* ± 1 for
   N ≤ 10^5 and t* − 1 at all nine scales (tests).

**What scales, and what does not.**

* *These scale:* the golden identities, the M_k ring facts, the register (O(N·k) bits for 2^N states) and
  custody, and the certificate for t*. All are polylogarithmic in S.
* *These do not scale:* the stepping (Θ(√N) iterations), the exact P(t*), and above all the oracle. On classical
  hardware, learning M still costs Θ(W) evaluations, so no scale changes the separation of §1.3.
* *A curiosity, reported as found:* at k = ⌈log₂ S⌉ we always have π(2^k) = 3·2^(k−1) > S, so the Pisano reduction
  S mod π(2^k) is the identity at these scales. It is a real reduction only for indices beyond the ring.

## References

[1] L. K. Grover. A fast quantum mechanical algorithm for database search. *Proc. 28th ACM STOC*, pp. 212–219, 1996.
[2] M. Boyer, G. Brassard, P. Høyer, A. Tapp. Tight bounds on quantum searching. *Fortschritte der Physik* 46(4–5):493–505, 1998.
[3] M. A. Nielsen, I. L. Chuang. *Quantum Computation and Quantum Information*. Cambridge University Press, 2000 (10th anniversary ed. 2010), §6.1.
[4] Hensel's lemma: N. Koblitz. *p-adic Numbers, p-adic Analysis, and Zeta-Functions*. Springer GTM 58, 2nd ed., 1984.
[5] S. C. Pohlig, M. E. Hellman. An improved algorithm for computing logarithms over GF(p) and its cryptographic significance. *IEEE Trans. Inf. Theory* 24(1):106–110, 1978.
[6] D. J. Bernstein, S. Jeffery, T. Lange, A. Meurer. Quantum algorithms for the subset-sum problem. *PQCrypto 2013*, LNCS 7932, pp. 16–33.
[7] A. Helm, A. May. Subset Sum Quantumly in 1.17^n. *TQC 2018*, LIPIcs 111, 5:1–5:15. doi:10.4230/LIPIcs.TQC.2018.5.
[8] A. Becker, J.-S. Coron, A. Joux. Improved generic algorithms for hard knapsacks. *EUROCRYPT 2011*, LNCS 6632, pp. 364–385.
[9] D. D. Wall. Fibonacci series modulo m. *American Mathematical Monthly* 67(6):525–532, 1960.
[10] E. Horowitz, S. Sahni. Computing partitions with applications to the knapsack problem. *J. ACM* 21(2):277–292, 1974.

## Appendix A. THESEUS receipts

**Mining benchmark.** `GROVER_TARGET_VERIFIED` receipts, as journal entry hash / receipt-body SHA-256:

| W | height | nonce | journal entry hash | receipt body SHA-256 |
|---|---|---|---|---|
| 4096 | 976064 | 90468167 | b9038f266ebb89f84f3b5b594ff5632afe7dc8eb4c069c96ad3d2ccb9fa19d53 | 0cea830233894ae9ccea7e8ed879978dbbac95dea00ff96fb695048754822e14 |
| 4096 | 976063 | 1265527642 | 85b6f5d41e318a9de9ca6defe9b6b2d5db0dd84a7d1e2517c05a5216f09581c7 | 62b89992c7c21e95acf496b4fd9a6aa7e307387ccf261f8bfddd036964277f6c |
| 4096 | 976062 | 462700330 | 8652d616c0aeec9367b5d9164f947dcf0ec6fe9427d9cff9a134dcf0f7625574 | a0c6e5ad25b457369bdcd0434aeaa387ac42df9132ab504f771cd40720c8b7bd |
| 65536 | 976064 | 90468167 | 9c665ce9caeba3b918ce3ead411e16742282fba1a8a81590713fd7733afdab46 | 2b03f5a0c14ad313e31015fc31804966f7a6fc6ca67bd74227811833519a9d83 |
| 65536 | 976063 | 1265527642 | 17543fa3f64df08a565517a60bbf7235fe538f428673507d8927c318ce566e77 | 7168befbc4009e9ccdefd684b023ab517a6ff5978bf302f722189482aee8d325 |
| 65536 | 976062 | 462700330 | c19f931d8903e3af92d79c787c3a159360cb2a94d6b8acaa4700f4f8ee7deba2 | 85a31ae5fe80cc557e50d94285c95bbb468301d8a3b29148b417069a7483eebb |

**Stress test, k = 32.** Triad-as-built `GROVER_TARGET_VERIFIED` journal entry hashes. Every tenant chain was
verified with `verify_journal_continuity`. All 44 rows are in `benchmarks/attractor_stress/results.json`.

| family | W = 4096 | W = 65536 |
|---|---|---|
| orbit hidden shift | 6240e50efda809788a2a6ebcb8e2cd51169104bbcc47b3f0dbcbfe1aa652173c | 3aedbd34fb38475fe411c6ea451b94f7d2e05f16632111ed92e4e63e37837648 |
| trace fibre | edca4a8df41f0b5cb48186beb67093f17063a6b87163f743f3d4a26cd610b72e | 3d043b6e3c6bc96aad5bd0536f4238db0a3cf025d6223dcadf4dd020bf962ce4 |
| order finding | acb3f111c1120bf32789a65c25f14518a4ed08ebce7828adf26f19a96e9e50c6 | 15f1a28c0867452f4bfb0f81232efbd9d6e40f360cb1f48b37e745d2139e0a79 |
| triangular linear | b0fe77ad7406e3c7c1cadcfa0d8be4f8db30cbf6df3d48d8bb57dd79d80acf66 | 31b65fcdb937f1b88b410f0c7e939a7f348f287f020f92ebe0744dc0ee91a569 |
| quadratic, simple roots | 10c56dda32e690151ebbe0d18bf7a787eab2bd6873ffdcc63ccac75b20fcfb2e | d172408a1161df5b5039a2b17b4bbc325e0d6840da56ded7b00e7f0ec947dd0b |
| x² = r | eae2cc524f5e3a7aaa8d62abadbe92e75cbd070f6724b9caebe17977977473e6 | a0e73b46dd0e860334d054bd774db90f77ec1693a5bf00e70fac8e4b3f7f90ba |
| dense subset sum | c363cfaf9fca7b82cecb0d419c4eb169d8b6393778509319a78ae51f174933f9 | b500296a0201bb264dc11242552c64470d96df490c9dab3470630d53f39fe25d |
| SHA-256d point target | b5c05083f948e54912450033e22cea00bc57c74a3597d3f73c8c9a7ae584fd2f | 50599be8eccd32bdb0285dfaa22cc3daa23ea4cd5a493668fcb0833a7cd5deab |
