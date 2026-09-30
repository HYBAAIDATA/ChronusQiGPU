# GPU blueprint implementation audit

## Claim boundary

Only executed SHA-256d hashes divided by measured wall time are hashrate.
TFLOPs, folds, tensor scores, device counts, swarm size and genetic policy do
not multiply H/s. Hardware status remains `not_run` until a physical device
executes the gate.

## Capability status

| Blueprint capability | Implementation | Status |
|---|---|---|
| `matmul_f4`, `matvec_f4` | `gpu.reference` generic exact-scalar oracle | software verified; hardware conformance required |
| `qfi_pure` | `gpu.reference.qfi_pure` | software reference |
| `grover_iterate` | `gpu.reference.grover_iterate` | software reference |
| `grover_hendrix_iterate` | permutation-validated reference | software reference |
| Exact tensor substrate | `gpu.tensor` → Turing VQC exact/quantum tensor modules | packaged separately; import-gated |
| Virtual quantum computer | `gpu.quantum` → `turing_universal_quantum_computer` | substantial exact implementation; physical-quantum claims excluded |
| Aethel manifold | `gpu.manifold` → `aethel.manifold` | punch 0x15 CPU parity and OpenCL dispatch implemented; hardware conformance required |
| `sha256d_scan` | bounded exhaustive reference plus existing OpenCL path | software verified; target hardware required |
| `sha256d_verify` | real double-SHA-256 equality | software verified |
| `sha256d_midstate` | one-block SHA-256 compression state | software verified |
| `sha256d_merkle` | Bitcoin-style double-SHA-256 pair hash | software verified |
| Seam dispatch | real reference execution for the capabilities above | software implemented; hardware identity remains explicit |
| Host attestation | result and composition links | software implemented; not a TPM/TEE quote |
| Traversal kernels | names exist in seam contract | fail closed; executable semantics not yet wired |
| Reversible/uncompute kernels | names exist in seam contract | fail closed; no physical backend |
| Zero-knowledge attestation | name exists in seam contract | fail closed; no prover implementation |
| Tensor scheduling | advisory-only ordering boundary | integrated; exact permutation enforced |
| ASIC dispatch | `hyba.hybrid.ASICSolver` network protocol | physical hardware not verified |
| Fleet aggregation | `hyba.inventory`, `hyba.virtual_gpu`, `hyba.multi_hasher` | implemented; fleet hardware not verified |
| Provenance | `gpu.provenance.validate_provenance` | production records fail closed |
| 10 EH/s floor | measured physical hashes only | not demonstrated |

## Remaining gaps

1. Merge and run the sequential-contract changes from PR #30.
2. Implement the traversal, reversible/uncompute and zero-knowledge kernels;
   they now fail closed rather than returning synthetic success values.
3. Complete the staged move from top-level `igpu/`, `kernels/` and hybrid GPU
   modules into `gpu/backends`, retaining compatibility shims for one release.
4. Execute strict OpenCL tests, including punch 0x15 parity, on the target iGPU
   and discrete GPUs.
5. Execute ASIC protocol tests against a physical endpoint.
6. Run a real job through hardware, host verification, pool submission and pool
   acknowledgement.
7. Regenerate provenance after human merge; existing sample records with null
   merge SHAs or empty change bundles cannot support production claims.
8. Measure the built container. The proposed 100 GB allocation is a budget, not
   evidence that the image or cache currently fits.
9. Promote the 32-face unified-manifold device from `legacy/`, rewire it to
   canonical modules and move its tests into the normal CI suite. Documentation
   now marks the legacy boundary explicitly.
