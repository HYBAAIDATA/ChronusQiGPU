# Exact package-validation experiments

These small executable cases validate packaging, exact observables, execution
provenance and a finite variational family. They are not a quantum advantage,
large-scale performance or compiler novelty study.

- `bell_z0`: H(0), CX(0,1) on zero state; analytic Z0 expectation 0.
- `radical_z0`: H T H on one qubit; analytic Z0 expectation sqrt(2)/2.
- `finite_variational_z0`: enumerate the three native states |0>, |+>, |1>;
  the exact minimum of Z in this declared finite family is -1.

One JSON config defines the seed, execution settings, cases and repetitions.
The runner calls the installed TURING API, retains every canonical job report,
checks exact reference coefficients and writes a unique manifest. Even failed
runs retain a failed diagnostic manifest. Analysis rejects failed, incomplete,
modified or mismatched evidence; it regenerates CSV and TeX directly from data.
No publication table should be edited by hand.

Commit/dirty state are inspected, not supplied as an arbitrary SHA. Clean source
identity is required by default. Explicit development overrides label evidence
`development_only`; they do not authorize publication or replace independent
scientific validation. Timing is observed diagnostic wall time, not a speedup.
