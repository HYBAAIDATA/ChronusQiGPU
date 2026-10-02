# Zero-Downtime Schema Contract

Every deployed application version must remain compatible with the database
schema used by both version N and version N-1. Rolling deployment safety is an
application-and-schema invariant, not a Kubernetes feature.

## Prohibited in ordinary rollout migrations

- `DROP COLUMN`, `DROP TABLE`, or destructive type changes
- `RENAME COLUMN` or `RENAME TABLE`
- adding a non-null column without a safe default and bounded backfill
- changing enum values or constraints before every live reader accepts them
- deploying code that requires a migration which has not completed

Destructive contract migrations require evidence that no N-1 process, queued
job, rollback artifact, projection, or reporting consumer uses the old shape.

## Expand and contract sequence

1. **Expand:** add the new nullable column or table. Version N writes both old
   and new fields and continues reading the old field.
2. **Migrate:** backfill in bounded, resumable batches. Record progress and
   verify row counts and checksums without long table locks.
3. **Read switch:** deploy a version that still dual-writes but reads the new
   shape. Retain an instant read fallback.
4. **Stop old writes:** after N-1 has fully drained and rollback windows close,
   write only the new shape while retaining the old field.
5. **Contract:** only a later release may remove the old shape. Confirm
   telemetry shows zero old-field reads and writes before approval.

## CI/CD gates

- Run compatibility tests against both pre-expand and post-expand schemas.
- Test version N and N-1 binaries against the expanded schema.
- Reject destructive SQL unless a signed contract-phase manifest identifies
  the completed expand, backfill, read-switch, and drain evidence.
- Apply migrations before increasing new-version traffic.
- Keep contract migration rollback separate from application rollback.

## Event-store changes

CQRS event payloads are immutable. Never edit historical events in place.
Introduce a new event version and make projections understand both N and N-1
payloads. Rebuild projections from the journal to validate compatibility before
promotion.