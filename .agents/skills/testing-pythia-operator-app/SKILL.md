---
name: testing-pythia-operator-app
description: How to boot and end-to-end test the PYTHIA operator app (control API + React operator UI) on the devinbox Windows environment, including required stratum env vars and fail-closed expectations.
---

# Testing the PYTHIA operator app

Repo: `C:\Users\Administrator\repos\PYTHIA` on devinbox (older notes may say `C:\Users\Administrator\PYTHIA`). Interpreter: prefer `.venv\Scripts\python.exe` — it carries the editable install so `mla1517_platform_v3.4/python` is already on `sys.path` (no PYTHONPATH needed for `Intelligence.self_test`, `control_api`, or `mining/*` imports). Fallback: `C:\devin\python\python.exe` (embeddable-style, do not use `py`). Browser: `C:\devin\chrome\chrome-win64\chrome.exe`. UI build output: `dist/public`. **npm on PATH fails inside Git Bash** (`npm`/`npm.cmd` → "No such file or directory") — invoke npm-cli directly: `node /c/hostedtoolcache/node/20.19.0/x64/node_modules/npm/bin/npm-cli.js run build`. Also: each `exec` call resets cwd (prefix `cd ~/repos/PYTHIA`), Windows `timeout` cmd is not GNU timeout (use exec timeout), and native-Windows `.venv/Scripts/python.exe` cannot resolve Git-Bash `/tmp` paths — `cat /tmp/x > data/.tmp` first when python must read a bash-created file.

## Booting the control API (`python main.py`)

`main.py` → `control_api.main()` serves statics from `--web-root` plus `/api/*` JSON on the same origin/port. Boot is FAIL-CLOSED on stratum identity — without env it exits 1 with `StartupConfigError: MLA1517_STRATUM_USER is required` (see `startup_contract.py:126-165`). A repo-root `.env` is auto-loaded (`_load_env_file`, process env wins); `.env.example` documents the full surface.

Minimum placeholder env for a test boot (identity is only HMAC-committed — the control API never dials the pool):
```
MLA1517_STRATUM_USER=testoperator.001
MLA1517_STRATUM_PASSWORD=x
MLA1517_BRAIINS_ENDPOINT=stratum.braiins.com:3333
python main.py --host 127.0.0.1 --port 3000 --web-root dist/public
```
On Windows, Bash-embedded `python` resolves via PATH the same as cmd. Success line: `PYTHIA Python control API listening on 127.0.0.1:3000`. Note: stdout is block-buffered when redirected to a file — run in a visible console for the boot banner, or accept delayed flush in logs.

Expected honest no-hardware state on devinbox (no pyopencl, no MMIO device, no real creds):
- `workers armed but not started: MLA1517_MMIO_DEVICE is unset`
- `stratum bridge not started (bridge=True, opencl=False, creds=...)`
- status JSON: `device.available=false`, `device.count=0`, workers `armed_no_device`, `canonicalEngine.execution` = "device-required; fails closed when OpenCL is unavailable", `canonicalEngine.hashrate` is a policy string (never a fabricated number), `fallback:false`, `stratum.connected:false`.

Side effects to be aware of: writes `C:\app\data\BOOT_AUDIT.log` + `C:\app\data\pythia-main.lock` (msvcrt lock; released on process exit). `fs_selfcheck` runs `stat -f` on `/run/pythia/hb` → expected `No such file or directory` noise on Windows, harmless.

## Verifying the canonical-engine console

`App.tsx` polls `/api/v1/mla1517/status` + `/api/v1/ready-to-mine` every 5 s same-origin (`apiFetch` — no absolute API base baked into the bundle) and passes the payloads to `Mla1517MiningPanel` and `Header`. The ready-to-mine endpoint returns 503 with a JSON body when not ready — the body is the signal. Adversarial subtlety: absent fields render as "not reported", never fabricated — the only field-level UI proof that `canonicalEngine` is present is the hashrate basis line — real: "pool-accepted shares or measured device run only". Always also screenshot the raw `/api/v1/mla1517/status` JSON.

Known benign console noise: `favicon.ico` 404 (no favicon reference/asset shipped), `/.well-known/appspecific/com.chrome.devtools.json` 404 when DevTools opens, and — new since the ops-console redesign — a `GET /api/v1/ready-to-mine 503 (Service Unavailable)` console error on every 5 s poll (the endpoint answers 503 with a JSON body by design; Chrome auto-logs non-2xx fetches — it is not a JS fault).

## Stratum CLI checks (no pool connection needed)

- `python mining/stratum_bridge.py --dry-run` without `--worker` must exit 2 in <1 s with "no default account is assumed" — instant exit proves it errors before connecting.
- `.env.<pool>` nuance: `stratum_bridge.py` auto-loads only repo-root `.env` (module-level `load_env_file()`), NOT `.env.viabtc`/`.env.braiins` — those files are auto-merged only by `live_mine.py`/`live_handshake.py` (`.env` + `.env.<pool>` + process env, process env wins, pool-specific vars first). To test bridge resolution from a pool env file, export it first (`set -a; source .env.viabtc; set +a`); then `--dry-run` prints `Connecting to Stratum pool btc.viabtc.io:3333 as PYTHIA.001` before any network I/O. `_default_pool_env()` is importable (`from mining.stratum_bridge import _default_pool_env`) for network-free resolution checks, e.g. cross-pool isolation: `VIABTC_ENDPOINT=btc.viabtc.io:3333 BRAIINS_ACCOUNT=PYTHAGORAS.PYTHIA PYTHIA_POOL_PROFILE=braiins` must resolve to the braiins endpoint+worker, never a viabtc-endpoint/braiins-worker mix.
- The devinbox CAN reach real pools: with `.env.viabtc` exported, `--dry-run` authorizes `PYTHIA.001` on `btc.viabtc.io:3333`, receives a live job, grinds one nonce window on CPU, and submits nothing — good e2e evidence that stays safe because dry-run never submits.
- `python mla1517_platform_v3.4/python/manifold_pool_coordinator.py --help` and `mining_runtime.py --help` share `_build_parser` (runtime imports it) — `--tls` lives there.
- `parse_endpoint` scheme table is importable for negative tests with `PYTHONPATH=mla1517_platform_v3.4/python`; script-file runs don't need PYTHONPATH (sys.path[0] = the script dir already contains `mla1517/`).

## Solver-arms testing (PYTHIA_SOLVER_ARMS, PR-22+)

- `PYTHIA_SOLVER_ARMS` (default 1, floor 1, ceiling 600, invalid → 1 + `solver_arms_invalid` audit) sets `status.solvers` = {arms, lanes_per_arm:32, lane_ceiling:600, nonce_partition, hashrate}. The "Solver manifold" UI card renders only when `status.solvers` exists — `{arms} independent solvers` / `{arms*32}` total.
- **Arms only supervise when `opencl_devices()` is non-empty** — on devinbox (no pyopencl) the gate fails closed and `status.workers` shows NO stratum-bridge rows; that honest absence is the expected state, not a bug. A per-worker hashrate row can only populate on a box with an OpenCL device.
- A **manual arm** is how you prove measured hashrate lands: `set -a; source .env.viabtc; set +a` then `env PYTHIA_WORKER_NAME=stratum-bridge-1 PYTHIA_WORKER_HEARTBEAT_DIR=C:/pythia-hb PYTHIA_IDENTITY_HMAC_SECRET=<64 hex> PYTHONPATH=mla1517_platform_v3.4/python .venv/Scripts/python.exe -u mining/stratum_bridge.py --continuous --dry-run --backend cpu`. Boot the API with the SAME `PYTHIA_WORKER_HEARTBEAT_DIR` so its `/metrics` glob reads the arm's sidecar.
- `PYTHIA_IDENTITY_HMAC_SECRET` MUST be a 64-hex (32-byte) value — the emitter crashes in `tick()` without it (`hmac.new(None)` TypeError), and with `PYTHIA_WORKER_NAME` set the whole arm dies. Secret value doesn't need to match the API's for metrics passthrough — only `.bin` heartbeat HMAC uses it, and unsigned `.metrics.json` is what `/metrics` publishes (freshness TTL 30 s).
- Evidence chain: `C:\pythia-hb\<worker>.bin` = 62 bytes (30 B body + 32 B tag); `<worker>.metrics.json` counters carry `hashrate_hs, solver_lanes=32, nonce_order=m32, nonce_window, extranonce2, coverage_nonces, job_id, backend`; `/metrics` shows `pythia_worker_hashrate{name="<worker>"}` + `pythia_heartbeat_write_duration_*` phase histograms even for non-supervised workers.
- **Frontend rebuild is required when the diff touches `src/`** — `dist/public` is not committed; a stale bundle silently lacks new UI. Verify with `grep -o "<new string>" dist/public/assets/*.js` before UI-testing.
- **Small-button click coordinates**: the runner-card START buttons and mining-verb buttons are ~70px wide and easy to miss — aim at card_left+35px, not mid-card. A missed click lands on the card body silently (no error); verify the intended POST actually fired (state flip or config change) before assuming a defect.

## Runtime-control testing (GET/PUT /api/v1/config, PR-22+)

- `runtime_config.py` is the contract: `PYTHIA_RUNTIME_CONFIG` env wins, else `<repo>/data/runtime_config.json` (gitignored, auto-created on first PUT). Arms re-read the file each window — hashrate pacing + the live-submit gate apply without restarts; pool/arm-count changes apply via arm respawns.
- GET `/api/v1/config` returns the REDACTED `public_view` (pools get `password_committed` not the password; live_submit gets `approval_bound` not the id) plus `effective_arms` + `live_arms`. PUT accepts ONLY {pools, solvers, hashrate, live_submit, window} — unknown sections → 400 `unknown config sections`. Success → `{ok:true, applied:{spawned,retired,restarted,note?}, config}`.
- Bounds (rejected at write, never clamped): arms/workers [1,600], hashrate target [0,1e18] (1 EH/s), window [1,4194304]. **Client vs server error strings DIFFER**: the UI validates before PUT (banner shows `arms must be an integer in [1, 600]` — note space + `arms` prefix), while direct PUT to the server returns `solvers.arms must be an integer in [1,600]` — verify BOTH layers.
- `"use"` on a pool sends `password:""` for every row — the server re-merges the stored password by endpoint+worker key. Adversarial check: after any pools write, GET must still show `password_committed:true` on every surviving row or the merge broke.
- Arming live-submit: the server injects `approval_id=sha256(endpoint|worker)` of the ENABLED pool — verify it in the file (`data/runtime_config.json`) against `hashlib.sha256(b"endpoint|worker")`. A pools write WITHOUT an explicit live_submit section auto-disarms + wipes the approval (pool switch revokes arming — test it while armed).
- On no-OpenCL boxes `_apply_runtime_config` short-circuits → every applied PUT's note is `no OpenCL device — config saved, arms stay armed_no_device`; live_arms stays []. Expected, not a failure.
- SAFETY: `_submit_permitted` now includes a config-side gate — an ARMED config + a running arm bound to the enabled pool identity can really submit shares (dry-run still never submits regardless). Do not arm while a real arm runs; always leave the end state disarmed with approval wiped.
- Config drives status: `status.solvers.arms` = `_desired_arms()` (file wins over `PYTHIA_SOLVER_ARMS` env once the file exists) — a PUT arms=N flips the Solver-manifold card to `N independent solvers`/N*32 within the 5 s poll. Cheap coupling proof: screenshot the manifold after applying arms.

Real pool connections/share submission are gated by creds + `HYBA_*` live-submit env triple-gate — do not attempt without explicit credentials; that path is untestable on devinbox.

## PYTHIAPhiMiner checkout deltas (PR-13-era repo layout)

- Same architecture, different repo root: `C:\Users\Administrator\repos\PYTHIAPhiMiner`. Interpreter is `/c/Python312/python.exe` (no `.venv`, `python`/`py` not on PATH — matches blueprint). `main.py` inserts `mla1517_platform_v3.4/python` into `sys.path` itself, so plain script runs work; module imports (e.g. `import control_api` from a one-liner) need `PYTHONPATH=mla1517_platform_v3.4/python`.
- Frontend lives in `frontend/` (vite), builds to `dist/public` — not committed, so a fresh checkout needs `node /c/hostedtoolcache/node/20.19.0/x64/node_modules/npm/bin/npm-cli.js --prefix frontend ci` then `... run build` (node 20 works despite engines>=22; only an EBADENGINE warning).
- This `control_api.py` prints NO "listening" banner — only `[pythia-control] loaded N vars from .env` and per-request access lines. Verify boot by curling `GET /` (200) and `/api/v1/mla1517/status` (200) instead of grepping stdout.
- Views: OPERATIONS/ALGEBRA/INTELLIGENCE/MANIFOLD/AUDIT tabs (hash routes like `/#/algebra`). Honest no-hardware state renders "Standing by." + `WORKER_UNAVAILABLE`/`NO DEVICE` chips — distinct from the red `API offline` chip, which means the UI can't reach the API.
- On Chrome for Testing, `file:///` URLs render local JSON in the built-in viewer — handy for on-recording evidence of diagnose/benchmark output. Scroll needs the cursor over the JSON pane.

## System Fabric panel testing (PR-23+)

- `SystemFabricPanel` polls 5 GETs every 4 s (`/system/map`, `/system/verify`, `/intelligence/selftest`, `/agentic/status`, `/campaign/status`) plus `/api/v1/config` for the pool dropdown. Runner POSTs return 202 (idle→running) or 409; per-phase config writes inside campaign runs re-bind `live_submit` approvals via `identity_commit(endpoint|worker)` — verify by diffing `data/runtime_config.json` and hashing `endpoint|worker` yourself.
- **Runner-status GETs embed the raw `result` report** — numpy scalars inside reports (e.g. `winning_nonce` np.uint64, np.bool_) crash `json.dumps` in `_json` and permanently 500 the endpoint after a run completes; the UI card then wedges at `running` (fetch rejected → last snapshot kept). If the panel never reaches `done`, check the API log for `not JSON serializable` tracebacks before suspecting the runner.
- Verb UX gap (by design, document not fail): `POST /api/v1/mining/start` returns `{ok:false, reason:"no OpenCL device"}` at HTTP 200 — the panel's `post()` only surfaces `!res.ok`, so the refusal is invisible in the UI; prove it with curl.
- `RuntimeControlPanel` fetches `/api/v1/config` once on mount — after out-of-band config writes (campaign phases, fabric verbs) it shows STALE pools/arms/arming until reload. Use the status-driven Solver-manifold card or GET /config for post-write proof, then reload to refresh the panel.
- `mining/switch` rewrites pools → the pools-without-live_submit rule auto-disarms + wipes approval; expect `armed → off` after any switch, and re-arm via `arm live` to restore a shipped armed config.
- Campaign runner with `phases:[]` flips to `error` within one poll (honest); a real phase needs a bounded `campaign.phases` PUT — the phase's `arms`/`target_hs`/`pool`/`live_submit` writes persist, so restore the pre-test config (backup the file first) and re-clear phases afterward.
