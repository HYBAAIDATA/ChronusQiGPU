# Fibonacci–Korobov lattices

The two-dimensional rule in `fibonacci_lattice` is a rank-1 lattice.
Its higher-dimensional power extension is not. The modulus forces the
extra coordinates back onto the first two.

## The two-dimensional lattice

For `n ≥ 3`, with `N = F_n` and `a = F_{n-1}`,

```text
(k / N,  (k a mod N) / N),    k = 0 .. N-1
```

`korobov_points(N, a, 2)` is this same set. Both coordinates, as
multisets, are exactly `{0, 1/N, ..., (N-1)/N}`, because
`gcd(F_{n-1}, F_n) = 1`. Each axis is a permutation of the grid. The
lattice is the pairing.

The generator is the convergent of `1/φ`. The Cassini identity shifted
by one index,

```text
F_n F_{n-2} - F_{n-1}^2 = (-1)^{n-1},
```

says `F_{n-1}^2 ≡ (-1)^n  (mod F_n)`. So `a` is its own inverse when `n`
is even, and the negative of itself when `n` is odd.

At `F_18 = 2584` the mean of `x y` is exactly `1/4 - 1621/13354112`.
The corner `[0, 1/2)²` holds exactly `646` points, which is `N/4`.
Across every modulus from `F_3` through `F_21` that corner count equals
`floor((N+3)/4)`. That range is checked. It is not a proof for every `n`.

## What is not this lattice

`({k/φ}, {k/φ²})` lies on the line `x + y ∈ ℤ`, because
`1/φ + 1/φ² = 1`. The finite form of the same collapse is consecutive
Fibonacci generators: `F_{n-1} + F_{n-2} = F_n`, so

```text
(k F_{n-1} mod N) + (k F_{n-2} mod N)  ≡  0   (mod N).
```

The second and third Fibonacci residues are one line.

## Dimension three and above

A Korobov rule in dimension `d` is `({k a^{i} / N})` for `i = 0 .. d-1`.
On the Fibonacci modulus the square congruence kills it. `a^2 ≡ ±1`,
so

| n | third coordinate |
|---|---|
| even | equal to the first |
| odd | `0` at `k = 0`, otherwise `1` minus the first |

The fourth coordinate repeats the second, and every later power
alternates between those two. The Fibonacci–Korobov construction does
not fill a cube. The cube sequence in this repository is a different
object, the additive recurrence of the root of `x^4 = x + 1`.

## The traversal named Korobov

`kellogg/traversal_map.py` walks modulus `64` with generator `55`.
`64` is not a Fibonacci number. `55^2 mod 64 = 17`, not `±1`, so that
walk does not collapse, and it is not `fibonacci_lattice`. Dimension 1
of any Korobov rule is `({k / N})`, because `a^0 = 1`. That is why the
measured `korobov_d1` row is the sequential scan.
