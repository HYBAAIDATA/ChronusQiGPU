# Pisot numbers

A Pisot number is a real algebraic integer \(\theta > 1\) whose other
Galois conjugates all lie strictly inside the unit disk. The set of
them is called \(S\).

Two symbols in this repository must not be collapsed:

| symbol in the tree | what it actually is |
|---|---|
| \(\psi = -1/\varphi\) in `ARCHITECTURE.md` | the golden conjugate. \(\|\psi\| < 1\), so \(\|\psi\|^n \to 0\). This is why \(\varphi\) is Pisot. |
| plastic \(\psi\), root of \(x^3 - x - 1\) | the smallest element of \(S\). A different number. |

`PlasticIntelligence` uses neither.

## Proved in this tree

### The golden ratio

The minimal polynomial is \(x^2 - x - 1\), irreducible over \(\mathbb{Z}\).
The roots are \(\varphi\) and \(\hat\varphi = 1 - \varphi = -1/\varphi\).
Their product is \(-1\), and \(\varphi > 1\), so \(|\hat\varphi| = 1/\varphi < 1\).
Hence \(\varphi \in S\).

The Lucas numbers are the traces \(L_n = \varphi^n + \hat\varphi^n\).
Equivalently

\[
|\varphi^n - L_n| = \varphi^{-n}.
\]

For \(n = 1\), \(\varphi^{-1} > 1/2\), since that is \(\sqrt{5} > 2\). So \(L_1 = 1\)
is not the nearest integer. The nearest integer is 2, at distance
\(2 - \varphi = \varphi^{-2}\). For every \(n \ge 2\),
\(\varphi^{-n} \le \varphi^{-2} = (3 - \sqrt{5})/2 < 1/2\), because that
comparison is \(4 < 5\). So \(L_n\) is the nearest integer, and the
distance to it decays geometrically with ratio \(1/\varphi\).
That is the Pisot power property in the one case the substrate uses.
It is Binet's formula, not a consequence that needs the general theorem.

### No quadratic Pisot number lies below \(\varphi\)

Let \(\theta > 1\) be quadratic, with minimal polynomial
\(x^2 - t x + n\), \(t, n \in \mathbb{Z}\), and conjugate \(\theta'\)
satisfying \(|\theta'| < 1\). Then \(t = \theta + \theta'\) is an integer,
\(t \ge 1\), and \(n = \theta\theta' \ne 0\).

If \(t = 1\), then \(\theta' = 1 - \theta\) and \(\theta(\theta - 1) = -n\) is a
positive integer. The function \(x(x-1)\) on \((1, \infty)\) hits 1 at
\(x = \varphi\) and is smaller than 1 on \((1, \varphi)\). So the only
possibility is \(\theta = \varphi\), \(n = -1\).

If \(t \ge 2\), then \(\theta > t - 1\). The only way to have
\(\theta < \varphi < 2\) would be \(t = 2\) and \(1 < \theta < \varphi\).
On that interval the product \(\theta(2 - \theta)\) is strictly less than 1,
so it is not a nonzero integer. Contradiction.

Therefore every quadratic Pisot number is at least \(\varphi\), and
\(\varphi\) is the only one that meets the bound. The family

\[
\theta_m = \frac{m + \sqrt{m^2 + 4}}{2}, \qquad m \ge 1,
\]

root of \(x^2 - m x - 1\), is an infinite sequence of examples. It starts
at \(\varphi\) and increases. A second family, roots of \(x^2 - m x + 1\)
for \(m \ge 3\), starts at \(\varphi^2 > \varphi\).

### The plastic number is a Pisot number

This does not use Siegel's minimality theorem.

Let \(f(x) = x^3 - x - 1\). On \([1, \infty)\), \(f'(x) = 3x^2 - 1 \ge 2\),
so \(f\) is strictly increasing there. \(f(1) = -1 < 0\) and \(f(2) = 5\),
so there is a unique real root \(\psi > 1\). On \([-1, 1]\) the critical
value at \(x = -1/\sqrt{3}\) is \(2/(3\sqrt{3}) - 1 < 0\) because
\(\sqrt{3} < 2\) gives \(2/(3\sqrt{3}) < 4/9 < 1\). There is no other real
root. The other two roots are a complex conjugate pair.

For the monic polynomial the product of the roots is 1. The complex pair
therefore has modulus \(\psi^{-1/2} < 1\). So \(\psi \in S\).

The trace \(P_n = \psi^n + \alpha^n + \beta^n\) is the Perrin sequence, and
\(|P_n - \psi^n| \le 2\,\psi^{-n/2}\). The same product argument shows that
the tribonacci constant, the real root of \(x^3 - x^2 - x - 1\), is a
Pisot number greater than 1. Both facts are why those companions appear
in `docs/ABOVE_THE_FLOOR.md`.

### An algebraic integer greater than 1 need not be Pisot

The real cube root of 2 is an algebraic integer greater than 1. Its
minimal polynomial is \(x^3 - 2\), irreducible by Eisenstein at 2. The
product of the three root-moduli is 2. If the two conjugates both had
modulus less than 1, the product of all three moduli would be strictly
less than the real root. But that product equals 2, and the real root
\(\theta\) satisfies \(\theta^3 = 2\), so \(2 = \theta^3 > \theta\).
Contradiction. \(\sqrt[3]{2} \notin S\).

### Degree one

Every integer \(m \ge 2\) is a Pisot number: the minimal polynomial is
\(x - m\), and there is no other conjugate. \(S\) is unbounded. For the
denominator bound of Finding 3 this is the uninteresting end.
\(\log_2 m \ge 1 > \log_2\varphi\), so an integer base stores more bits
per step than Lucas. The useful bases sit in \((1, \varphi)\), and the
quadratic classification says none of those are quadratic.

### Base \(\varphi\) and base \(\psi\)

\(1 = \varphi^{-1} + \varphi^{-2}\), because \(\varphi^2 = \varphi + 1\).
The greedy expansion of 1 in base \(\varphi\) is finite, digits `0.11`.
The same identity is why a Zeckendorf word has no two consecutive ones:
a consecutive pair can be rewritten by this relation. That rewriting is
already the integer codec in `aethel/zeckendorf.py`.

\(1 = \psi^{-2} + \psi^{-3}\), because \(\psi^3 = \psi + 1\). The expansion of
1 in base \(\psi\) is finite, digits `0.011`. This is why \(\psi\) is a
simple Parry number. It is also why three plastic powers are linearly
dependent, which is the reason they do not fill the unit cube.

## Cited, not proved here

These are classical. Using one of them as if this repository had proved
it would be a false certificate.

| statement | source | what this tree does instead |
|---|---|---|
| \(S\) is closed, and therefore has a least element | Salem, 1944 | not proved |
| the least element is the plastic number, and it is isolated | Siegel, 1944 | proved only that the plastic number is *a* Pisot number |
| the smallest limit point of \(S\) is \(\varphi\) | Dufresnoy–Pisot, 1953 | proved the weaker fact that no quadratic member of \(S\) lies below \(\varphi\) |
| if \(\sum \|\lambda \alpha^n\|^2 < \infty\) for some \(\lambda \ne 0\), then \(\alpha\) is Pisot | Pisot | not proved; the golden and plastic decays above are direct |
| a real base in which every rational has an eventually periodic expansion is Pisot or Salem | Schmidt | not proved; the golden case is the Zeckendorf codec |

A Salem number is an algebraic integer greater than 1 whose conjugates
lie in the closed disk and at least one lies on the unit circle. The
Pisot condition is the strict disk. \(\varphi\) and \(\psi\) are not Salem:
their other conjugates are strictly inside. No Salem number is computed
here.

## What the decay buys the substrate

The companion \(a_n = \theta^n + \sum \sigma(\theta)^n\) is an integer, and
the error is \(O(r^n)\) for \(r < 1\). Scaling a state by \(a_n/a_{n+1}\)
is therefore a ratio of integers whose size grows like \(\theta^n\).
Finding 3 of `docs/ABOVE_THE_FLOOR.md` is this fact plus the odd-part
arithmetic of the diffusion operator. The rate \(\log_2\theta\) is the
logarithm of the Mahler measure of the minimal polynomial, which for a
Pisot polynomial equals \(\theta\) itself because every other root is
inside the disk.

The rate is only a memory bound when the companion has no zero. The
trace of the plastic number has one. Padovan does not. The trace of the
next cited Pisot number, the root of \(x^4 - x^3 - 1\), has none. Those
distinctions are checked in `tests/test_plastic_applications.py`. The
definition, the quadratic bound, the plastic and tribonacci membership
proofs, the cube-root counterexample, and the two finite expansions of
1 are checked in `tests/test_pisot_theory.py`.
