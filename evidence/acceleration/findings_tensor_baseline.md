# Finding: tensor baseline

Source inspected at `7be3e20d1dc34bcb7477d00346669ce98debaa7b`. The existing tensor route uses NumPy complex floating-point arrays; this is the FP baseline for a future same-input ring comparison, not evidence of drift or of measured advantage.

- `src/chronus/tensor/types.py` Git blob `2d08a1ce3bf015c2f54f901e95dc28a34f280dbf`: `SymmetricTensor.product_state` allocates `np.complex128`; `SymmetricTensor.to_dense` returns the dense array.
- `src/chronus/tensor/network.py` Git blob `1ad877573d585e28282bb00b147a084e9635a594`: `build_network(..., topology="MPS")` creates product-state blocks, and `TensorNetwork.to_statevector()` contracts using `np.tensordot`, then normalizes. Compare equivalent normalization and output, not raw unnormalized outputs against normalized ones. The source includes a 32-site limit but that alone is not a resource guarantee.
- `src/chronus/tensor/evolution.py` Git blob `b5d846e388685042dc82c2ea93190fb9f9586271`: `evolve_tdvp` builds complex matrices and uses SVD; `evolve_trotter` builds complex exponential gates. Their documented claims are not independently validated here. A future comparison must identify the exact operation and mathematically identical input and output, numerical tolerance, cost and complete method.

This finding is from static source inspection; no tensor workload, drift, depth or timing has been run for it. It is a reference for subsequent tests, not a stop or a claim of a capability.
