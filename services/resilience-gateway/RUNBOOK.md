# Resilience and Sovereign Operations Runbook

## Signals

- `http_errors_total`, route latency quantiles, circuit state events
- `ws_stale`, `ws_backpressure_total`
- shutdowns missing `shutdown_complete` after 35 seconds
- CQRS hash-chain or actor-signature verification failure
- billing records without `OUTCOME_VERIFIED` evidence
- shadow egress denial and strategic-asset authorization denial
- A/B/C/E output drift above the tenant SLA

## Dependency circuit open

1. Confirm the upstream incident and the affected dependency.
2. Verify responses declare `degraded`, `source`, and `reason`.
3. Do not force-close the breaker. Confirm half-open probes recover naturally.
4. If the cache has expired, expect an explicit unavailable result.

## WebSocket thundering herd

1. Verify close codes and heartbeat traffic.
2. Confirm clients use capped exponential backoff with jitter.
3. Rate-limit upgrades at the load balancer if connection pressure threatens
   healthy traffic.

## Provenance failure

1. Freeze the affected tenant's command intake.
2. Preserve the event journal and database WAL.
3. Verify the stream from genesis and locate the first invalid sequence.
4. Validate actor key rotation records and signature encoding.
5. Never rewrite history. Restore projections from the last valid sequence and
   append a signed remediation event.

## Billing boundary breach

1. Stop the isolated billing projector, not the execution plane.
2. Quarantine ledger entries lacking a valid outcome event hash.
3. Rebuild the ledger from the verified event journal.
4. Confirm physical and theoretical metrics remain non-billable.

## Shadow-tenant egress

1. Treat any successful external write as a severity-one isolation breach.
2. Revoke the shadow workload identity and apply deny-all egress.
3. Compare source and shadow journals for production pollution.
4. Resume only after network policy and application-level severance tests pass.

## Strategic asset leak

1. Revoke the affected artifact and CDN cache immediately.
2. Rotate artifact-signing and clearance keys.
3. Diff standard and strategic manifests to identify the leaked chunks.
4. Rebuild in separate CI identities; do not rely on SPA route guards.

## Governance rollback

If drift, latency, maintainability, or sample floors fail, authorization remains
false. Keep arm A active, quarantine candidate artifacts, and retain experiment
evidence for audit. No manual optimization override is permitted without a new
signed client tolerance.