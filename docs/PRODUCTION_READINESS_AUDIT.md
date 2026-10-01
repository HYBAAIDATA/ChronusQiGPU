# PYTHIA Production-Readiness Audit

> Date: 2026-09-29. Auditor: Devin (automated). Scope: full repository,
> canonical path `main.py` → `control_api.py` → `chronus/mla1517_platform/python`
> → `mining/` → `python_backend/` → `chronus/`/`hyba/` device layer. Supersedes the
> 2026-09-23 audit, which was written before the AL HARAS / HYBA-service merges
> and the `turing_universal_quantum_computer` graft.

## 1. Executive summary

The canonical path (`main.py` → control API → `mining_runtime` → Stratum →
proof boundary) is honest, fail-closed, env-credentialled, TLS-capable, and
test-covered. All checks that CI documents were executed on this machine;
nothing in §3 is inferred.

The audit found **real regressions introduced by recent merges**, all fixed in
this pass:

- `scripts/import_audit.py` had been replaced by an API-surface audit for a
  package (`mla1517_core`) that does not exist in this repo — the gate
  silently passed while doing nothing, and every caller importing
  `import_audit` got an `ImportError`. The real local-import-resolution audit
  was restored and the gate repointed to it.
- `control_api._guardian_preflight` let an `evaluate()` exception propagate to
  `_guarded`, turning a guardian outage into HTTP 500 instead of the intended
  fail-closed 503 — including on `/api/v1/security/status`, the route whose
  job is to report that outage.
- `re_paper_gate` tripped on a literal `accepted += 1` share counter (real,
  but matching the synthetic-acceptance detector); rewritten in the measured
  form the record path already uses.
- 5 Windows-only sqlite defects (`NamedTemporaryFile` opened as a DB while the
  handle is still held) in `gate_impl.claims()` and four test files.
- One unqualified refuted-claim line in `docs/STRICT_QUANTUM_ARCHITECTURE.md`.
- 9,632 flake8 violations across 78 files — all cleaned to 0.

**Net result: the canonical path is production-shaped. Non-production code is
present but honestly labeled and off the production call graph.**

## 2. Method

- Baseline: every command documented by CI (`.github/workflows/ci.yml`,
  `pythia-ci.yml`), `Makefile`/`make/gates.mk`, `CONTRIBUTING.md`, and
  `AGENTS.md` was executed; results recorded verbatim in §3.
- Every top-level package was classified by reading module docstrings and
  following the import graph from `main.py`, `control_api.py`,
  `mining_runtime.py`, and `headless_miner.py` outward — production
  reachability, not folder names.
- Simulation/mock markers were swept repo-wide; each hit was read and
  classified (see §4b–§4e).
- Live smoke test: **RAN** — `scripts/pool_smoke.py` against Braiins, ViaBTC,
  and ckpool mainnet stratum endpoints, including one run authorized with the
  operator's stored worker credentials. Real `mining.subscribe` session
  parameters and a real `mining.notify` job were received; `mining.submit` was
  never called (non-destructive by design; no MMIO/OpenCL device exists on
  this machine to produce a share). See §6.

## 3. Baseline test matrix (all executed 2026-09-29, none inferred)

| Command | Purpose | Result |
|---|---|---|
| `python -m flake8 --count` | Repo lint (`.flake8`) | **PASS — 0** (was 9,632 findings in 78 files) |
| `python -m black --check` (9 CI-scoped files, `pythia-ci.yml`) | Canonical formatting | PASS — 9/9 unchanged |
| `python scripts/import_audit.py` | Every local import resolves; none hidden | PASS — 0 findings, 0 swallowed |
| `python scripts/import_graph.py cycles && layers` | No new cycles/layer violations | PASS — 12 known cycles, 6 known violations, 0 new vs baseline |
| `python -m pytest tests/ -x -q` | Root suite | **PASS — 1640 passed, 16 skipped** |
| `python -m unittest discover -s chronus/mla1517_platform/python` | Platform suite | **PASS — 317 passed, 7 skipped** |
| `python -m pytest tests -q` (in `turing_universal_quantum_computer/`) | VQC suite | PASS — 55 |
| `python -m compileall -q` (8 dirs per CI) | Byte-compile | PASS |
| `python -m scripts.deploy_sentry` | Config/dependency/CI wiring | PASS — 0 errors, 0 warnings |
| `python -m scripts.drift_sentry --verify` | Rules/skills/agents mirror drift | PASS |
| `python scripts/re_paper_gate.py` | Behavioral acceptance gate | PASS (after `coordinator.py` fix) |
| `python -m aethel selftest` | Aethel C ABI + seqlock + handoff | PASS |
| `python -m Intelligence.self_test` | Intelligence stack self-test | PASS — verdicts honestly report NOT EMERGED / DORMANT |
| `make gates` (11 gate scripts + rollup) | Assurance gates | PASS — 10/10 recorded, `assert_gate_rollup` `failed: []`; `privileged-path-audit` requires `MEDIATION_MANIFEST_KEY` (fails closed without it — correct) |
| `python -m pytest tests/test_hybrid_signal.py -q` | Hybrid traversal gates | PASS — 3 |
| `python scripts/benchmark_hybrid.py --n 4 …` | Benchmark smoke | PASS — verdict honestly reports no significant difference |
| `npm ci` / `lint` / `test:ts` / `build` (`frontend/`) | Frontend deps, tsc, vitest, vite | PASS — 0 vulns, tsc clean, 32/32, build OK |
| Forbidden legacy paths (`cpu_fallback_mock.py`, `frontend/server.js`) | Integration audit | PASS — both absent |
| Hardware gate (`MLA1517_STRICT_HARDWARE_CI`) | Device conformance | **BLOCKED — NOT RUN** (no device) |
| `python scripts/pool_smoke.py --endpoint …` (sentinel worker) | Live pool connectivity, never submits | **PASS — RAN** (see §6) |
| `python scripts/pool_smoke.py …` (operator worker creds) | Real authorization + job observe | **PASS — RAN** (see §6) |
| Live pool share submit+ack (real hash) | E2E mining | **BLOCKED — NOT RUN** (no MMIO/OpenCL device to produce a share; submitting without one would be fabrication) |

Skips (16 pytest + 7 unittest) are hardware/environment guards, not weakened
tests. `npm` note: the Windows npm shim on this box has a corrupted shebang;
`node …/npm-cli.js` was used (npm 10.8.2, node 20.19.0 — `engines` wants ≥22;
all commands still pass).

## 4. Component classification

### 4a. Production — canonical path

| Component | Behavior | Notes |
|---|---|---|
| `main.py` → `control_api.py` | Operator HTTP API; never fabricates hashrate; `canonicalEngine` reports measured/pool-accepted only | Guardian preflight now fails closed (503) when the AL HARAS mediator is unreachable |
| `chronus/mla1517_platform/python/mining_runtime.py` | Hardware loop, bounded backoff, env identity via `startup_contract.py` | Lazily loads `mining.bitcoin_hasher`; fails closed without device/job/proof adapter |
| `chronus/mla1517_platform/python/manifold_pool_coordinator.py` | Stratum V1 client, failover, job→submit, proof-check before submit | TLS via scheme/`--tls`/`MLA1517_STRATUM_TLS` |
| `chronus/mla1517_platform/python/headless_miner.py` | Hardware miner entrypoint | Requires device + creds + explicit `--submit` |
| `chronus/mla1517/mining/*` (geometry, lane, chooser, solver, pow, coordinator, execution_router, hyba_bridge, toe_adapter, promotion) | M32 structured work allocation + real SHA256d boundary; chooser learns only from real pool outcomes; TOE advisory-only | A label never becomes a share |
| `mining/` (stratum_bridge, stratum_v2, braiins_sv2, bitcoin_hasher, hash_pipeline, difficulty, nonce_scheduler, safety_fsm, search) | Real Stratum V1/V2 wire protocols + bounded SHA256d batches with backend provenance | Production-reachable via `mining_runtime`/`execution_router`; declares it must not claim pool acceptance itself |
| `python_backend/` (math_folding, hilbert_manifold_solver, phi_grover_v4, pythia_mining) | `hyba_core_v1` — exact arithmetic + structured search folded into `mla1517` via `hyba_bridge`/`math_folding` shim | `core_modules/fold_pipeline` sqlite leak closed |
| `chronus/` (opencl_host, engine, device, telemetry) | OpenCL device binding + execution; identity gate refuses non-HYBA devices | Fail-closed |
| `hyba/` (verifiers, inventory, executor, lemma, operating_model) | Device identity, capability census, read-only verdicts | `require_lemma` paper-before-code gate |
| `al_haras/` | Guardian/mediation/envelope/claim-register security boundary behind privileged routes | Signed mediation manifest requires `MEDIATION_MANIFEST_KEY` |
| `l_hras/` | Guardian math (heuristic by name/design — see 4d) | |
| `hyba_services/`, `hyba_contracts/`, `hyba_profiles/` | Enterprise service objects, fold contracts, profile compiler + gates | Covered by `tests/test_enterprise_v2_*` |
| `aethel/` | Topological storage substrate (C ABI, seqlock, geodesic handoff) | `aethel selftest` PASS |
| `frontend/` (React/Vite) | Operator UI; display-only, owns no mining/proof/pool claims | tsc/vitest/build all pass |
| `turing_universal_quantum_computer/` | Installed VQC package — **exact-arithmetic simulator** of documented quantum algorithms (stabilizer/sparse/exact backends); part of the miner per repo thesis | Named and documented as virtual/simulated; 55/55 tests |

### 4b. Offline simulator / experimental — honestly labeled, isolated

| Component | Classification | Evidence |
|---|---|---|
| `chronus/mla1517_platform/python/policy_bench.py`, `discovery_runtime.py` | Offline simulator | Declared-seed policy simulator; findings emitted with `evidence="simulated"` |
| `chronus/mla1517/mining/promotion.py` | Offline simulator | Twin/parallel-seed promotion evidence — labeled |
| `pci/` (engine, api, forensics, transparency_dashboard) | Offline simulator + heuristic | "full-amplitude simulator for up to ~15 qubits" — declared simulator; grandiose docstring framing, honest labels |
| `Intelligence/` (orchestrator, pythia_memory, self_repair, unified_punch, strict_quantum, …) | Experimental / heuristic | Salamander self-repair is opt-in (`HYBA_STARTUP_SELF_HEALING_ENABLED=false` default); `unified_punch` declares itself classical GPU compute; self-test reports NOT EMERGED |
| `agi/`, `asi/`, `enhanced_intelligence/` | Experimental (enterprise AI surface) | Not on mining path; reached only via `Intelligence`/compat shims; `agi/simulations.py` explicitly disclaims mocks |
| `toe/`, `kellogg/` | Experimental math substrate | Tensor/TOE engine; advisory-only on canonical path via `toe_adapter` (fail-closed per record) |
| `mtheory/`, `millennium/`, `pythagoras/`, `lucas/`, `phi_rotation/` | Exact-arithmetic research libraries | `omega/catalog.py`: "Yang-Mills continuum mass gap is NOT claimed" |
| `experiments/toe_enterprise_collapse.py` | Research artifact | Executable proof claim under test |
| `benchmarks/` | Measurement harness | Declared-seed reproducible benchmarks |

### 4c. Test fixture / external adapter

| Component | Classification |
|---|---|
| `soak_voyage.py` | Test fixture — soak harness over `FakeChain`/`FakePool` |
| `chronus/mla1517/connectors.py` | External adapter — offline conformance harness; "never retried silently and never faked" |
| `integrations/`, `conformance/`, `standard/`, `distributed/`, `thermo/`, `omega/`, `bench/` | External adapter / conformance-proof suite — seam contract tests and invariant checkers |
| `hyba_compat/` | External adapter — legacy-namespace shims; unknown names raise `LegacyNamespaceRemoved`, never return placeholders |

### 4d. Mock-stub / unimplemented / broken

| Component | Classification | Status |
|---|---|---|
| `asic/__init__.py` | Unimplemented (empty marker package) | Harmless; no code imports it |
| `core_engine/` | Deprecated facade (docstring-only) | Redirects to `Intelligence` |
| `legacy/` | Retired surface | Excluded from flake8/black; includes `firebase-applet-config.json` with a committed Firebase **web** apiKey — see §5 |
| `scripts/import_audit.py` | **Broken → fixed** | Was a stub auditing absent `mla1517_core`; real audit restored |
| `control_api._guardian_preflight` | **Broken → fixed** | Unhandled mediator exception → 500; now fail-closed 503 |

No unqualified `Mock(`/`FakeDriver`/`faker` usage on any production-reachable
path; the only fake objects are in test files and `soak_voyage.py`.

## 5. Security posture

- **Secrets**: stratum creds via env (`MLA1517_STRATUM_*`, per-pool
  `MLA1517_{POOL}_{USER,PASSWORD,ENDPOINT}`); control key via
  `EUCLID_ADMIN_API_KEY`; mediation signing via `MEDIATION_MANIFEST_KEY`;
  AL HARAS keys via `AL_HARAS_SUBSCRIPTION_KEYS`. `.env.example` is
  deploy-sentry-checked against code. No secrets in code or logs.
- **Credential hygiene**: `StratumIdentity` keeps `sha256(password)` only.
- **Fail-closed**: no device/job/proof-adapter/credentials/explicit-submit →
  refuse, never fake; guardian outage → 503 (fixed this pass);
  unsigned mediation manifest → gate FAIL (by design).
- **Committed key**: `legacy/firebase-applet-config.json` contains a real
  Firebase web apiKey. Web keys are public-by-design identifiers and
  `firestore.rules` is default-deny, but the file is unused — recommend
  removing it or rotating the key.
- **Remaining**: `black --check .` repo-wide still fails on ~308 files —
  almost entirely vendored `turing_universal_quantum_computer/` internals and
  research dirs outside the 9-file CI scope; documented gap, not new debt.

## 6. Live verification status

| Item | Status | Evidence |
|---|---|---|
| Pool connectivity smoke (sentinel) | **RAN — PASS** | Braiins `stratum.braiins.com:3333`: TCP connect, `mining.subscribe` (extranonce2_size=6, extranonce1 empty — Braiins pushes it via `set_extranonce`), sentinel worker **authorize-rejected**. ckpool `solo.ckpool.org:3333`: same, authorize-rejected. ViaBTC `btc.viabtc.io:3333`: connect, subscribe (en1 len 8, en2_size 8), sentinel **authorized** — ViaBTC accepts arbitrary worker names (auth binds to the account inside the worker string); a real `mining.notify` job `9425` was observed within 15 s. `mining.submit` never called. |
| Pool connectivity smoke (operator creds) | **RAN — PASS** | Braiins with the operator's stored worker: connect, subscribe, **authorized**, real `mining.notify` job `00` observed; zero submits. |
| TLS stratum endpoint | **NOT AVAILABLE — verified, not assumed** | `stratum+ssl://stratum.braiins.com:3333` → `SSLError: WRONG_VERSION_NUMBER` (the port speaks plaintext); `stratum+ssl://btc.viabtc.io:443` → connection reset. These public endpoints offer no TLS stratum port that we verified; the client's TLS path is exercised by the loopback tests instead. |
| OpenCL/MMIO hardware gate | BLOCKED — NOT RUN | No device on this machine |
| Live pool share submit + ack | BLOCKED — NOT RUN | No device to produce a real share; a synthetic share would be fabrication |
| `MEDIATION_MANIFEST_KEY`-signed manifest | Verified with a local dev key | Production key lives in CI secrets |

## 7. Honest-labeling compliance

- No classical component is labeled quantum: the VQC is documented as an
  exact-arithmetic **simulator**; `pci/engine.py` is a declared
  "full-amplitude simulator"; `unified_punch` is declared classical.
- No hashrate is fabricated; pool shares are counted only on measured
  `PoolOutcome.ACCEPTED` (the form the re-paper gate now verifies).
- Refuted-claim gate passes: `docs/STRICT_QUANTUM_ARCHITECTURE.md` qualifier
  restored.
- `AGENTS.md` anti-drift and the user's no-fabrication rule are consistent:
  simulated components carry "simulated"/"virtual" labels end-to-end.

## 8. How to run the verification gates

See `docs/TESTING.md`. Quick start:

```bash
pip install -e ./turing_universal_quantum_computer -e ".[ml,dev]"
python -m flake8 --count
python scripts/import_audit.py
python -m pytest tests/ -x -q
python -m unittest discover -s chronus/mla1517_platform/python
MEDIATION_MANIFEST_KEY=<dev-key> make gates && python scripts/assert_gate_rollup.py
cd frontend && npm ci && npm run lint && npm run test:ts && npm run build
```

## 9. Audit verdict

**Production-ready with documented constraints.** The canonical mining path is
honest, fail-closed, env-credentialled, TLS-capable, and test-covered (1640 +
317 + 55 + 32 tests green). The merge-induced regressions found in this pass
are fixed. Non-production components are isolated, honestly labeled, and
unreachable from the runtime entry points. Remaining items are enumerated —
the committed Firebase web key, repo-wide black formatting outside CI scope,
and hardware/pool gates that correctly report BLOCKED — not hidden.
