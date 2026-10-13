# Deterministic elevation — v3.8.1

The supplied exact Lucas engine and Chronos dense ground-state solver remain unchanged. This increment removes repeated identical dense diagonalizations without changing the Hamiltonian, candidates, hash predicate or completed-work count.

## Mathematics

For normalized complex state a of length n, the advisory matrix is

H = diag(linspace(0,1,n)) - Re(a a*) - phi^-1 (upper_shift + lower_shift).

Identical n, a and phi produce the identical H. Its eigenvector positional ordering can therefore be reused when the complete inputs match. The cache key binds a versioned construction ID, n, float64 phi and the full complex128 state bytes. A cold miss invokes the original ChronosEngine, checks norm and eigenpair residual, and stores only an immutable positional permutation plus its evidence. Candidate nonce values are never cached.

The default cache is eight entries; admitted dimensions are at most 128. Concurrent identical calls perform one cold solve. A changed state, dimension or phi causes a miss; custom solver callbacks bypass this cache. Eviction produces another cold solve, not dropped work. S1–S5 and job-specific S6 permutation application still execute each call, and host SHA256d winner verification is unchanged.

```txt
S1..S5 := existing fresh job-specific stages
key := hash(construction_id, n, phi_bits, amplitude_bits)
positions := bounded_cache.get(key)
if positions absent:
    H := identical original advisory construction
    vector := original_ChronosEngine.evolve(H)
    validate vector norm and eigenpair residual
    positions := stable descending probability order
    bounded_cache.put(key, immutable positions + evidence)
owned_candidates := current_candidates[positions]
execute exact SHA256d beneath existing solve-first path
```

A residual validates an eigenpair, not independently its minimality. Ground-state selection comes from the original dense solver's lowest-eigenvalue selection; tests compare the ordering directly against that solver.

## Executed comparison

The reference is a frozen byte-for-byte v3.8 GoldenRuntime source snapshot under benchmarks/, SHA256-bound in the benchmark record, running the same current native hash executor. It is not a new baseline slowed by extra validation.

Two Lucas rungs (18,31), two prefixes (public genesis header and explicitly derived timestamp+1 control), 30 randomized-order repeats per stratum: 120 full-call samples per path. Each executes exactly 4,096 nonces with target zero. Tier labels specify logical plan scaling; both are clamped to the same executed budget and use the same 64-candidate dense advisory solve. **This is not a sparse-path benchmark.**

Warm pooled result: v3.8 1,352,811 SHA256d/s; v3.8.1 1,870,699 SHA256d/s; ratio 1.3828231400645932. Per-stratum ratios range 1.3599–1.4303. Each path executes 491,520 hashes in total. Cold plan observations are recorded separately. Warm reuse is useful for repeated equal-state work; cold/changing-state workloads are not assigned the warm gain.

This result is not multiplied by the historical 3.44× result: different runs and comparison scopes must not be spliced. Hardware is the same CPU/OpenSSL host; GPU, physical ASIC, power, pool acceptance and competitors remain unmeasured. Data and independent reconciliation are in benchmarks/deterministic-reuse-results.json and validation/v3.8.1-benchmark-reconciliation.json.

## Backlog carried forward

- Target iGPU/GPU mining execution, device/backend identity, clocks, throughput and hardware evidence.
- Registry selection/authentication, upload log, installed artifact digest.
- Implement and validate a structured/matrix-free or sparse solver before claiming sparse tier-18/31 execution. The current advisory matrix contains a dense rank-one term; sparse storage alone does not eliminate it.
- Physical ASIC vendor job/result protocol, real sensor interfaces; current bridge is a configured full-digest interface only.
- Pool network jobs, submission and acknowledgements.
- Chronus-1 binary ISA, H4/600-cell, general TT/MPO.
- Docker/TLS target deployment, multi-platform CI execution and Apple/OpenCL target qualification.
- Broader combined-workload adjacency benchmarks, cold/changing-state cases, long-run memory/p99/energy measurements.
- Lean theorem formalization/compiler receipts. Existing proof_report.json says BLOCKED with no proved theorems; no Lean proofs are claimed.

## Evidence binding

Source fingerprint, distribution digests, environment, frozen reference digest, JUnit/test log and raw benchmark hashes are bound in validation/EVIDENCE_INDEX-v3.8.1.json. The envelope has a SHA256 integrity seal, not a hardware-root signature. This standalone tree has no authoritative repository commit or remote CI run. Those fields remain null with an explicit reason; local tests are not relabelled CI. The final ZIP digest is a detached release receipt because a file cannot include its own complete-file digest without a recursive dependency.
