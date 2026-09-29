---
name: testing-pythia-operator-app-addendum
description: Addendum to testing-pythia-operator-app — AL HARAS security endpoints (status/subscribe/evaluate/toe-collapse), running a second control-API instance alongside the first, and fail-closed triggers on Windows.
---

# AL HARAS security-endpoint testing addendum (extends testing-pythia-operator-app)

Applies to the PYTHIAPhiMiner checkout (`C:\Users\Administrator\repos\PYTHIPhiMiner`); the same layout may exist in `repos\PYTHIA`.

## Running a SECOND control-API instance alongside the first
`control_api` takes a process-global boot lock (`msvcrt` lock on `PYTHIA_BOOT_LOCK`, default `/tmp/pythia/pythia-main.lock` → effectively `C:\app\data\pythia-main.lock` on this box). A second `main.py` exits 1 with `RuntimeError: canonical control plane already running`. To run a side-by-side instance (e.g. a guardian-broken instance vs a healthy one), override BOTH paths:
```
env PYTHIA_BOOT_LOCK='C:/app/data/pythia-test2.lock' PYTHIA_BOOT_AUDIT='C:/app/data/BOOT_AUDIT-2.log' \
  MLA1517_STRATUM_USER=testoperator.001 MLA1517_STRATUM_PASSWORD=x \
  MLA1517_STRATUM_ENDPOINT=stratum.braiins.com:3333 \
  /c/Python312/python.exe -u main.py --host 127.0.0.1 --port 3001 --web-root dist/public
```

## Guardian availability matrix (Windows devinbox, no fcntl)
- Default env (no `AL_HARAS_*`): `build_guardian` raises RuntimeError inside `pythia_guardian_api`, caught → guardian runs on IN-MEMORY `HashChainAudit` → `GET /api/v1/security/status` returns **200** with `audit_durable:false`, `configured:false` (empty keyring), `subscription_required:true`, `lhras_enabled:false`. This is the expected healthy degraded state, NOT a 503.
- `AL_HARAS_SUBSCRIPTION_KEYS` = malformed JSON (or a non-dict): `ALHarasSettings.from_env` raises BEFORE the in-memory fallback can run → every security endpoint answers **503** `{"allowed":false,"reason":"guardian_unavailable"}` (proper response, not a dropped connection — the pre-hardening behavior was a dropped conn). `pythia_guardian_api` is `lru_cache`d per process but exceptions are NOT cached, so every request re-fails → all four endpoints 503 consistently. The rest of the API (`/api/v1/mla1517/status`, statics) stays 200.
- `AL_HARAS_ENABLE_LHRAS=1` without `AL_HARAS_LHRAS_CONFIG` also 503s — do not enable unless a config is provisioned.

## Evaluate/collapse fail-closed contract
`POST /api/v1/security/evaluate` and `POST /api/v1/toe/collapse` check headers INSIDE `GuardianAPI.evaluate`, in this order:
1. Missing `X-HYBA-Tenant` or `X-HYBA-Actor` → **400** `TENANT_AND_ACTOR_REQUIRED` (before auth is even checked — always send both headers when testing 402/403).
2. No `Authorization: Bearer ...` → **402** verdict + `subscription_url`; `reason` = `SUBSCRIPTION_DENIED:missing or malformed subscription token`.
3. `Bearer badtoken` (or any malformed token) → **403**, same `SUBSCRIPTION_DENIED:` reason family.
4. `POST /api/v1/toe/collapse` additionally requires a non-empty JSON object → `{}` returns 400 `empty_body` before guardian is consulted.
There is no way to mint a valid subscription token with an empty keyring — the allowed path is untestable on devinbox without `AL_HARAS_SUBSCRIPTION_KEYS` populated plus a signed token.

## Misc findings
- Frontend: `frontend/src/security/al_haras_gateway.ts` is currently NOT imported by the app bundle — tree-shaken out of `dist/public` (grep confirms neither `resonance_valid` nor `authenticated` appear in the bundle). Type-level regressions there only surface via `npm run lint` (`tsc --noEmit`), not `vite build`.
- `npm run lint` (tsc --noEmit) and `npm run build` both run fine under node 20 via `node /c/hostedtoolcache/node/20.19.0/x64/node_modules/npm/bin/npm-cli.js --prefix frontend ...`.
- Chrome for Testing on this box is NOT launched with `--remote-debugging-port`, so the `browser_console` CDP tool cannot connect — use F12 DevTools + screenshots for console checks.
- `GET /api/v1/security/status` and `/security/subscribe` are fully public (no `_refuse_unauthorized` in the GET path); API-token gating only applies to the `_POST_TABLE` runner endpoints.
