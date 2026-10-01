---
name: testing-pythia-operator-app
description: How to boot and end-to-end test the PYTHIA operator app (control API + React operator UI) on the devinbox Windows environment — updated for the post-fold chronus layout (chronus/mla1517_platform, chronus.mla1517 namespace).
---

# Testing the PYTHIA operator app (post-chronus-fold)

Supersedes the path references in the older pre-fold platform notes. Everything
below verified live on `devin/1790841083-chronus-consolidation` (PR #43, 2026-10-01).

## Environment on this box
- Repo: `C:\Users\Administrator\repos\PYTHIPhiMiner`. Python: **`C:\Python312\python.exe`**
  — there is NO `.venv`; the editable install `pythia-mla1517` in site-packages is
  regenerated per-layout and maps `chronus` + every `chronus\mla1517_platform\python`
  top-level module (`control_api`, `startup_contract`, `system_fabric`, `worker_lifecycle`,
  `discovery_runtime`, …) + repo packages (`Intelligence`, `al_haras`, `lucas`, `toe`).
  `import chronus` / `chronus.mla1517.fib(10)==55` works from ANY cwd.
- Node: 20.19.0 and 24.0.1 under `C:\hostedtoolcache\node\`; engines want >=22 → prefer 24.
  **npm on PATH fails in Git Bash** — invoke npm-cli directly:
  `node /c/hostedtoolcache/node/24.0.1/x64/node_modules/npm/bin/npm-cli.js`.
  `frontend/node_modules` is NOT committed — `npm-cli.js --prefix frontend ci` first
  (~55 s, 354 pkgs), then `node frontend/node_modules/vite/bin/vite.js build`
  (cwd=frontend) → `dist/public`. Grep the bundle for `chronus.mla1517.status/1`
  to prove the build isn't stale.
- Chrome: `C:\devin\chrome\chrome-win64\chrome.exe` (renders JSON in-page even on
  400/503 — navigate straight at JSON endpoints for recorded evidence).
- Secrets: `VIABTC_USERNAME`/`VIABTC_PASSWORD` (+BRAIINS) repo-scoped; bind via exec env.
  Real creds are safe — nothing dials the pool — and prove identity HMAC + redaction
  (`status.host.stratum.user_redacted` shows `PY***` for real, `te***` for placeholder).

## Booting the control API
Entrypoint moved: `chronus/mla1517_platform/python/main.py` (repo-root `main.py` shim
inserts the platform dir on sys.path then calls `control_api.main` — both boot;
`package.json start` uses the shim).

```
env MLA1517_STRATUM_USER=$VIABTC_USERNAME MLA1517_STRATUM_PASSWORD=$VIABTC_PASSWORD \
  PYTHIA_POOL_PROFILE=viabtc MLA1517_VIABTC_ENDPOINT=btc.viabtc.io:3333 \
  EUCLID_ADMIN_API_KEY=test-operator-key \
  /c/Python312/python.exe -u chronus/mla1517_platform/python/main.py \
  --host 127.0.0.1 --port 3000 --web-root dist/public
```
- Boot env order (startup_contract.resolve_stratum_identity): pool catalog
  (`PYTHIA_POOLS`/`PYTHIA_POOL_PROFILE`, default braiins; catalog braiins/viabtc/nicehash/
  ckpool) → `MLA1517_STRATUM_USER is required` → alias policy → endpoint
  (`MLA1517_STRATUM_ENDPOINT` or `MLA1517_{PROFILE}_ENDPOINT`).
- Bare-env fail-closed proof: `env -i PATH=… … python -u chronus/mla1517_platform/python/main.py`
  → traceback ends `startup_contract.StartupConfigError: MLA1517_STRATUM_USER is required`.
- `_PROJECT_ROOT` is now 3 levels up from `python/` (was 2) — `.env` still loads from
  repo root; `runtime_config` resolves `<repo>/data/runtime_config.json` (visible in
  GET /api/v1/config `path` field — quick path-arithmetic check).
- Lock/audit defaults `/tmp/pythia/*` → effectively `C:\app\data\*`; second instance needs
  `PYTHIA_BOOT_LOCK`/`PYTHIA_BOOT_AUDIT` overrides. `taskkill //PID //F` frees the lock;
  **killing the control API orphans the discovery worker** — taskkill the leftover
  `python.exe` too (its pid is in the audit `worker_spawned` event).

## Post-fold response shapes (verified)
- Schema strings renamed: status `chronus.mla1517.status/1`, ready probes
  `chronus.mla1517.ready/1`, stratum `chronus.mla1517.stratum/1`;
  `canonicalEngine.path` = `main.py → control_api.py → chronus/mla1517_platform/python`;
  identity HMAC body prefix `chronus.mla1517.stratum.identity.v1`.
- Workers: `agentic-mining`,`salamander` device-gated → `armed_no_device`; **`discovery`
  is ungated and RUNS** (simulated twin) → heartbeats flip it ready/running →
  `GET /ready-to-mine` answers 503 `{"ready":false,"reason":"stratum_disconnected"}`
  (was `worker_not_running`/`worker_unavailable` pre-heartbeat — both honest).
  `/metrics` `pythia_ready_to_mine{reason="<current>"}` = 1, `pythia_ready_to_mine_value 0`.
- `/readyz` → 200 `{"ready":true,"reason":"ok"}`.
- `/api/v1/telemetry/events` → 200 `{"available":false,"reason":"the mining worker has not
  reported Stratum telemetry"}`; `/api/v1/hardware/status` → `mining_device.bound:false`,
  `opencl.device_count:0, physical_gpu_count:0` (chronus.report; CPU `detected_backend:"cpu"`
  is honest, `error:null`); `/api/v1/stratum/status` → `state:"CONFIGURED"`,
  `primary.transport:"DISCONNECTED"`, worker redacted.
- Guardian: privileged GETs (`/api/v1/security/status`, `/api/v1/mining/evidence`, …)
  AND privileged POSTs (`POST /api/v1/mining/start` — preflight runs BEFORE the handler)
  → **400 `TENANT_AND_ACTOR_REQUIRED`** signed receipt (`allowed:false`, `evidence_id`,
  `payload_hash`, `tenant_id:"UNKNOWN"`, `policy_version:"al-haras.policy.v1"`).
  NON-privileged POSTs (e.g. `POST /api/v1/agentic/start`) → 401 `"operator key required"`
  when `EUCLID_ADMIN_API_KEY` is set, 403 `"... is not configured"` when unset.
- `GET /api/v1/status` → 404 `{"error":"not_found"}` (old notes said
  "endpoint not implemented" — string drifted).
- `GET /api/v1/knowledge` → 200 exercises the lazy `chronus.mla1517.knowledge` import
  (and `announce_skills()` → `Intelligence.skill_graft` — populated fabric facts at boot).
- Old namespaces must FAIL LOUDLY: importing `igpu` or `mla1517` must raise
  ModuleNotFoundError (no compat aliases by design — assert this).
- `python -X utf8 -m unittest discover -s chronus/mla1517_platform/python` from REPO ROOT
  → 348 tests, ~23 s, 1 fail + 1 error at main parity (envelope `allowed` vs `available`
  assertion; `stale_ratio` 0.0 vs None — both behavioral, pre-existing).

## UI (5 s poll of /api/v1/mla1517/status; hash views Operations/Algebra/Intelligence/Manifold/Audit)
- Header `PYTHIA OPS` + `MLA1517 CANONICAL` badge; amber chip shows `ready.reason`
  verbatim (`stratum_disconnected`); `SUPER-GPU · CPU HOST` device chip.
- Hero `Standing by.` + `Readiness gate reports stratum_disconnected`; footer literally
  renders `chronus.mla1517.status/1`; engine card PATH shows the chronus platform path;
  exact-ladder chips L10 L12 L15 L18 L20 L31 L50 L76; solver manifold `1 independent
  solver`/32.
- **Privileged polls fire the native 3-prompt subscription sequence**
  (`Subscription token` → `Tenant id` → `Actor id`) — a 400 guardian denial can trigger
  it; Cancel/Esc declines for the session (sessionStorage flag). Expect one prompt on
  first load from the evidence poll.
- Kill API → within one poll red `API OFFLINE` chip + hero `Control plane unreachable.`
  (still-open tab auto-reconnects on reboot — visible as resumed 5 s GETs in the log).

## Blueprint (post-fold, already retargeted)
`.devin` blueprint was retargeted post-fold to `chronus/mla1517_platform` for
unittest discover and the startup boot path, and to `chronus.mla1517` module
names (`chronus.mla1517.remote_gpu_agent`, `chronus.mla1517.prime`).

## Exercising the real mining loop on a GPU-less box (verified live)
- `PYTHIA_EXECUTION_DEVICE=cpu` — un-gates `agentic-mining` → supervisor spawns
  `mining_runtime.py` → `EuclidProductionMiningCoordinator.run_execution_loop`.
  **Prerequisite on this box:** `pip install -e turing_universal_quantum_computer --no-deps`
  (nested editable package, blueprint maintenance step — it may not have run).
  Without it the worker crash-loops at `resolve_nonce_order("hendrix")` →
  `No module named 'turing_universal_quantum_computer.pisot'`; retries burn the
  5/600s respawn budget → `failed` → `supervisor_degraded`.
- Windows heartbeat dir: `control_api._heartbeat_dir` now uses
  `worker_lifecycle._default_heartbeat_dir()` (fixed on the chronus-surface PR) —
  the earlier Windows-only bug (default `/run/pythia/hb` → `C:\run\pythia\hb`)
  made every metrics-derived surface silently unavailable while liveness read
  green. If a pre-fix build is ever under test, set
  `PYTHIA_WORKER_HEARTBEAT_DIR=%LOCALAPPDATA%\pythia\hb` as the workaround.
- With real ViaBTC creds + submit gate disarmed: connected/authorized/subscribed,
  jobs stream ~1/20s, CPU hasher ~450-650 kH/s, `ready-to-mine` →
  `ready:true reason:"ok"` — grind-only, safe.

## Chronus contract device — where it surfaces (post-chronus-surface PR)
`chronus.detect.detect_all()` enumerates the MLA1517 iGPU contract device FIRST
(vendor `hyba`, integrated, `mla1517_simt`; `default` = `hyba: MLA1517 iGPU`).
Served surfaces: `/api/v1/gpu.contract_device` carries the record ALONGSIDE the
physical counts (`opencl_device_count`/`physical_gpu_available` deliberately
exclude it — declared identity, not probed silicon); the header chip shows
`Chronus · MLA1517 iGPU` (amber) when no OpenCL hardware is present.
`status.device.devices` + `hardware/status.opencl` remain OpenCL-only by design.
