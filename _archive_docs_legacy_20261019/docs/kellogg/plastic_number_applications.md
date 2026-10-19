# Plastic number: which applications survive

ψ is the real root of \(x^3 = x + 1\), about 1.324717957. Siegel proved
it is the smallest Pisot number, and that it is isolated. The definition,
the decay, and which of those theorems are proved in this tree are in
`docs/kellogg/pisot_numbers.md`. This note
separates the applications that are exact from the ones that only share
the name. Nothing here is a device measurement.

`PlasticIntelligence` in `toe/intelligences/plastic.py` is a thermal and
batch-size tuner. It does not use ψ. The name is a collision.

## What is exact

The powers of ψ obey \(ψ^n = ψ^{n-2} + ψ^{n-3}\). Any integer sequence
with that recurrence has the same limit of successive ratios, when the
terms are not zero.

Three sequences share the recurrence:

| sequence | start | zero? | what it actually counts |
|---|---|---|---|
| Perrin | 3, 0, 2 | \(P_1 = 0\) | trace \(ψ^n + α^n + β^n\) |
| Van der Laan / compositions | 1, 0, 1 | index 1 is 0 | compositions of \(n\) into parts 2 and 3 are 0 at \(n=1\), and equal to the Padovan term \(P_{n-2}\) for \(n\ge 2\) |
| Padovan | 1, 1, 1 | none | the positive solution. \(\lim P_n/ψ^n \approx 0.722\), not 1 |

Positivity is the proof that Padovan never hits 0: the first three terms
are positive and each later term is a sum of earlier ones.

## The memory bound, split in two

`docs/ABOVE_THE_FLOOR.md` Finding 3 asked for a zero-free Pisot companion
with a slower bit rate than Lucas (\(\log_2\varphi \approx 0.694\)).

The trace reading disqualifies ψ. No \(x^2\) term means the sum of the
roots is 0, so the trace dies at \(n=1\). The next Pisot number, the
root of \(x^4 - x^3 - 1 \approx 1.38028\), has power sums

\[
p_n = p_{n-1} + p_{n-4}, \qquad p_1 = p_2 = p_3 = 1,\; p_4 = 5.
\]

Those four terms are positive and the recurrence preserves positivity,
so the trace never vanishes. The rate is \(\log_2\theta_2 \approx 0.465\)
bits per step. That is the tightest *trace* companion below \(\varphi\).
There is no smaller Pisot number whose trace could beat it.

The telescoping reading accepts any zero-free integer solution. Padovan
qualifies. With \(a_1 = 1\) and \(N = 2^m\),

\[
\operatorname{odd\_part}(d_k) = \operatorname{odd\_part}(P_{k+1}).
\]

At \(n = 60\) the odd part of \(P_{60}\) has 23 bits and the odd part of
\(L_{60}\) has 41. The leading rate is \(\log_2ψ \approx 0.406\). That
is tighter than the second Pisot's trace, and it is not the identity
\(a_n = ψ^n + α^n + β^n\).

## Sampling

The additive recurrence \((\{n/ψ\}, \{n/ψ^2\})\) is the \(d=2\) member of
\(x^{d+1} = x + 1\). It fills the square. This is already the
two-dimensional generator in `kellogg/first_principles.py`.

Three plastic powers do not fill the cube. \(ψ^{-2} + ψ^{-3} = 1\), so
the third coordinate is determined by the second. The corner error stays
large. The cube generator is the next root, of \(x^4 = x + 1\).

A sphere dressed with the plastic turn is not a packing application.
Nearest-neighbour distances on the Fibonacci sphere, \(N = 800\):

| turn | coefficient of variation |
|---|---|
| golden \(1/\varphi^2\) | 0.013 |
| \(137/360\) | 0.147 |
| plastic \(1/ψ^2\) | 0.138 |

The golden turn wins. The plastic turn is in the same band as the
rational angle the grid artifact was confusing with the golden angle.

## What is not a substrate result

Van der Laan's architectonic scale (the ratios near \(4/3\) and \(7/4\),
the abbey church at Vaals) is a historical proportion system. It is not
an identity the miner can execute.

The splitting field \(\mathbb{Q}(\sqrt{-23}, ψ)\) and the appearance of ψ
in the metric of the snub icosidodecadodecahedron are classical. Neither
is used by the substrate.

A "plastic chain" Hamiltonian whose ground-state counts grow like ψ is a
combinatorial recurrence with the same characteristic factor
\(x^3 - x - 1\). It is not an extra computational primitive beyond the
recurrence already checked.
