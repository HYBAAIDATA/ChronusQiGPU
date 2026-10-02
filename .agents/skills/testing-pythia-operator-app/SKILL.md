---
name: testing-pythia-operator-app
description: How to boot and end-to-end test the PYTHIA operator app (control API + React operator UI) on the devinbox Windows environment — updated for the post-fold chronus layout (chronus/mla1517_platform, chronus.mla1517 namespace), worktree checkouts, pool credentials, guardian subscription tokens, and the euclid_support mining-evidence surface.
---

# Testing the PYTHIA operator app (post-chronus-fold) — 2026-10-02 update

Everything in the base skill still holds. This update adds: worktree booting,
which repo-scoped pool secrets actually pass the fail-closed identity gate,
running the agentic-mining worker for real evidence, minting guardian
subscription tokens for privileged routes, and where `euclid_support`
evidence surfaces (API payload — NOT the UI panel).

## Environment on this box
- Repo: `C:\Users\Administrator\repos\PYTHIPhiMiner`. Worktrees may exist
  (e.g. `C:\Users\Administrator\wt-training`) — test the checkout the PR
  branch lives in, not the main checkout.
- Python `C:\Python312\python.exe`. **The editable `pythia-mla1517` install is
  STALE**: its `__editable__` finder maps `control_api`, `startup_contract`,
  `worker_lifecycle`, … to a nonexistent pre-fold `mla1517_platform_v3.4`
  layout and has **no `chronus` entry at all**. Plain `import chronus` raises
  ModuleNotFoundError. Fix per-checkout by booting with:

  `PYTHONPATH=<checkout>;<checkout>\chronus\mla1517_platform\python`

  (Windows `;` separator; verify with `python -c "import chronus, control_api;
  print(chronus.__file__)"` — every module must resolve inside the intended
  checkout. Worker subprocesses inherit PYTHONPATH via env.copy+setdefault,
  and `al_haras_pythia.py` also appends `<platform>/../../..` itself.)
- Node: prefer 24 (`node /c/hostedtoolcache/node/24.0.1/x64/node_modules/npm/bin/npm-cli.js`).
  `frontend/node_modules` is NOT committed: `npm-cli.js --prefix frontend ci`
  (~55 s) then `node frontend/node_modules/vite/bin/vite.js build` (cwd=frontend)
  → `dist/public`. Grep bundle for `chronus.mla1517.status/1` (freshness).
- Chrome: `C:\devin\chrome\chrome-win64\chrome.exe` (`--start-maximized`).
  Renders JSON in-page — navigate straight at JSON endpoints for evidence.

## Secrets: which pool creds actually work (verified 2026-10-02)
- `secret:repo:PHIDATA2/PYTHIA:VIABTC_USERNAME` is the literal placeholder
  `pythia.001` → **rejected** by `startup_contract` fail-closed
  (`MLA1517_STRATUM_USER must be a real pool worker identity, not a placeholder`).
  Do not use the viabtc profile for a real boot.
- `secret:repo:PHIDATA2/PYTHIA:BRAIINS_USERNAME`/`BRAIINS_PASSWORD` pass
  validation AND the pool genuinely connects: default catalog endpoint
  `stratum.braiins.com:3333`, `Pool: braiins connected`, `Authorized: true`,
  jobs ~1/20 s, CPU hasher ~450–650 kH/s. UI redacts worker to `Py***`.
- Submit gate stays disarmed by default (worker spawned without `--submit`;
  `/api/v1/config` shows `live_submit.enabled:false`). Grind-only, safe.

## Booting the control API (worktree-verified)
```
cd <checkout>
env PYTHONPATH='<checkout>;<checkout>\chronus\mla1517_platform\python' \
  MLA1517_STRATUM_USER=$BRAIINS_USERNAME MLA1517_STRATUM_PASSWORD=$BRAIINS_PASSWORD \
  EUCLID_ADMIN_API_KEY=test-operator-key \
  PYTHIA_EXECUTION_DEVICE=cpu \
  AL_HARAS_SUBSCRIPTION_KEYS='{"k1":"<any >=32-byte secret>"}' \
  /c/Python312/python.exe -u chronus/mla1517_platform/python/main.py \
  --host 127.0.0.1 --port 3000 --web-root dist/public
```
- `PYTHIA_EXECUTION_DEVICE=cpu` un-gates `agentic-mining` → supervisor spawns
  `mining_runtime.py` → `GeodesicProductionMiningCoordinator` →
  `EuclidMiningSupport(baseline_breadth)` ctor path + `evidence_snapshot()`
  publish loop. Needs `pip install -e turing_universal_quantum_computer
  --no-deps` **and** `pip install numpy sympy` (both blueprint maintenance
  steps — if the worker crash-loops `No module named 'turing_...'` or
  `No module named 'sympy'`, that's the missing piece).
- Provenance check: `GET /api/v1/config` → `path` field shows
  `<checkout>\data\runtime_config.json` — proves which checkout is serving.
- Evidence only publishes after stratum CONNECTS (the publish sites are in
  the job loop); while disconnected the metrics file has counters but no
  `mining_evidence` key.

## Guardian subscription tokens for privileged GETs (verified working)
Privileged prefixes (`/api/v1/mining|policy|worker|recovery|admin|toe|
quantum|scale|assembly|security/`) are mediated: need `X-HYBA-Tenant` +
`X-HYBA-Actor` headers + `Authorization: Bearer <subscription token>`;
absent → signed 400 `TENANT_AND_ACTOR_REQUIRED` denial receipt.
- Boot with `AL_HARAS_SUBSCRIPTION_KEYS` (JSON map key-id→≥32-byte secret);
  issuer `hyba-subscriptions`, capability `hyba.security`.
- Mint a token with worktree code:

  ```
  from al_haras.entitlements import SubscriptionAuthority, SubscriptionClaims
  SubscriptionAuthority({"k1": secret}, "hyba-subscriptions").issue(
      SubscriptionClaims(subscription_id="sub-e2e-test",
        tenant_id="e2e-tenant", issuer="hyba-subscriptions", key_id="k1",
        capabilities=("hyba.security",), actors=("e2e-actor",),
        not_before=0, expires_at=now+7200))
  ```
- UI fires the native 3-prompt sequence (token → tenant → actor) on the
  first denied privileged poll; entered triples are stored in sessionStorage
  and retried — a correctly minted triple returns 200.
- Gotcha: sessionStorage creds do NOT reliably survive navigation to a
  different page on the same origin in Chrome-for-Testing — pass them via
  query params on test-harness pages instead.
- CSP gotcha: every served page has `script-src 'self'` (NO unsafe-inline) —
  any custom test HTML must load JS from an external `.js` file or it
  silently never runs. `connect-src 'self'` allows same-origin fetch.

## euclid_support evidence surface (what the mining_evidence payload carries)
`EuclidProductionMiningCoordinator.evidence_snapshot()` embeds
`euclid_support.snapshot()` → heartbeat `mining_evidence`
(`%LOCALAPPDATA%\pythia\hb\agentic-mining.metrics.json`) →
`GET /api/v1/mining/evidence`. Block contains (post-PR-93):
`schema:"pythia.euclid_mining_support/1"`, `available`, `unavailable_reason`,
`baseline/current_dispatch_breadth`, `last_advice` (incl.
`evidence.policy_identity` + `claim_boundary`),
`policy_identity:{checkpoint_path,checkpoint_sha256,manifest_path,
manifest_verified,source_revision,policy_version}`,
`authority:"operational-only"`,
`single_actuator:"dispatch_breadth via this support only"`.
**The React MiningEvidencePanel does NOT render `euclid_support`** (lib/
evidence.ts row lists exclude it) — the fields exist only in the API JSON.
Verify via the endpoint response (curl with the 3 headers, or a
CSP-compliant viewer page); do not expect it in the panel UI.

## Response shapes (unchanged this round, re-verified)
- `/readyz` 200 `{"ready":true,"reason":"ok","schema_version":"chronus.mla1517.ready/1"}`
- `/api/v1/mla1517/status` `chronus.mla1517.status/1`; `workers` is a DICT
  keyed by id (agentic-mining/discovery/salamander), each with
  `state/liveness/readiness/attempts_*`.
- `/ready-to-mine` → `ready:true reason:"ok"` once pool-connected + worker live.
- `/api/v1/stratum/status` `state READY`, `transport CONNECTED`,
  `authorized/subscribed:true`, `worker:"Py***"`, `worker_live:true`.
- `/api/v1/telemetry/events` `available:true` with real stratum event stream
  when connected (schema `pythia.telemetry_events/1`).
- `/api/v1/hardware/status` `execution.backend:"cpu"`,
  `mining_device.bound:true`, `opencl.device_count:0`,
  `physical_gpu_count:0`, salamander `armed_no_device` — honest, no
  fabricated GPU.
- Audit view `#/audit` runs 15/15 local checks live.

## Blueprint
`.devin` blueprint already covers: turing editable install (no-deps),
`sympy numpy fastapi` runtime deps, `npm-cli.js --prefix frontend install`,
chronus unittest discover, startup boot path, and the stale-finder
PYTHONPATH caveat (under remote-gpu knowledge). No new blueprint steps were
needed for this session's setup.

## Devin Secrets Needed
- `secret:repo:PHIDATA2/PYTHIA:BRAIINS_USERNAME`, `...:BRAIINS_PASSWORD`
  (working pool identity)
- `secret:repo:PHIDATA2/PYTHIA:VIABTC_USERNAME`, `...:VIABTC_PASSWORD`
  (present but placeholder `pythia.001` — fails identity gate by design)
- `EUCLID_ADMIN_API_KEY` — set any test value at boot for POST coverage.
- `AL_HARAS_SUBSCRIPTION_KEYS` — a test-only keyring you choose at boot,
  paired with a locally minted token for privileged GETs.
