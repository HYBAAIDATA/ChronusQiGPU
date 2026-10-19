# Running legacy/PYTHIA_Frontend

The original PYTHIA operator console (Grok app-builder workspace:
TanStack Start + Nitro + PGLite + better-auth). Restored to run against the
canonical Python control API — no backend was rewritten and no data is
fabricated: when the control API is unreachable every panel renders its
`unavailable` / pending truth state.

## Requirements

- Node.js **>= 22.12** (TanStack Start requirement; verified on 24.0.1).
- The PYTHIA control API running (`mla1517_platform_v3.4/python/main.py`,
  default `PYTHIA_PORT=3000`).

## Install + dev server

```sh
npm install            # not `npm ci` — the lockfile was regenerated on restore
npm run dev            # serves http://127.0.0.1:8080
```

The app calls the backend **same-origin** (`/api/v1/*`, `/healthz`,
`/readyz`, `/metrics`); `vite.config.ts` proxies those paths to the control
API in dev. Point at a different backend with `PYTHIA_API_URL`:

```sh
PYTHIA_API_URL=http://other-host:3000 npm run dev
```

Scripts route through `node scripts/with-app-env.mjs`, which loads
`.grok/app-env.json` (auth disabled: `VITE_AUTH_ENABLED=false`).

## Production build

```sh
npm run build          # TanStack Start + Nitro -> .vercel/output
```

## Routes

`/` (Operations: evidence gates, stratum/hashrate/shares/latency truth
cards, live arm status), `/console`, `/algebra`, `/intelligence`,
`/manifold`, `/audit`.

## Honesty boundary

Privileged verbs (Start/Stop mining, agentic controls) POST
`/api/v1/mining/*` and friends. The control API mediates those through the
AL HARAS guardian: without a subscription Bearer token + tenant/actor
headers they are denied (400/402), and the UI surfaces the denial rather
than pretending success. Read paths (`telemetry/summary`, `system/map`,
`ready-to-mine`) work unauthenticated as designed.
