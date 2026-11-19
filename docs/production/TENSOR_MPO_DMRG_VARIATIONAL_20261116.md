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
couplings; n = 16 equals the exact Jordan-Wigner energy to 1e-9; budget
exhaustion fails fast without mutation; the local-dimension policy refuses.

Experiment E3 (`/v1/tensor/experiments/E3`, previously a 501) now runs
n = 1000, chi_max = 512, 2 sweeps, P = +1 sector. Measured on the review box
(CPU, 2026-11-19): E = -1272.875271..., exact open-chain Jordan-Wigner energy
-1272.876295..., relative energy error 8.0e-7, truncation ledger bound
1.2e-10, maximum bond dimension used 32, about 34-42 s wall time. PASS
requires the ledger bound < 1e-6, the energy not below the exact value beyond
round-off, the relative error <= 1e-6 and the n=32 density cross-check < 0.05;
otherwise the endpoint returns an honest 422 with the measured numbers. The
API serialises E3 runs and reuses a certified result per solver policy.
This is local numerical evidence, not a hardware or GPU performance claim.
