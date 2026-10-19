# ADR 0002 — Exact finite-domain facade optimization

Status: accepted for this adapter, not a universal restriction on TURING.

The native public IR has concrete supported gates, not an arbitrary continuous
angle compiler. Binding a float angle to a nearby gate would change the problem
while appearing to preserve the API. We therefore materialize an explicitly
finite family, validate parameter identity/domain and admit every member before
execution. Exhaustive ordering uses exact rational/radical expectations.

Consequences: `run_vqe` identifies a minimum only in that family; an iteration
budget can stop early without convergence. Shot-based results cannot certify
exact exhaustion. Family construction has an explicit candidate budget. This
is useful and reproducible but not a continuous optimizer or a new claim about
TURING's broader algorithm library. Extend through a real compiler/optimizer
with independently validated semantics rather than silently relaxing the rule.
