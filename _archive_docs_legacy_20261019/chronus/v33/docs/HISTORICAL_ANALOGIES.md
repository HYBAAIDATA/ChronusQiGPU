# Historical Analogies — Scope and Limits

Chronos is a classical software implementation of selected quantum-*mathematical*
models. Occasional references to historical mathematicians and physicists are
**structural analogies**, not claims of anticipation, proof, or unbroken
technical lineage into this codebase.

## Doctrine

1. **Implement the maths; attribute the history carefully.**
2. **Analogy ≠ identity.** Sharing a logical shape (axioms → constructions →
   checks) does not mean the ancient source contains the modern theory.
3. **Tests verify algorithms, not metaphysics.** Passing pytest does not prove
   a philosophy of physics.
4. **Compass documents** (external high-level notes) propose direction. Only
   checkable mathematics is merged into `src/`.

## Allowed vs. disallowed phrasing

| Avoid | Prefer |
|-------|--------|
| “Euclid was the first computational thinker; Chronos is his Elements for quantum reality.” | “The Euclidean algorithm is an early recorded division algorithm; we implement gcd and the extended form as ordinary number theory.” |
| “Tegmark’s Mathematical Universe Hypothesis is proven by this code.” | “These models are classically computable in the regimes we test; that is consistent with, but does not establish, stronger ontological claims.” |
| “Pythagoras → complex Hilbert vectors.” | “Pythagorean emphasis on number is a cultural ancestor of mathematised science; Hilbert space is a 20th-century construction.” |
| “Everything is computable.” | “The structures implemented here are computable on classical hardware at the sizes we exercise.” |
| “Complete proof of quantum reality.” | “Verified implementation of a finite set of quantum-mathematical routines and a graphics pipeline.” |

## Concrete attributions we *do* stand behind

| Topic | Historical note (modest) | Code |
|-------|--------------------------|------|
| Division algorithm / gcd | Elements (traditionally Euclid, c. 300 BCE), Book VII | `theory/euclid.euclid_gcd` |
| Extreme-and-mean ratio | Elements II.11 / VI.30; φ = (1+√5)/2 | `theory/euclid.PHI`, manifold geometry, `phi_scaling` |
| Bézout coefficients | Extended Euclidean algorithm (later number theory) | `theory/euclid.extended_euclid` |
| Euclidean metric | Classical geometry of \(\mathbb{R}^n\) | `euclidean_distance`, `euclidean_angle` |
| Hilbert space / quantum formalism | 20th century (Hilbert, von Neumann, Dirac, …) | State vectors, unitaries, POVMs in core modules |
| Stabilizer / surface codes | Late 20th / early 21st century QEC literature | `academic/caltech.py`, theory error-correction |
| MPS / TEBD | Tensor-network literature (e.g. White, Vidal, …) | `academic/tensor_compression.py`, `compression/large_space.py` |

## Structural parallel (optional metaphor only)

```text
Elements-style presentation     Chronos engineering practice
----------------------------    ------------------------------
Definitions                     Type signatures / docstrings
Axioms / postulates             Explicit model assumptions
Constructions                   Algorithms (gcd, eigh, MPS update, …)
Proofs                          Unit + integration tests
Theorems / propositions         Measured outputs under those tests
```

This parallel describes **how we organise work**. It does not claim that
Elements is a quantum codebase or that Chronos is a new Elements.

## Bottom line

Historical names may appear in comments and docs for orientation and respect.
They never substitute for a derivation, a citation of the modern source, or a
failing test. When in doubt, delete the analogy and keep the equation.
