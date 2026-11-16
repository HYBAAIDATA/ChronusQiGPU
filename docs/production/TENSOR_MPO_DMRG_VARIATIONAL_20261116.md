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
It does not implement exact algebraic eigenvectors, U(1)/Z2 block-aware
optimization, certified eigensolver residual bounds or a qualification of
1,000-site production convergence. Unsupported symmetry, non-Hermitian
effective Hamiltonians, invalid tensor contracts or oversized local
effective spaces fail closed.

The source-correctness tests compare several non-identical actual MPOs
with independent dense eigensolvers for small physical systems, and check
that invalid invocation cannot mutate the MPS. These correctness checks
do not substitute for current deployment evidence or physical GPU tests.
