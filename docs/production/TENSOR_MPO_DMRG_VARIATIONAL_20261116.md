# MPO-dependent two-site DMRG and tensor error-accounting correction

The former DMRG entry point substituted a hard-coded two-site critical-TFIM
eigenstate for every bond, ignored its H_mpo parameter, and returned an
unrelated closed-form energy. That is not a variational ground-state solver.

The corrected entry point accepts validated uncharged qubit MPS and MPO
networks; canonicalizes the input MPS; contracts actual MPO left/right
environments; solves the two-site Hermitian effective Hamiltonian using
dense eigensolve for <=128-dimensional local spaces, or bounded
SciPy/ARPACK eigsh for dimension <=8192; runs bidirectional sweeps;
and returns the resulting MPS's MPO Rayleigh quotient. All edits are
staged and committed only on successful completion. No global-minimum
certificate or hardware performance assertion is issued.

SVD discarded weights are now accounted for per local canonical bond.
The ErrorLedger accumulates the conservative sequential truncation
bounds additively, rather than incorrectly calculating
2*sqrt(sum(discarded_weight)). The static analytical critical-TFIM helper
remains a floating reference, not the DMRG result. Randomized-SVD uses
its own generator instead of changing NumPy's global RNG.

Important limitations: the solver is a finite-precision variational method.
It does not implement exact algebraic eigenvectors, U(1) block-aware
optimization or certified eigensolver residual bounds (Z2 is implemented as
of 2026-11-19; see below). Unsupported symmetry, non-Hermitian
effective Hamiltonians, invalid tensor contracts or oversized local
effective spaces fail closed.

The source-correctness tests compare several non-identical actual MPOs
with independent dense eigensolvers for small physical systems, and check
that invalid invocation cannot mutate the MPS. These correctness checks
do not substitute for current deployment evidence or physical GPU tests.

## Update 2026-11-19 — Z2 charge-aware DMRG and experiment E3

`DMRG` now accepts MPS gauge group `"Z2"` (global spin-flip parity
P = prod X): site-wise Hadamard rotation into the parity basis, verified MPO
virtual charges, exact projection of the input MPS onto the target sector,
running-parity bond labels, sector-restricted local eigensolves (with a
one-time symmetry-leak probe that refuses on leaks) and block-diagonal SVD per
sector keeping the global top-chi values plus an optional `cutoff` tail.
`claim_bound` makes the solver stop with `UntrustedApproximation` as soon as
the additive truncation bound reaches the budget; local problems above
`CHRONUS_MAX_DMRG_LOCAL_DIM` (default 8192) raise `UntrustedResult`. Failed
runs never mutate the network or ledger. Environments use a fixed tensordot
contraction order (about 14x faster than the previous einsum path at n=100).

Tests (`tests/test_dmrg_z2_charge_aware.py`): sector energies equal dense
sector diagonalisation for n = 2, 4, 6, 7 in both parities and off-critical
couplings; at n = 16 the energy agrees with the closed-form Jordan-Wigner energy
within a 1e-9 numerical tolerance; budget
exhaustion fails fast without mutation; the local-dimension policy refuses.

Experiment E3 (`/v1/tensor/experiments/E3`, previously a 501) now runs with a
fixed contract: n = 1000, chi_max = 512, 2 sweeps, P = +1 sector. PASS requires
all of the following:

- a truncation ledger bound below 1e-6;
- an energy not below the closed-form value beyond IEEE-754 round-off (the
  variational principle);
- a relative energy error of at most 1e-6;
- an n = 32 density cross-check difference below 0.05.

If any check fails, the endpoint returns an honest 422 with the measured numbers.

**Numerical acceptance, not exact equivalence.** The reference is the
closed-form open-chain Jordan-Wigner energy (Pfeuty 1970), evaluated in float64.
A relative error at or below 1e-6 meets a numerical acceptance threshold. It is
not evidence that the DMRG state equals the ground state exactly. The response
states this in `telemetry.acceptance` (`kind: numerical_threshold`,
`exact_equivalence_claimed: false`, `threshold`, `measured`,
`headroom_fraction`).

Reference result
([`evidence/benchmarks/tensor-e3-1000-20261119.json`](../../evidence/benchmarks/tensor-e3-1000-20261119.json),
produced by `PYTHONPATH=src python benchmarks/benchmark_tensor_e3.py --out ...`;
CPU, Python 3.13.5, NumPy 2.5.5, x86_64):

| Quantity | Value |
|---|---|
| E (DMRG) | -1272.875271183 |
| E (closed-form Jordan-Wigner) | -1272.876295342 |
| Relative energy error | 8.05e-7 (threshold 1e-6) |
| Headroom | about 19.5% of the threshold |
| Truncation ledger bound | 0.0 (no step discarded weight above the cutoff) |
| Maximum bond dimension used | 32 of 512 |
| Wall time | 24-42 s across review-box runs |

The DMRG energy differs between runs on the same machine at about 1e-11
relative. The closed-form reference is deterministic.

**Headroom.** The error is set by sweep convergence, not by truncation. A
change that adds roughly 2e-7 of relative error (for example fewer sweeps,
another initial state or a different eigensolver tolerance) would make E3
refuse with 422 rather than report a weaker PASS.

**Concurrency.** The API runs E3 under a non-blocking lock. While a run is in
progress, another request gets 503 with `Retry-After: 60`, and outcomes (the
accepted result or the refusal) are cached per solver policy. The lock and the
cache are **per worker process**: several workers can each run E3, and there is
no service-wide guard.

This is CPU reference numerical evidence. It is not a hardware or GPU
performance claim, and it is not production qualification.
