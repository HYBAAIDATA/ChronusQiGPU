# Exact Lucas algebra close-out

## Scope

The canonical Lucas layer is an exact quadratic integer algebra:

\[
\mathbb Z[\phi] = \{a+b\phi : a,b\in\mathbb Z,\ \phi^2=\phi+1\}.
\]

The implementation uses arbitrary-precision integers only. It does not use
floating-point Binet evaluation, random sampling, a hardware provider, or a
statevector as a prerequisite.

## Definitions implemented

For the non-trivial automorphism

\[
\overline{\phi}=1-\phi,
\]

the exact operations are:

\[
\operatorname{Tr}(x)=x+\overline{x},\qquad
N(x)=x\overline{x}.
\]

For every \(n\ge 0\):

\[
\phi^n = F_{n-1}+F_n\phi\quad(n\ge1),
\]

\[
F_n=[\phi]\phi^n,\qquad L_n=\operatorname{Tr}(\phi^n).
\]

The composition laws are implemented and tested:

\[
L_{a+b}=\frac{L_aL_b+5F_aF_b}{2},
\]

\[
L_{a-b}=(-1)^b\frac{L_aL_b-5F_aF_b}{2}
\quad(a\ge b).
\]

The multiplication matrix of \(a+b\phi\) in the basis \((1,\phi)\) is:

\[
M(a+b\phi)=
\begin{pmatrix}
a & b\\
b & a+b
\end{pmatrix}.
\]

Therefore:

\[
\operatorname{tr}(M(\phi^n))=L_n,\qquad
\det(M(\phi^n))=(-1)^n.
\]

## What this does not claim

This closes the exact Lucas algebra boundary. It does **not** by itself claim:

- Fibonacci anyon fusion;
- a \(U_q(\mathfrak{sl}_2)\) representation;
- Temperley–Lieb generators;
- Jones polynomial evaluation;
- braiding matrices;
- topological quantum computation universality.

Those require separate algebraic objects and proof obligations. The current
implementation is the exact \(\mathbb Z[\phi]\)/Lucas layer on which such a
representation could be built without conflating an integer trace algebra with
anyon physics.