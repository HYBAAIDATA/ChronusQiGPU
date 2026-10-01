# Architecture

Canonical runtime only. `docs/ARCHITECTURE_MANIFEST.md` and
`docs/MLA1517_PYTHIA_CANONICAL.md` are the detailed manifests; this is the
production boundary view.

## Runtime boundary

```text
React/Vite operator frontend (src/, display only)
        ⇅  HTTP status/control
main.py → chronus/mla1517_platform/python/control_api.py
        ⇅
chronus/mla1517_platform/python
  ├── mining_runtime.py            hardware loop, bounded reconnect
  ├── manifold_pool_coordinator.py Stratum V1 client + failover + TLS
  ├── startup_contract.py          env identity resolution (fail-closed)
  ├── chronus/mla1517/mining/*             M32 work allocation, exact reference
  └── chronus/mla1517/{accelerator,connect,identity,...}.py
mining/
  ├── stratum_bridge.py            live bridge + live-submit env gate
  ├── bitcoin_hasher.py            real SHA256d/OpenCL
  └── hash_pipeline.py             backend pipeline
hyba/ + Intelligence/{backend_binding,chronus_telemetry,unified_manifold_device}.py
                                   device identity binding + telemetry
hyba/hybrid/
  ├── coordinator.py               certified GPU/iGPU + ASIC nonce dispatch
  ├── tensor_advisor.py            validated scheduling-only model boundary
  ├── performance.py               measured H/s and TFLOP accounting
  ├── gpu_solver.py                GPU/iGPU SHA256d execution
  └── asic_solver.py               fail-closed physical ASIC protocol adapter
```

There is no Node/TS backend in the canonical runtime. The frontend is a
presentation layer: it renders `canonicalEngine` and does not own mining,
proofs, sockets, or hashrate claims.

## Proof-of-work boundary

Every share path ends at real double-SHA256 vs the negotiated target:

- `chronus/mla1517/mining/pow.py` — compact-target decode + SHA256d compare.
- `solver.py` enumerates lanes; every header is checked with real SHA256d.
- `manifold_pool_coordinator.submit_candidate` proof-checks before submit;
  `submit_record` refuses non-proof state.
- M32/Lucas structure is a **search/work-allocation** mechanism, never a
  cryptographic shortcut. A label never becomes a share.

## Honest-labeling rule

Hashrate is only ever "pool-accepted shares or measured device run".
`canonicalEngine.fallback` is `false`. `execution` reports
"device-required; fails closed when OpenCL is unavailable" without a device.
Nothing classical is labelled quantum; `Intelligence/strict_quantum.py` is an
exact-rational math module that disclaims replacing SHA256d.

## Phase 4: measured tensor, iGPU/GPU and ASIC layers

The production interpretation of “Infinity GPU” is a heterogeneous,
capability-routed compute fabric. It does not imply instantaneous execution or
zero-latency communication.

1. **Tensor layer (advisory):** an optional `WindowRanker` may reorder an
   already-certified set of nonce windows. `apply_tensor_advice` rejects any
   model output that creates, removes, resizes, retargets or reassigns work.
   Model latency and identity are recorded. Tensor operations and TFLOPs are
   telemetry; they never become hashes.
2. **iGPU/GPU layer (execution):** OpenCL-capable devices perform real work.
   CPU fallback and backend identity remain explicit in attestations. Every
   reported candidate is rechecked by the host with SHA-256d.
3. **ASIC layer (execution):** `ASICSolver` uses a configured, responsive
   physical endpoint. Missing or unsupported hardware fails closed and creates
   an attestation gap; no synthetic ASIC hashrate is generated.
4. **Fleet/swarm layer (aggregation):** only hashes actually executed inside
   the observation window are summed. Device counts and vendor nameplate
   capacity are not multiplied into measured output.
5. **Genetic/learning layer (policy):** policy may change future dispatch
   order only. It cannot alter targets, nonce coverage, proof validation or
   historical measurements.

The canonical production equation is:

```text
measured_hashrate_hps =
    protocol_valid_sha256d_hashes_executed / measured_wall_seconds
```

`PerformanceReport` keeps tensor throughput separate:

```text
measured_tensor_tflops =
    measured_tensor_operations / measured_wall_seconds / 10^12
```

A `10^19 H/s` floor is unclaimed unless measured physical work reaches it. Folds, geometric projections, classifier scores, expected search
uplift, parallelism factors and hardware inventory do not multiply H/s. They
may be reported separately as experimental or projected evidence, never as
production hashrate.

### Enterprise invariants

- Certified nonce coverage remains total and disjoint before and after advice.
- Tensor advice is a strict permutation and is fail-closed on mutation.
- Every accepted share passes host SHA-256d and target verification.
- ASIC support requires a responsive physical channel.
- H/s and TFLOPs retain different units and separate accounting.
- Floor status is derived only from measured protocol hashes and wall time.
- Reports include device identity, layer, timing, work counts and truth class.

## Non-production code (isolated)

- `experiments/`, `legacy/papers/` — research artifacts.
- `legacy/python_backend/`, `legacy/pythia/`, `legacy/advisor/`,
  `core_engine/`, `legacy/AETHEL_Subsystem/` —
  alternate/experimental backends not on the canonical call graph.
- `Intelligence/` research modules (`toe*`, `mandelbrot_*`, `pulvini_*`,
  `empirical_state_controller`, `strict_quantum`) — experimental, honest labels.
- `chronus/mla1517/connectors.py` — test-only offline conformance adapter.
- `mtheory/`, `lucas/`, `pythagoras/`, `euclid/` — exact-math libraries.
- `hardware/`, `kernels/`, `iGPU_Accelerator_JV/` — RTL/OpenCL artifacts.

None are reachable from `mining_runtime.py`'s production call graph.
