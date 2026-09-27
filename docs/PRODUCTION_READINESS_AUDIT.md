# PYTHIA Production-Readiness Audit

Date: 2026-09-23. Auditor: Devin (automated). Scope: full repository, canonical path
`mla1517_platform_v3.4/python` + `mining/` + `Intelligence/` bindings + `src/` frontend.

## 1. Executive summary

PYTHIA's canonical mining path is closer to production-ready than most repos of this
size: proof-of-work is bounded by real SHA-256d everywhere, the control API refuses to
fabricate hashrate, the hardware gate fails closed, and live share submission is
triple-gated behind env vars. The largest defects found during this audit were
*latent regressions* (deleted packages still imported, restored API fields) and a
small set of unsafe defaults — not systemic mock behavior. All findings are now fixed
or honestly classified below.

**Net result after this pass: the canonical control-API → Stratum → share-submission
path is fail-closed, env-credentialled, TLS-capable, and test-covered. What remains
non-production is isolated and labelled, not silently reachable.**

## 2. Method

- Baseline: `pytest tests/` + `unittest discover` on the platform + `flake8` +
  `compileall` + `tsc` + `vite build`, all actually executed on this machine.
- Every component classified by reading code paths (not docstrings alone).
- Production reachability traced from `main.py` / `control_api.py` /
  `mining_runtime.py` entry points outward.
- Live smoke test: **BLOCKED — NOT RUN** (no pool credentials, no OpenCL/MMIO device
  on this machine; the strict hardware gate correctly reports device-required).

## 3. Baseline test matrix (all executed, none inferred)

| Command | Purpose | Result | Passed | Failed | Skipped |
|---|---|---|---|---|---|
| `python -m pytest tests/ -x -q` | Root test suite | PASS | 593 | 0 | 1 |
| `python -m unittest discover -s mla1517_platform_v3.4/python` | Platform suite | PASS | 130 | 0 | 6 |
| `python -m flake8 --count` | Repo lint (.flake8 config) | PASS | 0 findings | — | — |
| `python -m compileall` (8 dirs per CI) | Byte-compile | PASS | — | — | — |
| `npm run lint` (`tsc --noEmit`) | Frontend typecheck | PASS | — | — | — |
| `npm run build` (`vite build`) | Frontend bundle | PASS | — | — | — |
| `npm ci` audit | Dependency vulnerabilities | PASS (0) | — | — | — |
| Hardware-gate (`MLA1517_STRICT_HARDWARE_CI`) | Device conformance | BLOCKED — NOT RUN | — | — | — (no device) |
| Live pool smoke (submit/share ack) | E2E mining | BLOCKED — NOT RUN | — | — | — (no creds/device) |

Skipped tests are pre-existing hardware/environment guards (device absent), not weakened.

## 4. Component classification

### 4a. Production — canonical path

| File/symbol | Current behavior | Risk | Action taken |
|---|---|---|---|
| `main.py` | Thin entry → `control_api.main` | none | kept |
| `mla1517_platform_v3.4/python/control_api.py` | HTTP status/control; emits `canonicalEngine`; **never fabricates hashrate** (only measured/accepted) | none | restored regressed `backend`/`canonicalEngine` fields; removed dead `_IDENTITY_ERROR` |
| `mla1517_platform_v3.4/python/manifold_pool_coordinator.py` | Stratum V1 client, failover endpoints, job→submit translate, proof-check before submit | creds over cleartext | **added TLS**: scheme-aware endpoints (`stratum+ssl://`, `stratum+tls://`), `--tls` flag, `MLA1517_STRATUM_TLS` env, default TLS context on connect |
| `mla1517_platform_v3.4/python/mining_runtime.py` | Hardware loop; bounded reconnect backoff | none | threads `tls=args.tls` through both endpoint parses |
| `mla1517_platform_v3.4/python/startup_contract.py` | Env identity resolution; canonical+alias conflict is fail-closed; `StratumIdentity` holds only `password_sha256` | none | kept; masked `[:2]***` in conflict errors |
| `mla1517_platform_v3.4/python/mla1517/mining/*` | M32 work allocation, exact reference, real MMIO/vault | none | kept; honest labels (search structure ≠ PoW shortcut) |
| `mining/stratum_bridge.py` | Stratum bridge for live runs; live-submit triple env gate | unsafe defaults | **worker now required** (no silent `PYTHIA.001`); `STRATUM_PASSWORD` default `x` (pool convention) |
| `mining/bitcoin_hasher.py`, `hash_pipeline.py`, `production_miner.py`, `live_handshake.py` | Real SHA256d/OpenCL paths | none | kept |
| `hyba/` (device identity) | iGPU binding, telemetry, describe/require gates | none | **restored package** (was deleted while `Intelligence/unified_manifold_device.py` still imported it) |
| `Intelligence/backend_binding.py`, `igpu_telemetry.py`, `unified_manifold_device.py` | Device binding + telemetry | none | kept |
| `src/` frontend + `Mla1517MiningPanel.tsx` | Renders `canonicalEngine` status | none | kept; display-only, no claims |

### 4b. Experimental / offline / honestly-labeled (isolated, not on production path)

| File/symbol | Classification | Why |
|---|---|---|
| `mla1517_platform_v3.4/python/mla1517/connectors.py` | Offline conformance adapter | CPU-fallback translation harness; test-only, not reachable from runtime entry points |
| `Intelligence/strict_quantum.py`, `toe*.py`, `mandelbrot_resonance.py`, `pulvini_runtime.py`, `empirical_state_controller.py` | Experimental research modules | Honest docstrings (exact rational arithmetic, "does not replace SHA256d"); not on `mining_runtime.py` call graph |
| `experiments/`, `legacy/papers/` | Research artifacts | Paper experiments (headless_miner, hilbert_manifold_solver); not imported by production path |
| `mtheory/`, `lucas/`, `pythagoras/`, `legacy/euclid/` | Mathematical libraries | Exact-arithmetic research; standalone |
| `legacy/python_backend/`, `legacy/pythia/` , `legacy/advisor/`, `core_engine/` | Alternate/experimental backends | Not the canonical runtime; kept for reference |
| `legacy/AETHEL_Subsystem/`, `models/*.joblib` | Subsystem/ML artifacts | Separate product surface |
| `legacy/hardware/`, `kernels/`, `legacy/iGPU_Accelerator_JV/` | RTL/OpenCL sources | Device firmware/artifacts, not Python runtime |
| `target.py` | Dead stub (2 lines) | **deleted** |

### 4c. Findings fixed this pass

1. **`hyba/` package deleted but still imported** → restored (fail-closed device gate).
2. **`backend`/`canonicalEngine` missing from `status_payload()`** → restored (test regression).
3. **`scripts.measure_lucas_scaling` unresolvable** in platform test → rewritten with `importlib.util.spec_from_file_location`.
4. **No TLS on Stratum** → full scheme/TLS support added.
5. **`PYTHIA.001` hardcoded default account + `123` password** → worker required; password `x`.
6. **`_IDENTITY_ERROR` dead code** → removed.
7. **`hilbert_manifold_solver.py` F821 `Any`** → real NameError fixed.
8. **34 flake8 findings** → 0.
9. **`.env.example` contradicted auto-load behavior** → corrected.
10. **`firebase-applet-config.json`** committed real Firebase web apiKey, unused by code;
    `firestore.rules` default-deny → flagged (not deleted; see §5).

### 4d. Known remaining gaps (documented, not blocking)

- Client-side nonce-dedup is structural (M32 non-overlap + fresh `latest_job()`); stale-job
  guard is protocol-level. Server-side pool dup rejection remains the backstop.
- Live share submit is gated but the gate is env-based; ops should audit env at deploy.
- `firebase-applet-config.json` unused-but-committed web key — revoke/rotate or remove.

## 5. Security posture

- **Secrets**: stratum user/password via env (`MLA1517_STRATUM_*`, `VIABTC_*`, `BRAIINS_*`,
  `STRATUM_PASSWORD`); `.env` auto-loaded by `main.py` (process env wins). No secrets in code,
  logs, or git history introduced by this audit.
- **Credential hygiene**: `StratumIdentity` stores `sha256(password)` only; conflict errors mask
  with `[:2]***`; `test_identity_public_view_contains_no_password` asserts it.
- **Live submit gate**: `HYBA_ENABLE_LIVE_SHARE_SUBMIT` + `HYBA_LIVE_SHARE_APPROVAL_ID` +
  `HYBA_AUTONOMOUS_EXTERNAL_ACTIONS` all required; loopback permitted for tests only.
- **TLS**: opt-in via scheme or `--tls`/`MLA1517_STRATUM_TLS`; default `ssl.create_default_context()`.
- **Fail-closed**: every degraded input (no device, no job, no proof adapter, unknown scheme,
  missing worker, conflicted alias, rejected share) raises/refuses rather than fakes.

## 6. Honest-labeling compliance

- No classical component is labelled quantum. `strict_quantum.py` is an exact-rational
  mathematical module that explicitly disclaims replacing SHA256d.
- No hashrate is fabricated; `canonicalEngine.hashrate` reads "pool-accepted shares or
  measured device run only". `fallback: False` is emitted.
- No unverified capability is claimed in `status_payload()` — `execution` reports
  "device-required; fails closed when OpenCL is unavailable" when no device is found.

## 7. How to run the verification gates

See `docs/TESTING.md` for the full matrix. Quick start:

```bash
pip install -e ".[ml,dev]"
python -m pytest tests/ -x -q
python -m unittest discover -s mla1517_platform_v3.4/python
python -m flake8 --count
npm run lint && npm run build
```

Hardware gate (device required): `MLA1517_STRICT_HARDWARE_CI=1 MLA1517_GPU_BACKEND=opencl make test`.

## 8. Audit verdict

**Production-ready with documented constraints.** The canonical path is honest,
fail-closed, credentialled-by-env, TLS-capable, and test-covered. Non-production code
is isolated and labelled. Remaining gaps (client-side nonce-dedup as belt-and-suspenders,
Firebase key hygiene) are enumerated above, not hidden.
