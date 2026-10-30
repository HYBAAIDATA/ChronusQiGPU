# EUCLID — Kairos Local Transport Adapter

**HYBA | EUCLID**

<aside>

**Status: implemented and internally verified.** The Kairos Runtime now has a dependency-free local WSGI transport adapter. It provides an auditable REST-shaped research boundary while remaining fail-closed and explicitly non-public.

</aside>

## Implemented endpoints

- `POST /v1/kairos/sessions` — creates one operator session.
- `POST /v1/kairos/sessions/{id}/events` — dispatches a governed Kairos domain action.
- `GET /v1/kairos/health` — reports runtime health.
- `GET /v1/kairos/replay` — exports chronicle-backed replay data.
- `DELETE /v1/kairos/sessions/{id}` — closes the session.

## Enforced controls

- Strict endpoint and request-field validation.
- JSON-object-only requests with a bounded body size.
- Operator-only sessions, one active session, and no-store response policy.
- Fail-closed rejection for audience or creator execution, concurrent sessions, invalid actions, unsupported fields, inactive sessions, and unknown endpoints.

## Verification

- **40/40** focused core, closure, CNS, interactive, Kairos world, runtime, and transport tests passed.
- **14/14** production-harness checks passed.
- Compilation passed.

## Boundary

The adapter is local and transport-neutral. It does not start a network listener and does not claim TLS, external authentication, public API operation, WebSocket support, multi-user execution, distributed persistence, client UI, renderer integration, or production network assurance.

## Custody

- **Baseline snapshot:** `EUCLID_SHARED_REPOSITORY_SNAPSHOT_20260718_2158.zip`
- **Baseline commit:** `a81fcfb755fbe2ddba014258d24b2f864a523d72`
- **Transport bundle SHA-256:** `fbb14666f2cbf3cfca6458a25eeb2da4b3843ae19fbd120709bd8635a4f886fd`

[Kairos Local Transport Adapter evidence bundle](KAIROS_LOCAL_TRANSPORT.zip)

Kairos Local Transport Adapter evidence bundle