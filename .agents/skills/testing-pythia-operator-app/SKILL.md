---
name: testing-pythia-operator-app
description: How to boot and end-to-end test the PYTHIA operator app (control API + React operator UI) on the devinbox Windows environment, including required stratum env vars and fail-closed expectations.
---

# Testing the PYTHIA operator app

Repo: `C:\Users\Administrator\repos\PYTHIPhiMiner` on devinbox (older notes may say `C:\Users\Administrator\PYTHIA`). Interpreter: prefer `.venv\Scripts\python.exe` — it carries the editable install so `chronus/mla1517_platform/python` is already on `sys.path` (no PYTHONPATH needed for `Intelligence.self_test`, `control_api`, or `mining/*` imports). Fallback: `C:\devin\python\python.exe` (embeddable-style, do not use `py`). Browser: `C:\devin\chrome\chrome-win64\chrome.exe`. UI build output: `dist/public`. **npm on PATH fails inside Git Bash** (`npm`/`npm.cmd` → "No such file or directory") — invoke npm-cli directly: `node /c/hostedtoolcache/node/20.19.0/x64/node_modules/npm/bin/npm-cli.js run build`. Also: each `exec` call resets cwd (prefix `cd ~/repos/PYTHIPhiMiner`), Windows `timeout` cmd is not GNU timeout (use exec timeout), and native-Windows `.venv/Scripts/python.exe` cannot resolve Git-Bash `/tmp` paths — pipe via stdin or `cat /tmp/x > data/.tmp` first when python must read a bash-created file.

## Booting the control API (`python main.py`)

`main.py` → `control_api.main()` serves statics from `--web-root` plus `/api/*` JSON on the same origin/port. Boot is FAIL-CLOSED on stratum identity — without env it exits 1 with `StartupConfigError: MLA1517_STRATUM_USER is required` (see `startup_contract.py:126-165`). A repo-root `.env` is auto-loaded (`_load_env_file`, process env wins); `.env.example` documents the full surface.

Boot-order contract (each missing piece fails closed with its own message):
1. `MLA1517_STRATUM_USER` missing → `MLA1517_STRATUM_USER is required`
2. `MLA1517_STRATUM_PASSWORD` missing → `MLA1517_STRATUM_PASSWORD is required`
3. `PYTHIA_POOL_PROFILE` not in {braiins, viabtc} → `PYTHIA_POOL_PROFILE must be braiins or viabtc` (checked AFTER user/password present)
4. endpoint missing → `canonical MLA1517 Stratum endpoint is required` (resolved from `MLA1517_STRATUM_ENDPOINT` or `MLA1517_{PROFILE}_ENDPOINT`)
5. alias conflicts (`PYTHIA_STRATUM_*` vs canonical) → `ConfigConflict` under default `compat` policy.

Minimum placeholder env for a test boot (identity is only HMAC-committed — the control API never dials the pool):
```
MLA1517_STRATUM_USER=testoperator.001
MLA1517_STRATUM_PASSWORD=x
MLA1517_BRAIINS_ENDPOINT=stratum.braiins.com:3333
python main.py --host 127.0.0.1 --port 3000 --web-root dist/public
```
With repo-scoped secrets bound via exec env (`VIABTC_USERNAME`/`VIABTC_PASSWORD` or `BRAIINS_*`), map them: `MLA1517_STRATUM_USER="$VIABTC_USERNAME" MLA1517_STRATUM_PASSWORD="$VIABTC_PASSWORD" MLA1517_VIABTC_ENDPOINT=btc.viabtc.io:3333 PYTHIA_POOL_PROFILE=viabtc`. Real creds are safe — nothing dials the pool; `status.host.stratum.user_redacted` shows `first2***` (e.g. `PY***`) proving real identity load. Use `python -u` or expect block-buffered stdout when redirected.

To prove the bare-env fail-closed path cleanly use `env -i` with minimal pass-through:
`env -i PATH="$PATH" USERPROFILE="$USERPROFILE" HOME="$HOME" SYSTEMROOT="$SYSTEMROOT" TEMP="$TEMP" TMP="$TMP" .venv/Scripts/python.exe main.py ...`

On Windows, Bash-embedded `python` resolves via PATH the same as cmd. Success line: `PYTHIA Python control API listening on 127.0.0.1:3000`. Note: stdout is block-buffered when redirected to a file — run in a visible console for the boot banner, or accept delayed flush in logs.

Expected honest no-hardware state on devinbox (no pyopencl, no MMIO device):
- `workers armed but not started: MLA1517_MMIO_DEVICE is unset` → workers `agentic-mining` + `salamander` in state `armed_no_device`
- `stratum bridge not started (bridge=True, opencl=False, creds=...)` — creds=True when real secrets bound
- status JSON: `device.available=false`, `device.count=0`, workers `armed_no_device`, `canonicalEngine.execution` = "device-required; fails closed when OpenCL is unavailable", `canonicalEngine.hashrate` = "pool-accepted shares or measured device run only" (policy string, never a number), `fallback:false`, `stratum.connected:false`, `stratum.status:"not_reported_by_worker_heartbeat"`, `solvers`={arms:1,lanes_per_arm:32,lane_ceiling:600}, `measurement`="no synthetic result; no measurement until a real run"
- `GET /api/v1/readyz` → 200 `{"ready":true,"reason":"ok"}` (identity HMAC verified at boot)
- `GET /api/v1/ready-to-mine` → 503 `{"ready":false,"reason":"worker_not_running","details":{"worker":"agentic-mining","state":"armed_no_device"}}` (first registered worker wins the details slot)
- `POST /api/v1/mining/start` → 200 `{"ok":false,"reason":"no OpenCL device — arms stay armed_no_device","spawned":[]}`
- `GET /api/v1/status` is NOT a route → honest 404 `{"error":"endpoint not implemented"}` via the `/api/` catch-all. Real status routes: `/status` and `/api/v1/mla1517/status`.
- `GET /metrics` → `pythia_worker_up{name}=0`, `pythia_worker_hashrate{name}=0.0`, all `pythia_ready_to_mine{reason=*}` = 0.0 when not ready (the reason label only goes 1.0 when ready=true).

Side effects: writes `C:\app\data\BOOT_AUDIT.log` + `C:\app\data\pythia-main.lock` (msvcrt lock; released on exit). `fs_selfcheck` runs `stat -f` on the heartbeat dir (`%LOCALAPPDATA%\pythia\hb` on this box — `AppData\Local\pythia\hb`) → expected `No such file or directory` noise on Windows, harmless.

## Platform test invocation — cwd matters (verified 2026-09-29)

**Run platform unittest discover from the REPO ROOT**: `cd /c/Users/Administrator/repos/PYTHIPhiMiner && .venv/Scripts/python.exe -X utf8 -m unittest discover -s chronus/mla1517_platform/python` → 171 tests, ~7 s, 6 env-guarded skips.
- Do NOT cd into `chronus/mla1517_platform/python` and run `unittest test_<module>`: `toe_adapter.py` resolves `Intelligence.toe_bridge` via the *cwd* entry on sys.path (repo-root `Intelligence/` is NOT covered by the editable install). From inside the platform dir the import fails → `TOEMiningAdapter()` → `self.toe=None` → `test_submit_record_runs_toe_heal_and_choose_without_share` fails spuriously ("TOE adapter unavailable at startup").
- Do NOT add `-t .` (top-level-dir): the start dir isn't a package → `ImportError: Start directory is not importable`.
- `python -m unittest` puts cwd on sys.path, so repo-root invocation makes `Intelligence` resolvable.

## Verifying the canonical-engine console

`App.tsx` polls `/api/v1/mla1517/status` + `/api/v1/ready-to-mine` every 5 s same-origin (`apiFetch` — no absolute API base baked into the bundle) and passes the payloads to `Mla1517MiningPanel` and `Header`. The ready-to-mine endpoint returns 503 with a JSON body when not ready — the body is the signal. Adversarial subtlety: absent fields render as "not reported", never fabricated — the only field-level UI proof that `canonicalEngine` is present is the hashrate basis line — real: "pool-accepted shares or measured device run only". Always also screenshot the raw `/api/v1/mla1517/status` JSON.

Expected UI (no-device box, real creds): header "PYTHIA Ops" + "MLA1517 canonical" badge; amber `worker_not_running` chip + dim `no device` chip; hero "Standing by." + "Readiness gate reports worker_not_running..."; Stratum identity card (profile/endpoint/Worker `**`-redacted/Password "committed (HMAC)"/Pool link amber `not_reported_by_worker_heartbeat`); Canonical engine card (amber fails-closed execution line, policy-string hashrate basis, ladder chips L10 L12 L15 L18 L20 L31 L50 L76); Solver manifold "1 independent solver"/32/32; workers card 2× ARMED_NO_DEVICE rows with hashrate/shares "not reported"; OpenCL card "No OpenCL device discovered. The canonical engine fails closed on hardware absence by design."; measurement honesty line.

Kill the API mid-session to prove honesty: within one 5 s poll the header shows red "API offline" and the hero flips to "Control plane unreachable. ... nothing below is live" — stale cards remain but are honestly flagged dead. A fabricating UI would keep showing a live state.

Known benign console noise: `favicon.ico` 404 (no favicon reference/asset shipped), `/.well-known/appspecific/com.chrome.devtools.json` 404 when DevTools opens, and — new since the ops-console redesign — a `GET /api/v1/ready-to-mine 503 (Service Unavailable)` console error on every 5 s poll (the endpoint answers 503 with a JSON body by design; Chrome auto-logs non-2xx fetches — it is not a JS fault).

## Stratum CLI checks (no pool connection needed)

- `python mining/stratum_bridge.py --dry-run` without `--worker` must exit 2 in <1 s with "no default account is assumed" — instant exit proves it errors before connecting.
- `.env.<pool>` nuance: `stratum_bridge.py` auto-loads only repo-root `.env` (module-level `load_env_file()`), NOT `.env.viabtc`/`.env.braiins` — those files are auto-merged only by `live_mine.py`/`live_handshake.py` (`.env` + `.env.<pool>` + process env, process env wins, pool-specific vars first). To test bridge resolution from a pool env file, export it first (`set -a; source .env.viabtc; set +a`); then `--dry-run` prints `Connecting to Stratum pool btc.viabtc.io:3333 as PYTHIA.001` before any network I/O. `_default_pool_env()` is importable (`from mining.stratum_bridge import _default_pool_env`) for network-free resolution checks, e.g. cross-pool isolation: `VIABTC_ENDPOINT=btc.viabtc.io:3333 BRAIINS_ACCOUNT=PYTHAGORAS.PYTHIA PYTHIA_POOL_PROFILE=braiins` must resolve to the braiins endpoint+worker, never a viabtc-endpoint/braiins-worker mix.
- The devinbox CAN reach real pools: with `.env.viabtc` exported, `--dry-run` authorizes `PYTHIA.001` on `btc.viabtc.io:3333`, receives a live job, grinds one nonce window on CPU, and submits nothing — good e2e evidence that stays safe because dry-run never submits.
- `python chronus/mla1517_platform/python/manifold_pool_coordinator.py --help` and `mining_runtime.py --help` share `_build_parser` (runtime imports it) — `--tls` lives there.
- `parse_endpoint` scheme table is importable for negative tests with `PYTHONPATH=chronus/mla1517_platform/python`; script-file runs don't need PYTHONPATH (sys.path[0] = the script dir already contains `chronus/mla1517/`).

## Solver-arms testing (PYTHIA_SOLVER_ARMS, PR-22+)

- `PYTHIA_SOLVER_ARMS` (default 1, floor 1, ceiling 600, invalid → 1 + `solver_arms_invalid` audit) sets `status.solvers` = {arms, lanes_per_arm:32, lane_ceiling:600, nonce_partition, hashrate}. The "Solver manifold" UI card renders only when `status.solvers` exists — `{arms} independent solvers` / `{arms*32}` total.
- **Arms only supervise when `opencl_devices()` is non-empty** — on devinbox (no pyopencl) the gate fails closed and `status.workers` shows NO stratum-bridge rows; that honest absence is the expected state, not a bug. A per-worker hashrate row can only populate on a box with an OpenCL device.
- A **manual arm** is how you prove measured hashrate lands: `set -a; source .env.viabtc; set +a` then `env PYTHIA_WORKER_NAME=stratum-bridge-1 PYTHIA_WORKER_HEARTBEAT_DIR=C:/pythia-hb PYTHIA_IDENTITY_HMAC_SECRET=<64 hex> PYTHONPATH=chronus/mla1517_platform/python .venv/Scripts/python.exe -u mining/stratum_bridge.py --continuous --dry-run --backend cpu`. Boot the API with the SAME `PYTHIA_WORKER_HEARTBEAT_DIR` so its `/metrics` glob reads the arm's sidecar.
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

## System Fabric panel testing (PR-23+)

- `SystemFabricPanel` polls 5 GETs every 4 s (`/system/map`, `/system/verify`, `/intelligence/selftest`, `/agentic/status`, `/campaign/status`) plus `/api/v1/config` for the pool dropdown. Runner POSTs return 202 (idle→running) or 409; per-phase config writes inside campaign runs re-bind `live_submit` approvals via `identity_commit(endpoint|worker)` — verify by diffing `data/runtime_config.json` and hashing `endpoint|worker` yourself.
- **Runner-status GETs embed the raw `result` report** — numpy scalars inside reports (e.g. `winning_nonce` np.uint64, np.bool_) crash `json.dumps` in `_json` and permanently 500 the endpoint after a run completes; the UI card then wedges at `running` (fetch rejected → last snapshot kept). If the panel never reaches `done`, check the API log for `not JSON serializable` tracebacks before suspecting the runner.
- Verb UX gap (by design, document not fail): `POST /api/v1/mining/start` returns `{ok:false, reason:"no OpenCL device — arms stay armed_no_device"}` at HTTP 200 — the panel's `post()` only surfaces `!res.ok`, so the refusal is invisible in the UI; prove it with curl.
- `RuntimeControlPanel` fetches `/api/v1/config` once on mount — after out-of-band config writes (campaign phases, fabric verbs) it shows STALE pools/arms/arming until reload. Use the status-driven Solver-manifold card or GET /config for post-write proof, then reload to refresh the panel.
- `mining/switch` rewrites pools → the pools-without-live_submit rule auto-disarms + wipes approval; expect `armed → off` after any switch, and re-arm via `arm live` to restore a shipped armed config.
- Campaign runner with `phases:[]` flips to `error` within one poll (honest); a real phase needs a bounded `campaign.phases` PUT — the phase's `arms`/`target_hs`/`pool`/`live_submit` writes persist, so restore the pre-test config (backup the file first) and re-clear phases afterward.

## Dead-compositor (dwm) fallback — when screenshots record black/empty

If `tasklist` shows a `csrss` window titled `dwm.exe - Application Error`, dwm crashed and nothing composites: screenshots are black or desktop-only. Recovery attempt order (each may fail — have the fallbacks ready):
1. Dismiss the error dialog: `Get-Process csrss | select MainWindowHandle` then `PostMessage(hwnd, WM_CLOSE, 0, 0)` — often restores partial paint.
2. `ctrl+shift+win+b` (graphics reset), mouse/keyboard events to nudge repaint.
3. Kill/respawn dwm, `tscon` (may be denied 7045), `ChangeDisplaySettings` mode flip, `pnputil /restart-device` on the active display adapter (this box: `ROOT\IDDSAMPLEDRIVER\0000` IddSampleDriver virtual monitor).

When dwm stays dead (this box it did — app windows never composite):
- **Rendered-pixel evidence still works**: headless Chrome uses its own rasterizer, independent of dwm:
  `"C:\devin\chrome\chrome-win64\chrome.exe" --headless=new --disable-gpu --hide-scrollbars --window-size=1600,4600 --virtual-time-budget=9000 --screenshot=out.png http://127.0.0.1:3000/`
  A tall `--window-size` captures the full long page; `--virtual-time-budget` lets React mount + first polls resolve. Each invocation is a FRESH connect — two consecutive shots prove reconnect/state-reconstruction.
- **Offline-state render**: `python -m http.server 8080 --directory dist/public` then headless-load `127.0.0.1:8080` — the SPA loads, same-origin `/api/*` fetches 404/fail → the app renders its genuine degraded/offline state (this baseline: `STANDBY` chip + runner cards `OFFLINE` + all fields `not reported`; NOT the red "API offline" chip older PYTHIA had).
- **Real SIGINT delivery**: `exec` with `tty:true` + `write_to_process` `bytes_input=<C-c>` delivers a true Ctrl+C → `KeyboardInterrupt` (exit 130, traceback, `finally` cleanup). `AttachConsole(pid)+GenerateConsoleCtrlEvent(0,0)` via ctypes posts OK but the target python survived on this box — conpty/console-group semantics; don't rely on it. `GenerateConsoleCtrlEvent(1,0)` = CTRL_BREAK hard-terminates (no cleanup — same net as `os.kill(pid,SIGTERM)` = TerminateProcess on Windows).
- `SetForegroundWindow`/`AppActivate` + `SendKeys` cannot focus windows when dwm is dead — blind keyboard input is unreliable.

## Guardian-mediated privileged routes + console fixes (PR-22-era, owner-b branch)

- Newer branches add an AL HARAS guard: `PRIVILEGED_RE = /^\/api\/v1\/(mining|policy|worker|recovery|admin|toe|quantum|scale|assembly|security)\//` (mirrors `control_api._PRIVILEGED_PREFIXES`). Denial ladder verified live: no creds → **400** `reason:"TENANT_AND_ACTOR_REQUIRED"`; tenant+actor but no Bearer → **402** `SUBSCRIPTION_DENIED`; invalid Bearer → **403**. Guardian unavailable → **503** `guardian_dependency_unavailable` (NOT retryable — no prompt).
- `frontend/src/lib/api.ts` prompts via **native `window.prompt`** (Esc/empty = decline → sessionStorage flag). Subscription path = 3 sequential prompts: `Subscription token (al_haras bearer)` → `Tenant id (X-HYBA-Tenant)` → `Actor id (X-HYBA-Actor)`; flag `pythia.subscriptionDeclined`. Mutating non-privileged POST (e.g. `agentic/start`) gets 401 (when `EUCLID_ADMIN_API_KEY` set server-side) → prompt `Operator key (EUCLID_ADMIN_API_KEY)`; flag `pythia.operatorKeyDeclined`. Entering creds CLEARS the flag → a denied retry re-prompts (test with garbage creds in a fresh tab — sessionStorage is per-tab).
- Verification recipe: `EUCLID_ADMIN_API_KEY=test-operator-key` on the API → load console → evidence poll prompts → Esc → assert ≥2 poll cycles silent → click mining START → expect `rejected (400)` text under the verbs, no prompt → agentic START → operator-key prompt → Esc → re-click → audit trail shows a 2nd `control_refused` but no prompt. Refusals are AUDITED server-side (`control_refused` events in `/api/v1/audit/tail` — UI-visible proof the denied call fired).
- `legacy/PYTHIA_Frontend` dev server: `C:\hostedtoolcache\node\24.0.1\x64\node.exe` + its npm-cli (`npm run dev` → `scripts/with-app-env.mjs vite dev --port 8080`, proxies `/api|/healthz|/readyz|/metrics` → :3000). Dark-themed different UI ("The operator console that refuses to lie").
- Persistent pill (`pythia.backendRecovery`, localStorage, zustand persist v1, partializes `{recovery}`): thresholds 1→degraded, 2→recovering, ≥3→circuit_open, ≥6→fail_closed at POLL_MS=2000. `StatusPill` labels: healthy→`idle`/`workers up`/`stratum up`; `!healthOk`→muted `backend offline`; `circuit_open|fail_closed`→red `FAIL CLOSED`. Kill API ~8 s → FAIL CLOSED; F5 → pill must read `fail closed` AT FIRST PAINT (rehydrated before any poll — a broken persist would paint `idle`/`backend offline` until ≥1 poll failed). Read `localStorage.getItem('pythia.backendRecovery')` via browser_console for `{"state":{"recovery":{"state":"fail_closed","consecutiveFailures":N}},"version":1}`.
- Branch note: the `discovery` worker actually RUNS on no-device boxes (simulated-twin workload) → ready reason flips to `stratum_disconnected` once it's up.
