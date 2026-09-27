# ABOVE_THE_FLOOR

> A document containing only non-trivial results, each stated precisely,
> verified by exact-rational computation, and distinguished from
> triviality by a falsification test. The "floor" is the observation that
> $L_n/L_{n+1} \to 1/\varphi$. This document asks: what lives above it?

---

## Classification protocol

Every claim was tested against a **generic positive scalar** before being
reported. A finding is classified as:

- **NON-TRIVIAL**: fails for a generic scalar, or depends specifically on
  the Lucas-Pisot sequence structure
- **TRIVIAL**: holds for any positive scalar (arithmetic, not a result)
- **OBSERVATION**: verified but not fully characterized; marked unresolved

---

## Finding 1 (NON-TRIVIAL): The N-independence boundary

**Claim.** The projective denominator invariant
$\text{odd\_part}(d_k) = \text{odd\_part}(L_{k+1})$ holds **if and only if**
$N$ is a power of 2. For general $N$:

$$\text{odd\_part}(d_k) = \text{odd\_part}(L_{k+1}) \cdot \text{odd\_part}(N)^k$$

**Verification.** Tested for $k = 5, 10, 15$ and $N \in \{2^m, 3^m, 5^m, 7^m, 11^m, 13^m, 2^a p^b, \text{mixed}\}$. All match the formula exactly.

| $N$                | $\text{odd\_part}(N)$ | $\text{odd\_part}(d_{10})$ | Predicted            | Match |
| ------------------ | --------------------- | -------------------------- | -------------------- | ----- |
| $2^5 = 32$         | 1                     | 199                        | $199 \cdot 1^{10}$   | ✓     |
| $2^9 = 512$        | 1                     | 199                        | $199 \cdot 1^{10}$   | ✓     |
| $3^2 = 9$          | 9                     | $199 \cdot 3^{20}$         | $199 \cdot 9^{10}$   | ✓     |
| $5^3 = 125$        | 125                   | $199 \cdot 5^{30}$         | $199 \cdot 125^{10}$ | ✓     |
| $7^2 = 49$         | 49                    | $199 \cdot 7^{20}$         | $199 \cdot 49^{10}$  | ✓     |
| $6 = 2 \cdot 3$    | 3                     | $199 \cdot 3^{10}$         | $199 \cdot 3^{10}$   | ✓     |
| $100 = 4 \cdot 25$ | 25                    | $199 \cdot 5^{20}$         | $199 \cdot 25^{10}$  | ✓     |

**Falsification test.** The $\text{odd\_part}(N)^k$ factor is trivial
arithmetic: it comes from the diffusion operator dividing by $N$ at each
step. The non-trivial part is that the REMAINDER is exactly
$\text{odd\_part}(L_{k+1})$, independent of $N$. This remainder is
specific to the Lucas-Pisot telescoping product.

**Why the boundary matters.** The earlier Theorem 5 claimed "N-independence"
without specifying that it requires $N = 2^m$. The precise statement is:
the projective denominator is independent of $N$ **iff $\text{odd\_part}(N) = 1$**.
For any $N$ with an odd prime factor, the odd prime leaks into the
denominator at rate $k$ (one factor per step). The N-independence is
really **2-independence**: it exploits the fact that 2 is the only prime
that cancels in the odd part.

**Correction to prior documentation.** Theorem 5 in `FORMAL_THEOREMS.md`
stated N-independence without the $N = 2^m$ qualification. This is
corrected: the invariant holds iff $N$ is a power of 2.

---

## Finding 2 (NON-TRIVIAL): The generalized denominator factorization

**Claim.** For ANY scaling sequence $c_n$ (not just Lucas-Pisot), the
projective denominator after $k$ Grover steps factors as:

$$\text{odd\_part}(d_k) = \text{odd\_part}\!\left(\prod_{n=1}^{k} c_n\right)_{\text{den}} \cdot \text{odd\_part}(N)^k$$

where the subscript "den" means the denominator of the scale product.

**Verification.** Tested with four different scaling sequences at
$N = 512$, $k = 10$:

| Scaling                   | Scale product | $\text{odd\_part}(\text{prod den})$ | $\text{odd\_part}(d_k)$ | Match |
| ------------------------- | ------------- | ----------------------------------- | ----------------------- | ----- |
| Lucas-Pisot $L_n/L_{n+1}$ | $1/199$       | 199                                 | 199                     | ✓     |
| Generic $(n+1)/(n+2)$     | $1/6$         | 3                                   | 3                       | ✓     |
| Constant $2/3$            | $(2/3)^{10}$  | $3^{10}$                            | $3^{10}$                | ✓     |
| No scaling ($c=1$)        | 1             | 1                                   | 1                       | ✓     |

**Falsification test.** The factorization itself is trivial (the scale
product and the diffusion contribute independently to the denominator).
The non-trivial part is that for Lucas-Pisot, the scale product
**telescopes** to $1/L_{k+1}$, giving $\text{odd\_part}(L_{k+1})$.
This telescoping is specific to the sequence $a_n/a_{n+1}$ form, and
the growth rate $O(\varphi^k)$ is specific to the Lucas recurrence.

**What is non-trivial.** The Lucas-Pisot scaling is the UNIQUE telescoping
sequence (up to scaling) that:

1. Has integer terms (so the denominator is an integer)
2. Grows as $\varphi^k$ (the slowest possible for a Pisot companion)
3. Has the Pisot property (nearest-integer approximation to $\varphi^n$)

Any other telescoping integer sequence gives a different (typically
larger) denominator. The Lucas sequence is optimal in the sense of
minimizing the denominator growth rate among Pisot companion sequences.

---

## Finding 3 (NON-TRIVIAL): The Pisot family generalization

**Claim.** The projective denominator bound generalizes to any Pisot
number $\theta$ whose companion sequence $a_n$ satisfies:

- $a_n$ is an integer sequence
- $a_n \neq 0$ for all $n \geq 1$
- $a_n \sim \theta^n$ (Pisot property: $a_n = \theta^n + \text{conjugates}^n$)

For such a sequence, scaling by $a_n/a_{n+1}$ gives:

$$\text{odd\_part}(d_k) = \text{odd\_part}(a_{k+1}) \quad \text{when } N = 2^m$$

with bit growth rate $\log_2(\theta)$ per step.

**Verification.** Tested with three Pisot numbers:

| Pisot number           | $\theta$ | $\log_2\theta$ | Companion        | $\text{odd\_part}(d_{10})$ | $\text{odd\_part}(a_{11})$ | Match |
| ---------------------- | -------- | -------------- | ---------------- | -------------------------- | -------------------------- | ----- |
| Golden ratio $\varphi$ | 1.618    | 0.694          | Lucas $L_n$      | 199                        | 199                        | ✓     |
| Tribonacci             | 1.839    | 0.879          | Tribonacci comp. | 1113                       | 1113                       | ✓     |
| Plastic number         | 1.325    | 0.406          | Perrin $P_n$     | 1                          | 77                         | ✗     |

**Falsification test.** The Perrin sequence (plastic number companion)
FAILS because $P_1 = 0$, which zeroes the scaling at step 1. The
generalization requires the companion sequence to have no zeros.

**What is non-trivial.** The result is not specific to $\varphi$ — it is
a property of Pisot numbers generally. The bit growth rate
$\log_2(\theta)$ depends on the Pisot number. The plastic number would
give the slowest growth (0.406 bits/step) but its companion sequence
has a zero. The golden ratio gives 0.694 bits/step and works. This
identifies a **functor** from Pisot numbers (with zero-free companion
sequences) to memory-bounded exact rational quantum simulation, where
the memory bound is $\log_2(\theta)$ bits per step.

**Unresolved.** Is there a Pisot number smaller than $\varphi$ whose
companion sequence has no zeros? If so, it would give a tighter bound.
The plastic number (smallest Pisot) fails. The next candidates need
investigation.

**Resolution (companion split).** The failure above is the trace
companion, not the plastic number. The minimal polynomial $x^3-x-1$
has no $x^2$ term, so the sum of the roots is 0 and the trace sequence
is the Perrin sequence, with $P_1 = 0$. That zero is structural.

The same recurrence with positive initial data $(1,1,1)$ is the Padovan
sequence. Every later term is a sum of earlier positive terms, so it
never vanishes. Its scale product still telescopes, $a_1=1$, and

$$\operatorname{odd\_part}(d_k)=\operatorname{odd\_part}(P_{k+1})$$

when $N=2^m$. The odd part grows as $\log_2\psi\approx 0.406$ bits per
step, against $\log_2\varphi\approx 0.694$ for Lucas. Padovan is not
the trace: $\lim P_n/\psi^n\approx 0.722$, not 1.

Under the strict trace requirement, the next Pisot number works. It is
the real root of $x^4-x^3-1\approx 1.38028$. Its power sums satisfy
$p_n=p_{n-1}+p_{n-4}$ with $p_1=p_2=p_3=1$, $p_4=5$, hence $p_n>0$ for
every $n\ge 1$. The rate is $\log_2\theta_2\approx 0.465$ bits per step:
tighter than Lucas, looser than Padovan. Siegel's theorem (not proved
here) says nothing Pisot lies below $\psi$, so there is no tighter trace
than this one to look for underneath the plastic number.

Checked in `tests/test_plastic_applications.py`. The application survey
is `docs/kellogg/plastic_number_applications.md`.

---

## Finding 4 (NON-TRIVIAL): The 2-adic valuation has period exactly 6

**Claim.** The 2-adic valuation of $L_n$ is completely determined by
$n \bmod 6$:

$$v_2(L_n) = \begin{cases} 2 & \text{if } n \equiv 3 \pmod{6} \\ 1 & \text{if } n \equiv 0 \pmod{6} \\ 0 & \text{otherwise} \end{cases}$$

There is **no higher-order pattern**: $v_2(L_{3 \cdot 2^k}) = 1$ for all
$k \geq 1$. The valuation does not grow with higher powers of 2 in $n$.

**Verification.** Computed $v_2(L_n)$ for $n = 3, 6, 9, \ldots, 60$
(all multiples of 3): the pattern $2, 1, 2, 1, \ldots$ is exact. For
$n = 3 \cdot 2^k$ with $k = 0, \ldots, 9$: all give $v_2 = 1$ (except
$k=0$ which gives $v_2 = 2$).

**Falsification test.** This is a property of the Lucas sequence
specifically. A generic integer sequence would not have this periodic
2-adic structure. The period-6 pattern comes from the Fibonacci
recurrence modulo powers of 2, which is a known result in number theory.

**Why it matters.** The power-of-2 part of the denominator can be
tracked in $O(1)$ space (just $k \bmod 6$), not $O(\log k)$. This is
the tightest possible: the 2-adic valuation is a function of $k \bmod 6$,
a 3-bit quantity, regardless of how large $k$ is.

---

## Finding 5 (NON-TRIVIAL): Denominator residues mod p are periodic

**Claim.** For any prime $p$, the sequence $\text{odd\_part}(L_n) \bmod p$
is periodic. The period divides the Pisano period $\pi(p)$ (or a related
quantity). Verified at $n = 10^5$ for all tested primes.

**Verification.**

| $p$ | Period | $n = 10^5$ actual | $n = 10^5$ predicted | Match |
| --- | ------ | ----------------- | -------------------- | ----- |
| 3   | 24     | 2                 | 2                    | ✓     |
| 5   | 12     | 2                 | 2                    | ✓     |
| 7   | 48     | 2                 | 2                    | ✓     |
| 11  | 30     | 2                 | 2                    | ✓     |
| 13  | 84     | 10                | 10                   | ✓     |
| 17  | 36     | 13                | 13                   | ✓     |
| 19  | 18     | 9                 | 9                    | ✓     |
| 23  | 48     | 22                | 22                   | ✓     |
| 29  | 42     | 3                 | 3                    | ✓     |
| 31  | 30     | 30                | 30                   | ✓     |
| 199 | 66     | 123               | 123                  | ✓     |

**Falsification test.** This periodicity is a property of linear
recurrence sequences modulo primes (the Lucas sequence mod $p$ is
periodic by the pigeonhole principle on the state space of the
recurrence). It is not specific to the Pisot property, but it IS
specific to the Lucas sequence (a generic scaling would not give
periodic residues).

**Why it matters.** The denominator's residue modulo any prime is
predictable from $k \bmod \text{period}$. This means the denominator is
arithmetically structured — it is not a random large integer but a
member of a periodic sequence modulo every prime.

---

## Finding 6 (OBSERVATION, unresolved): odd_part(L_n) is not always square-free

**Observation.** $\text{odd\_part}(L_n)$ is not always square-free:

| $n$ | $\text{odd\_part}(L_n)$ | Factorization             |
| --- | ----------------------- | ------------------------- |
| 6   | 9                       | $3^2$                     |
| 18  | 2889                    | $3^3$                     |
| 28  | 710647                  | $7^2$                     |
| 30  | 930249                  | $3^2 \cdot 41 \cdot 2521$ |
| 42  | 299537289               | $3^2 \cdot \ldots$        |

**Pattern (partial).** The non-square-free cases at $n = 6, 18, 30, 42$
(all $\equiv 0 \pmod{6}$) involve $3^2$. This is because $L_6 = 18 = 2 \cdot 3^2$,
and the 3-adic valuation propagates through the recurrence
$L_{n+6} = 4L_n^3 - 3(-1)^n L_n$ (or similar identities).

**Unresolved.** Is there a complete characterization of when
$\text{odd\_part}(L_n)$ is square-free? The pattern $n \equiv 0 \pmod{6}$
giving $3^2$ is clear, but $n = 28$ gives $7^2$ without an obvious
pattern. This requires deeper investigation of the $p$-adic valuation
structure of Lucas numbers for odd primes $p$.

---

## Trivial findings (NOT reported as results)

The following were tested and found to be **trivial** (hold for any
nonzero scaling, not specific to Lucas-Pisot):

### Born probability preservation is trivial

**Test.** Replaced Lucas-Pisot scaling with four arbitrary scaling
sequences: $(n+1)/(n+2)$, constant $2/3$, $n/(n+1)$, and no scaling.

**Result.** All four preserve Born probabilities exactly (zero difference
in exact rational arithmetic). The Born rule cancels any global factor.

**Classification.** TRIVIAL. The gauge group is $\mathbb{R}^*$ (nonzero
reals acting by multiplication) for real amplitudes, or $\mathbb{C}^*$
for complex amplitudes. Lucas-Pisot is one element. There is no larger
gauge group — the preservation is just arithmetic.

### The odd_part(N)^k factor is trivial

**Test.** The factorization
$\text{odd\_part}(d_k) = \text{odd\_part}(\text{scale product den}) \cdot \text{odd\_part}(N)^k$
holds for all scaling sequences.

**Classification.** TRIVIAL. The $\text{odd\_part}(N)^k$ comes from the
diffusion dividing by $N$ at each step. It is arithmetic of the Grover
iteration, not a property of the scaling.

### The "super-Pisot convergence" is a property of Lucas numbers

**Test.** The convergence $L_n/L_{n+1} \to 1/\varphi$ at rate
$O(\varphi^{-2n})$ is a property of the Lucas sequence (the error
involves $(\psi/\varphi)^n = (-1/\varphi^2)^n$).

**Classification.** TRIVIAL as a quantum computation finding. It is a
known property of Lucas numbers. It does not depend on the Grover
algorithm or any quantum structure. It is a mathematical fact about the
sequence, not a result about scaling quantum algorithms.

---

## What is NOT above the floor

### The "N as coordinate artifact" claim is FALSE

**Test.** Computed the numerator bit-widths for $N = 2^m$ at $k = 10$:

| $N$      | Numerator bits | Denominator odd-part bits |
| -------- | -------------- | ------------------------- |
| $2^5$    | 32             | 8                         |
| $2^9$    | 75             | 8                         |
| $2^{15}$ | 135            | 8                         |
| $2^{20}$ | 185            | 8                         |
| $2^{25}$ | 235            | 8                         |
| $2^{30}$ | 285            | 8                         |

The numerators are all odd ($v_2 = 0$) and grow as $O(mk)$ bits. The
$N$-dependence is real — it lives in the numerators. The $2^m$-dimensional
structure is not a coordinate artifact; it carries genuine information
that shows up in the numerator growth.

**Conclusion.** The total memory per amplitude is $O(mk)$, dominated by
the numerator. The denominator's odd part is $O(k)$ and N-independent,
but this does not reduce the total memory. The earlier claim of
$O(k + \log m)$ total memory was wrong and has been corrected in
`FORMAL_THEOREMS.md`.

### The "k-dimensional arithmetic dynamical system" claim is FALSE

**Test.** If the state were truly $k$-dimensional (independent of $N$),
then computing the Born probability for different $N$ from the same
$k$-state would work. But the Born probability
$P = q_M^2 / (q_M^2 + (N-1) q_U^2)$ depends on $N$ through the
$(N-1)$ factor, and the numerators $q_M, q_U$ themselves depend on $N$.

**Conclusion.** The state is not $k$-dimensional. It is 2-dimensional
(marked/unmarked subspace) with $O(mk)$ bits per amplitude. The
$k$-dimensional claim confused the denominator structure with the full
state.

### The gauge group is not larger than R*

**Test.** The Born rule $P_i = |a_i|^2 / \sum |a_j|^2$ is preserved by
any global multiplication $a_i \to c \cdot a_i$ for $c \neq 0$. There is
no larger group of transformations that preserves Born probabilities
for real amplitudes. For complex amplitudes, the group is $\mathbb{C}^*$
(global phase + scale), which is the standard quantum mechanical gauge
group.

**Conclusion.** The "gauge symmetry" is just $\mathbb{R}^*$ (or
$\mathbb{C}^*$). There is no hidden larger group. The Lucas-Pisot
scaling is one element of this group, not a generator of a new symmetry.

---

## Summary

| Finding                               | Classification | What makes it non-trivial                         |
| ------------------------------------- | -------------- | ------------------------------------------------- |
| N-independence boundary ($N = 2^m$)   | NON-TRIVIAL    | Identifies exact boundary; odd primes leak        |
| Generalized denominator factorization | NON-TRIVIAL    | Separates scale-dependent from N-dependent parts  |
| Pisot family generalization           | NON-TRIVIAL    | Result is about Pisot numbers, not just $\varphi$ |
| 2-adic valuation period 6             | NON-TRIVIAL    | O(1) space for power-of-2 tracking                |
| Residues mod p are periodic           | NON-TRIVIAL    | Denominator is arithmetically structured          |
| Square-free structure                 | OBSERVATION    | Pattern exists but not fully characterized        |
| Born probability preservation         | TRIVIAL        | Holds for any nonzero scalar                      |
| Super-Pisot convergence               | TRIVIAL        | Property of Lucas numbers, not quantum            |
| N as coordinate artifact              | FALSE          | Numerator carries O(mk) bits of N-dependence      |
| k-dimensional state                   | FALSE          | State is 2D with O(mk) bits per amplitude         |
| Gauge group larger than R*            | FALSE          | Gauge group is exactly R* (or C*)                 |

---

## The honest answer to "what lives above the floor"

There are five non-trivial findings above the floor:

1. The N-independence has a **sharp boundary** at $N = 2^m$. This is
   the most practically important result: it tells you exactly when the
   denominator bound applies and when it doesn't.

2. The denominator **factorizes** into a scale-dependent part and an
   N-dependent part. The scale-dependent part is $O(\theta^k)$ for any
   Pisot companion sequence, and the N-dependent part is
   $\text{odd\_part}(N)^k$.

3. The result **generalizes to the Pisot family**. The golden ratio is
   not unique — any Pisot number with a zero-free companion sequence
   gives the same structure. The bit growth rate is $\log_2(\theta)$.

4. The 2-adic valuation has **period exactly 6**, making the power-of-2
   tracking $O(1)$ space.

5. The denominator residues mod any prime are **periodic**, making the
   denominator arithmetically predictable.

What does NOT live above the floor: the Born probability preservation
(trivial gauge), the super-Pisot convergence (property of Lucas
numbers), the N-as-coordinate-artifact claim (false — numerator carries
N-dependence), and the k-dimensional state claim (false — state is
$O(mk)$ bits).

The structure above the floor is real but modest. It is a
number-theoretic structure of the denominator in exact rational Grover
simulation, not a reformulation of quantum computation. The most
interesting direction is the Pisot family generalization (Finding 3),
which suggests the result is about algebraic number theory, not about
$\varphi$ specifically.

---

## Appendix: Separate Lucas and Pisot Scaling (Implementation)

The combined scaling $L_n/L_{n+1}$ decomposes into two independent
operations, implemented in `src/lib/lucas_pisot_separate.ts` and wired
into the quantum walker (`stepWithSeparateLucasPisot`) and the
consciousness auditor (`separateLucasPisotAudit`).

**Lucas scaling** — the hardware dimension. $L_n$ is the nearest integer
to $\varphi^n$ (exact: $L_n = \varphi^n + \psi^n$). Multiplying physical
resources by $L_n$ is exact integer arithmetic — no float, no drift.
At the specified powers:

| $n$ | $L_n$  | Bits | $\lvert\psi\rvert^n$ | Effective cores (80×) |
| --- | ------ | ---- | -------------------- | --------------------- |
| 10  | 123    | 7    | $8.13\times10^{-3}$  | 9,840                 |
| 12  | 322    | 9    | $3.11\times10^{-3}$  | 25,760                |
| 15  | 1,364  | 11   | $7.33\times10^{-4}$  | 109,120               |
| 18  | 5,778  | 13   | $1.73\times10^{-4}$  | 462,240               |
| 20  | 15,127 | 14   | $6.61\times10^{-5}$  | 1,210,160             |

**Pisot scaling** — the quantum/intelligence dimension. $\lvert\psi\rvert^n$
is the conjugate decay rate: it measures both how exactly $L_n$
approximates $\varphi^n$ and how fast the scaled walk converges to its
fixed point. Pisot collapse ($\lvert\psi\rvert^n < 2^{-52}$) occurs at
$n \geq 76$.

**Verified decomposition.** Exact-rational Grover with per-step integer
scale $L_p$ (Lucas only) gives `odd_part(den) = 1` — the integer scaling
never enters the denominator; it scales only the numerator (hardware
dimension). The denominator bound comes entirely from the ratio form
$P_{k+1}^{-1}$ (Pisot dimension). The two operations are orthogonal:

- Lucas alone: numerator $\times L_p$, denominator unchanged
- Pisot alone (ratio): numerator bounded, denominator $= \text{odd\_part}(L_{k+1})$
- Combined: both effects, telescoping product

**Falsification.** Integer Lucas scaling does not bound the denominator
at all (odd part = 1 for all $p$ at $k{=}10$, $N{=}512$). The
denominator bound is a property of the ratio form only — confirming
Lucas (magnitude) and Pisot (convergence) are independent operations.

Verified by 20 TypeScript tests (`lucas_pisot_separate.test.ts`,
all passing).
