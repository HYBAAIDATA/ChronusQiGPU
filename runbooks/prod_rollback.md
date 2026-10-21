# Production rollback procedure — UNEXERCISED DRAFT

This is a review procedure, not an executed drill or a production-ready runbook. No backup, restore, rollback tag, failover or deployment was performed by this patch run.

1. Before writes, record the actual immutable release artifact/config/schema/key identities and last owner-approved rollback target. Keep the deployment HOLD until real owner sign-off. Never invent a rollback tag from a partial export.
2. Quiesce new admissions through the documented control plane; keep custody authority with Theseus and the versioned transform/materialisation boundary with Ovid. PULVINI remains folding. Do not replace the authority root with a derived query/index projection.
3. Take a snapshot-consistent backup with the real process-wide transaction mechanism. Record its committed generation, journal/seal boundary, manifest, encryption/key references and hashes. Do not copy live files and call that a consistent backup.
4. Restore into a private staging root. Validate tenant/path/envelope bindings, seals and provenance; refuse ambiguous or divergent generations. Rebuild query/index/lineage projections only from authoritative sealed custody records through supported facade contracts.
5. While writers are exercised, prove backup consistency, then exercise validated atomic activation with a single generation cutover. Inject failure before/after switch and show the old committed root remains recoverable. Do not activate a partially restored root.
6. Restore the exact approved artifact/config using reviewed schema compatibility and key policy. Prove data integrity, tenant isolation, auth-denial/read-only behavior, health/readiness separation and actual device reattachment. A restarted device label is UNBOUND until physically rebound.
7. Save commands, timestamps, before/after hashes, fault points, downtime/data-loss measurements, rollback outcome and named operator/security/custody sign-offs. Then and only then propose a real rollback tag and production review.

Blocked acceptance: no supported full-stack restore command has been source-qualified here; process-wide custody CAS, backup-during-write and atomic root switch are not proven by WAL-local tests. `trio_faultinjection.log` and rollback drill logs must come from actual full-stack execution, not this template.
