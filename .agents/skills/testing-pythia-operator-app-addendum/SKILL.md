---
name: testing-pythia-operator-app-addendum
description: Addendum to testing-pythia-operator-app — AL HARAS security endpoints, second control-API instance, guardian fail-closed triggers, and post-PR-20 denial body shapes on Windows.
---

# AL HARAS security-endpoint testing addendum (extends testing-pythia-operator-app)

Applies to the PYTHIPhiMiner checkout (`C:\Users\Administrator\repos\PYTHIPhiMiner`); the same layout may exist in `repos\PYTHIA`.

## Running a SECOND control-API instance alongside the first
`control_api` takes a process-global boot lock (`msvcrt` lock on `PYTHIA_BOOT_LOCK`, default `/tmp/pythia/pythia-main.lock` → effectively `C:\app\data\pythia-main.lock` on this box). A second `main.py` exits 1 with `RuntimeError: canonical control plane already running`. To run a side-by-side instance (e.g. a guardian-broken instance vs a healthy one), override BOTH paths:
```
env PYTHIA_BOOT_LOCK='C:/app/data/pythia-test2.lock' PYTHIA_BOOT_AUDIT='C:/app/data/BOOT_AUDIT-2.log' \
  MLA1517_STRATUM_USER=testoperator.001 MLA1517_STRATUM_PASSWORD=x \
  MLA1517_STRATUM_ENDPOINT=stratum.braiins.com:3333 \
  /c/Python312/python.exe -u main.py --host 127.0.0.1 --port 3001 --web-root dist/public
```
`kill_shell` may not terminate the underlying Windows `python.exe` — if a reboot exits 1 with "canonical control plane already running", find the listener via `netstat -ano | grep :PORT` and `taskkill //PID <pid> //F` before retrying.

## Guardian availability matrix (Windows devinbox)
- Default env (no valid durable AL HARAS configuration): `pythia_guardian_api` fails closed; there is **no in-memory audit fallback**. Privileged routes surface the guardian dependency as unavailable rather than weakening the authority boundary.
- `AL_HARAS_SUBSCRIPTION_KEYS` malformed JSON/non-dict, or durable audit initialisation failure, leaves every privileged request unavailable/denied. `pythia_guardian_api` is `lru_cache`d but exceptions are NOT cached, so corrected configuration can be retried without process-global stale success. The rest of the API may remain live; fail-closure is targeted, not a dead API.
- `AL_HARAS_ENABLE_LHRAS=1` without `AL_HARAS_LHRAS_CONFIG` also 503s — do not enable unless a config is provisioned.
- To exercise the POST privileged path (POST_TABLE routes like `/api/v1/mining/start`) through `_guardian_preflight`, the broken instance ALSO needs `EUCLID_ADMIN_API_KEY` set — the operator-key gate (401 `operator key required` with key configured, 403 `... is not configured` without) runs BEFORE the guardian preflight. Send `Authorization: Bearer <key>` and expect the 503, not a mining action.

## Fail-closed body shapes — TWO correct envelopes (post-PR-20)
- `_guardian_preflight` (all `_PRIVILEGED_PREFIXES` GETs — `/api/v1/mining/*`, `/api/v1/security/*`, `/api/v1/toe/*`, `/api/v1/policy/*`, `/api/v1/worker/*`, `/api/v1/recovery/*`, `/api/v1/admin/*`, `/api/v1/quantum/*`, `/api/v1/scale/*`, `/api/v1/assembly/*` — plus privileged POST_TABLE routes): **503** `{"available": false, "reason": "guardian_unavailable: <ExcType>: <msg>"}` or `"guardian_dependency_unavailable"` when the import itself is None.
- `POST /api/v1/security/evaluate` and `POST /api/v1/toe/collapse` go through `_guardian_api()` instead: **503** `{"allowed": false, "reason": "guardian_unavailable"}`. Both shapes are by design — do not flag the difference as inconsistency.

## Healthy-guardian denial ladder (privileged GETs are NOT public on this branch)
`GET /api/v1/security/status` and `GET /api/v1/mining/evidence` run `_guardian_preflight` first — the older claim that security/status is a fully public GET is stale. Order inside `GuardianAPI.evaluate`:
1. Missing `X-HYBA-Tenant` or `X-HYBA-Actor` → **400** `TENANT_AND_ACTOR_REQUIRED` (a signed boundary-denial receipt: `allowed:false`, `evidence_id`, `payload_hash`, `tenant_id:"UNKNOWN"`).
2. Tenant+actor but no `Authorization: Bearer ...` → **402** `SUBSCRIPTION_DENIED:missing or malformed subscription token` + `subscription_url`.
3. `Bearer <malformed>` → **403**, same `SUBSCRIPTION_DENIED:` family.
4. `POST /api/v1/toe/collapse` additionally requires a non-empty JSON object → `{}` returns 400 `empty_body` before the guardian.
No keyring on this box → an ALLOWED verdict is untestable without `AL_HARAS_SUBSCRIPTION_KEYS` + a signed token.

## Honest-state expectations
- `ready_to_mine.reason` FLAPS between `worker_unavailable` and `stratum_disconnected` — the discovery worker's heartbeat cycles live/stale (an `hmac_invalid` malformed row can appear when two instances share the heartbeat dir). Both are honest not-ready reasons; assert `ready:false` + HTTP 503, record whichever string renders.
- `status.device.available` can be `true` with `count:1` — the CPU logical substrate (`gpu.detected_backend:"cpu"`, `logical_substrate.host_backend:"cpu"`). The honest signature is `opencl_device_count:0`, `physical_gpu_count:0`, `devices:[]`, `mining_device.bound:false` — never a named GPU. `hardware/status.opencl.available:true` refers to substrate availability, not a physical device.
- No `mining/stratum_bridge.py` in this checkout — stratum checks go through `GET /api/v1/stratum/status` (CONFIGURED/DISCONNECTED fallback, worker redacted `te***`).

## Frontend rendering of guardian denials
- `MiningEvidencePanel` gates on `response.ok` → a 400/503 keeps evidence null → "Waiting for the miner to publish evidence." + "MINING EVIDENCE UNAVAILABLE" chip.
- `EngineAlgebraCard` parses the JSON body unconditionally → the denial receipt lands in state → "Not reported: no window dispatched yet." Both are honest (nothing fabricated), just differently worded.
- `frontend/src/security/al_haras_gateway.ts` is NOT imported by the app bundle — type-level regressions there only surface via `npm run lint` (`tsc --noEmit`), not `vite build`.
- Chrome for Testing renders JSON bodies in-page even on 400/503 navigations — navigating to a fail-closed endpoint gives clean recorded evidence; curl remains authoritative for the status code.
- Chrome for Testing on this box is NOT launched with `--remote-debugging-port`, so the `browser_console` CDP tool cannot connect — use F12 DevTools + screenshots for console checks.
