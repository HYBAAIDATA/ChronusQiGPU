# Architecture

Canonical runtime only. `docs/ARCHITECTURE_MANIFEST.md` and
`docs/MLA1517_PYTHIA_CANONICAL.md` are the detailed manifests; this is the
production boundary view.

## Runtime boundary

```text
React/Vite operator frontend (src/, display only)
        ⇅  HTTP status/control
main.py → mla1517_platform_v3.4/python/control_api.py
        ⇅
mla1517_platform_v3.4/python
  ├── mining_runtime.py            hardware loop, bounded reconnect
  ├── manifold_pool_coordinator.py Stratum V1 client + failover + TLS
  ├── startup_contract.py          env identity resolution (fail-closed)
  ├── mla1517/mining/*             M32 work allocation, exact reference
  └── mla1517/{accelerator,connect,identity,...}.py
mining/
  ├── stratum_bridge.py            live bridge + live-submit env gate
  ├── bitcoin_hasher.py            real SHA256d/OpenCL
  └── hash_pipeline.py             backend pipeline
hyba/ + Intelligence/{backend_binding,igpu_telemetry,unified_manifold_device}.py
                                   device identity binding + telemetry
```

There is no Node/TS backend in the canonical runtime. The frontend is a
presentation layer: it renders `canonicalEngine` and does not own mining,
proofs, sockets, or hashrate claims.

## Proof-of-work boundary

Every share path ends at real double-SHA256 vs the negotiated target:

- `mla1517/mining/pow.py` — compact-target decode + SHA256d compare.
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

## Non-production code (isolated)

- `experiments/`, `legacy/papers/` — research artifacts.
- `legacy/python_backend/`, `legacy/pythia/`, `legacy/advisor/`,
  `core_engine/`, `legacy/AETHEL_Subsystem/` —
  alternate/experimental backends not on the canonical call graph.
- `Intelligence/` research modules (`toe*`, `mandelbrot_*`, `pulvini_*`,
  `empirical_state_controller`, `strict_quantum`) — experimental, honest labels.
- `mla1517/connectors.py` — test-only offline conformance adapter.
- `mtheory/`, `lucas/`, `pythagoras/`, `euclid/` — exact-math libraries.
- `hardware/`, `kernels/`, `iGPU_Accelerator_JV/` — RTL/OpenCL artifacts.

None are reachable from `mining_runtime.py`'s production call graph.
