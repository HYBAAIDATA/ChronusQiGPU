# Exact family composition atop the supplied core

The original `lucas_engine.py` remains the sequence authority. The added module uses that authority and the exact quadratic field Q(phi), not rounded phi values.

Write an element as a+b phi. From phi²=phi+1:

- product: `(a+b phi)(c+d phi) = (ac+bd) + (ad+bc+bd) phi`;
- conjugate: `(a+b)-b phi`;
- trace: `2a+b`;
- norm: `a²+ab-b²`.

For nonnegative n, `phi^n=(F_(n+1)-F_n)+F_n phi`. Its trace is L_n, and its norm is (-1)^n. Therefore `L_n²-5F_n²=4(-1)^n` is an exact cross-family check, not a floating proximity condition.

## Pair and three-way composition

A Fibonacci orbit stores `(F_n,F_(n+1))`. Multiplication of companion matrices gives:

```text
F_(m+n)   = F_m F_(n+1) + (F_(m+1)-F_m) F_n
F_(m+n+1) = F_m F_n + F_(m+1) F_(n+1)
```

Three-way composition is associative: `(Q^a Q^b) Q^c = Q^a (Q^b Q^c)`. The module verifies the result against the supplied fast-doubling core. Mixed compositions of up to sixteen indexes are accepted within the bounded index/bit domain.

The triple-index consequences are executable checks:

```text
L_(3n) = L_n³ - 3(-1)^n L_n
F_(3n) = F_n (L_n² - (-1)^n)
```

Binet representation, Lucas trace, norm/Pell-Cassini residue and Zeckendorf encodings are sealed into one certificate. Verification recomputes every declared field from the original exact core and rejects tampering. The certificate is an identity/replay record, not a claim of cryptographic proof-of-work.

## Engineering insight

These families are not unrelated constants multiplied together: they are representations and invariants of the same algebraic orbit. Combining them can give complementary exact checks and alternative composition paths. Three-way composition stays inside a two-dimensional exact coefficient space; it does not require constructing a three-dimensional amplitude array. This is a concrete storage/verification simplification to test against each workload, rather than an assumed throughput gain.

```python
from chronos import OneIGPU, PhiElement, FibonacciOrbit, FamilyCertificate
with OneIGPU() as gpu:
    certificate = gpu.family_certificate([10, 12, 15])
    assert FamilyCertificate.verify(certificate)
    assert certificate['combined_index'] == 37
```
