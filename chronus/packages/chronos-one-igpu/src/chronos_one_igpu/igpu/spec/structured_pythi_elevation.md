# v3.9 — Structured execution and native computation

## Preserved authority

The original 52 source modules remain; Lucas and ChronosEngine are unchanged. This is an additive standalone implementation, not a repository import. The complete supplied PowerShell inventory and PYTHI proposal are preserved under source_notes with hashes. Every listing entry is retained in ATTACHED_SURFACE_INVENTORY.json; a filename or successful import transcript is not treated as an algorithm implementation. Original vendor module source/API specifications are required for byte/API-equivalent ports.

## Structured S6 mathematics

Let a=u+i v. The existing real advisory Hamiltonian is

H = T - u u^T - v v^T,
T = diag(linspace(0,1,n)) + off*(upper_shift+lower_shift), off=-1/phi.

The complex case has two real update columns. Matrix-vector application needs O(n) storage/work rather than materializing n² entries.

For lambda below the lowest eigenvalue of T, T-lambda I is positive definite. Define B(lambda)=U^T(T-lambda I)^-1 U, U=[u,v]. The lowest crossing of lambda_max(B)=1 brackets the ground state of H when such a crossing is separated from T's lowest pole. Two-column tridiagonal solves use linear storage. The vector is proportional to (T-lambda I)^-1 U z, where z is the corresponding 2x2 eigenvector.

The native CPU implementation brackets T with Sturm counts, brackets the lowest crossing, and validates its resulting eigenpair on the host. To establish a numerical lower separation from the next state, it uses the congruence identity

negative_count(H-lambda I) = negative_count(T-lambda I) + negative_count(I-B(lambda)).

This follows by taking the two Schur complements of [[T-lambda I,U],[U^T,I]]. It is a numerical inertia check, not a Lean/compiler proof. Near-zero pivots, unresolved poles, degeneracy or ambiguous positional order fall back explicitly to the unchanged dense reference in the bounded mining cache. Residual and separation bounds guard the positional permutation. Large public structured calls fail rather than secretly allocating an over-quota dense matrix.

The cache supports auto/dense/structured modes. Auto uses the native structured path at n>=32 when available, retaining exact-input reuse. A universal install has the explicit Python structured implementation and dense reference. The original dense engine source is unchanged.

## Accelerator boundary

The fp64 OpenCL matrix-free operator uses a local-memory partial-dot reduction and pointwise tridiagonal/rank-two application. A bounded host reduction combines partial dots. Host validation checks the result against the CPU operator, and profiling records both kernel events and wall time. Missing GPU/fp64 capability fails closed. This is an operator binding, not a full GPU eigensolver. Only C++ syntax conformance ran here; no physical GPU execution occurred.

`chronos-igpu qualify-target --device-selector "Intel" --output target.json` runs known Bitcoin vector checks and actual mining on a required physical OpenCL executor, never CPU fallback. It also probes the structured operator when fp64 exists. Cold/warm labels concern the host solver cache; device context creation and vector-probe warm-up are recorded separately. On this host it correctly returned unavailable; provisioning hardware remains outstanding.

## PYTHI-native computation protocol

The new pythi_native_compute_v1 namespace is separate from Bitcoin and has no pool or chain transport. One canonical header maps deterministically to one local receipt or policy refusal; no nonce enumeration is performed by this native protocol.

1. Domain-separated SHA256 header digest binds protocol, chain ID, epoch, fold index, rung width and threshold.
2. Split the digest into two 128-bit integers (x,y). Apply Q^k modulo 2^128, Q=[[1,1],[1,0]]. Store both resulting coordinates.
3. Since det(Q^k)=(-1)^k, the matrix is invertible modulo 2^128. Its adjugate times that sign is an exact inverse. Thus the full 256-bit coordinate fold is bijective.
4. Derive bounded rung n=1+(left mod 2^b), b<=8. This projection is many-to-one; both coordinates remain in the receipt. It is not a cryptographic PRP and does not invert SHA256.
5. Compute exact Lucas/Fibonacci, corrected Cassini, Zeckendorf and original prime-ROM address. Bind the original ONE iGPU datapath value independently.
6. Seal the canonical certificate and independently recompute every field in the verifier. Evidence sealing uses additional hashes beyond the single work digest.

Correct Lucas neighbor identity: L_(n-1)L_(n+1)-L_n² = 5(-1)^(n+1). D1=5, and D_(n+1)=-D_n follows from the recurrence. The supplied sign fails already at n=1. The original core has the correct sign and remains unchanged.

A correct cheap receipt does not by itself establish accumulated work, Sybil resistance, leader election or reorg resistance. `native-security-gate` refuses deployment as consensus. T1–T10 are retained in PYTHI_NATIVE_OBLIGATIONS.json with implemented mathematics, corrected statements and unresolved security/physical obligations. No testnet/mainnet or exchange migration is claimed.

## Models are explicit, not measurements

`capacity_model` requires an initiation interval separately from six-stage depth. Its output is labeled MODELED_NOT_MEASURED. `landauer_model` requires an explicit assumed erased-bit count; it is a conditional lower bound, not observed power. The arithmetic 2^32/256=16,777,216 does not compare equivalent completed work on different protocols. CPU/GPU/ASIC percentages, four-billion-share rate, ASIC obsolescence and thermodynamic superiority are not executable evidence.

## Evidence and publication

The benchmark records frozen v3.8.1 dense solver source, exact equal candidate order/counts, actual rung evidence, separate cold/warm solver-cache conditions, raw timings and 32 independently verified local native receipts. Historical ratios are not multiplied. Cold here means re-solving S6 each call; process, native hash midstate and host remain warm. It is not machine cold boot.

The supplied CI workflow now emits actual GITHUB_SHA/GITHUB_RUN_ID bindings after tests/build. This workflow has not run remotely. Supplied repository SHAs in the inventory remain contextual input, not this release's commit. Registry upload needs registry selection/authorization; it is not claimed complete. Docker/Apple/vendor ASIC qualification, pool transport, binary ISA, H4/600-cell and general TT/MPO remain outstanding.
