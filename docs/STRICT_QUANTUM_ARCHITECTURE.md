
## Exact state-vector API

`mla1517.quantum.ExactStateVector` is the finite-dimensional exact algebra
used by the strict mathematical plane. Amplitudes live in
`Q(sqrt(2)) + i Q(sqrt(2))`, represented by `Fraction` coefficients. The
implementation now exposes:

- `probabilities_exact()` — exact Born weights with an exact sum-to-one gate;
- `measure_deterministic()` — maximum exact weight, lowest-index tie break;
- `collapse(index)` — exact computational-basis projection;
- `expectation_z_exact()` — exact least-significant-qubit Z expectation;
- `Qsqrt2.compare()` — ordered algebraic comparison without floating point.

This is deterministic mathematical selection, not physical sampling. No
randomness, floating-point normalization, tensor truncation, or hidden
fallback is used. Unsupported Hamiltonian exponentials continue to fail
closed with `NotImplementedError`, and state-vector resource bounds continue
to fail closed rather than degrade.

These tests certify algebraic invariants only. They do not license claims of
physical quantum hardware, quantum advantage, exponential speedup, accepted
pool shares, or measured iGPU throughput.
