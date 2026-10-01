# Kellogg July tensor convergence

Kellogg is the repository's canonical tensor implementation. This convergence
review compared the July PULVINI/Hermes, Geodesic Tensor Engine, extended
Geodesic Engine, and 1,000-qubit VQC archives against the active Kellogg API.
Duplicate ZIPs were compared by SHA-256 before review.

## Integrated into Kellogg

- Stable, complex-preserving tensor-train decomposition and reconstruction.
- Matrix-product-state decomposition and reconstruction.
- Matrix-product operators, MPS contraction, and guarded full expansion.
- Transverse-field Ising and complex-preserving XXX Heisenberg MPOs.
- Hamiltonian evolution followed by bounded MPS projection.
- Error-budgeted TT compression with measured reconstruction error.
- Graph Betti signatures and multi-scale topology comparison.
- Correct pure-state quantum Fisher metric and normalized natural-gradient step.
- Compression-aware tensor containers and quantum operator execution.
- Validated unitary, Kraus, mixing, projective, coherent-interference, and
  measurement paths.
- Safe `.pv` compatibility persistence using checksummed NumPy members,
  canonical JSON, atomic replacement, optional HMAC-SHA256, and no pickle.

## Existing Kellogg capabilities retained

The current exact F4 state-vector substrate, finite-precision complex tensor,
folded phi tensor core, manifold metric, 32-face traversal, tensor ML,
attestation, and exact algebraic scales remain the canonical implementations.

## Cross-package ownership retained

- Aethel owns PULVINI/phi-fold custody and memory tiers.
- Chronus owns scheduling, execution control, and physical backend evidence.
- Tensor backends own device dispatch.
- Mining retains SHA-256d and target authority.

Kellogg exposes mathematical tensor operations; it does not duplicate those
execution or consensus owners.

## Behaviors intentionally rejected

The supplied drafts contained several behaviors unsuitable for the canonical
implementation: silent vector padding, dropping imaginary components, labeling
representation ratios as physical compression, zero-padding instead of inverse
reconstruction, unbounded full-matrix expansion, non-trace-preserving Kraus
maps, and phase-insensitive “interference” over density matrices. Kellogg fails
closed for these cases.

## Validation boundary

The tests prove deterministic software semantics and numerical contracts. They
do not constitute device-kernel execution, measured TFLOPS, measured energy
savings, or mining/pool evidence.
