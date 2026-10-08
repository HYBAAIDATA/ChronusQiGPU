# PYTHIA Resilience Gateway

Production resilience and sovereign-control envelope for PYTHIA. It is isolated
under `services/resilience-gateway` so the existing Python mining control plane
and root container remain unchanged.

## Invariants

1. Every fallback is explicit, named, and observable.
2. Duplicate side effects are prevented by an atomic pending/done idempotency
   state machine.
3. Event-loop saturation removes the process from service.
4. Distributed trace context follows W3C `traceparent`.
5. HTTP `/api/*` requests and WebSockets are unauthorized until a valid,
   short-lived HMAC ticket is verified; HTTP additionally requires an
   `X-Tenant-Id` matching the signed ticket and scopes dependency paths under
   that tenant.
6. API request rates are bounded per signed tenant/subject identity. The
   in-process limiter is safe for a single replica; multi-replica production
   still requires the documented shared Redis ownership.
7. Database schemas remain compatible with application versions N and N-1
   through the expand-and-contract sequence in `SCHEMA-MIGRATIONS.md`.

## State topology

| Subsystem | State |
| --- | --- |
| Circuit breakers and WebSocket sessions | Per process |
| Retries | Per call |
| Idempotency keys and rate limits | Shared Redis adapter in production |
| Execution, provenance, and billing evidence | Durable append-only journal |
| Dependency health | Cached per process, aggregated through metrics |
| Shadow tenants | Isolated event stream with severed outbound writes |
| Feature flags | Shared configuration provider in production |

The included memory implementations are deterministic development adapters.
Production boot must inject real Firestore, Postgres, Redis, and event-journal
adapters; unconfigured dependencies fail readiness rather than pretending to be
healthy.

## Controls

- Circuit breaker with bounded half-open probes and explicit fallback results.
- Atomic idempotency ownership with `pending`, `done`, and expiry states.
- Event-loop p99 shedding at 500 ms on liveness and readiness.
- Retry with capped exponential backoff and non-negative jitter.
- Separate liveness/readiness endpoints and a 30-second graceful drain;
  readiness is false when the ticket secret is missing or too short.
- Fail-closed HTTP bearer authentication, signed tenant binding, path scoping,
  and per-identity rate limiting on `/api/*`.
- WebSocket heartbeat, backpressure, stale-session termination, and jittered
  client reconnection after a fail-closed ticket handshake.
- Structured logs, W3C trace propagation, and Prometheus text metrics.
- Deterministic feature rollout.
- Hash-chained CQRS events with Ed25519 actor-signature verification.
- Out-of-band outcome billing projection with strict physical, theoretical, and
  outcome metric boundaries.
- Shadow-tenant mirroring and exogenous shock injection with no production
  outbound write capability.
- Strategic-asset manifest segregation checks plus IP and clearance gates.
- A/B/C/E release governance using sample floors, output drift, latency
  regression, and maintainability thresholds.

## Verification

```bash
npm install
npm run check
```

## Production integration requirements

1. Replace the in-memory idempotency adapter with Redis using an atomic
   Lua script or transaction that claims `pending`, publishes `done`, and
   preserves ownership across all replicas.
2. Implement dependency adapters with bounded SDK timeouts.
3. Back `EventJournal.appendIfLatest` with a serializable Postgres transaction
   and a unique `(tenant_id, sequence)` constraint.
4. Run billing projection in a separate identity and process with read-only
   journal access and write-only ledger access.
5. Build standard and strategic frontend artifacts in separate CI jobs,
   accounts, buckets, and signing keys. Run `assertArtifactSegregation` on both
   manifests before promotion.
6. Run shadow tenants in separate namespaces and cloud accounts. Network policy
   must allow only the isolated shadow event sink and observability endpoints.
7. Never make theoretical metrics billable. Only signed
   `OUTCOME_VERIFIED` events can create charges.
8. Provision `WS_TICKET_SECRET` (minimum 32 bytes) through the workload
   secret manager and rotate it with an overlap window shorter than the ticket
   lifetime. HTTP callers must send `Authorization: Bearer <ticket>` and an
   `X-Tenant-Id` equal to the ticket's signed `tenantId`.
9. Back the HTTP rate limiter with the same shared Redis failure domain used
   for distributed idempotency before running more than one replica; the
   bundled limiter is deliberately process-local and cannot establish a
   cluster-wide quota.
10. Enforce the N/N-1 schema contract and expand-and-contract gates described in
   `SCHEMA-MIGRATIONS.md`.

## CQRS journal schema

```sql
CREATE TABLE command_events (
  tenant_id text NOT NULL,
  sequence bigint NOT NULL,
  event_id uuid NOT NULL UNIQUE,
  event_type text NOT NULL,
  causal_id text NOT NULL,
  actor_id text NOT NULL,
  actor_public_key_pem text NOT NULL,
  actor_signature_base64 text NOT NULL,
  occurred_at timestamptz NOT NULL,
  payload jsonb NOT NULL,
  previous_hash char(64) NOT NULL,
  event_hash char(64) NOT NULL UNIQUE,
  PRIMARY KEY (tenant_id, sequence)
);

REVOKE UPDATE, DELETE, TRUNCATE ON command_events FROM PUBLIC;
```

Database permissions are part of the security boundary: the application role
receives `INSERT` and `SELECT`, never mutation privileges.