# Avoided-capex clause (HYBA Data / Chronus)

Status: contracting template for pilot discussions. Not a signed MSA.
Not a claim of measured customer savings until a baseline exists.

## What we do not change (say first)

- Payload bytes
- Training
- Throughput at high batch

## What we remove (when measured)

- Resident index beside the record (address computed, not stored)
- Index rebuild after write
- Re-expansion of a lossless fold to reason over it

## Four required parts

1. **Declared baseline** — the client's own prior 90 days of accelerator-hours
   (or their chosen unit). Source and window must be named.
2. **Unit** — avoided accelerator-hours (or the client's equivalent).
3. **Symmetric quarterly true-up** — `space_bytes × utilisation` from the
   admission ledger against the baseline. Utilisation below 1.0 is a credit.
4. **`no baseline, no fee`** — without a declared baseline the fee line is
   inapplicable (`UtilisationLedger.quarterly_line`).

## Fifth part — refusal schedule

Every fail-closed `Refusal.code` from the procurement surface is listed as an
exclusion in the commercial schedule (see `docs/claims/claims-hyba-data.yaml`).
A documented refusal is never a later defect claim.

Current codes: `quote_not_binding`, `stale_envelope`, `version_mismatch`,
`evidence_mismatch`, `pool_exhausted`, `unknown_reservation`,
`already_consumed`, `expired`, `overage`, `invalid_quote`,
`idempotency_conflict`.

## Binding vs advisory

- A **quote** is advisory until `is_binding` is true and it matches the live
  `contract_version` and `evidence_hash` (server rebuilds economics).
- A **reservation** binds one quote, one size, one expiry, one tenant-scoped
  idempotency key.
- **Admission** refuses when actual size exceeds the reservation
  (`ADMISSION_GRACE` = 2% by default — absorbs measurement jitter; tighten
  to 1% when the harness is stable).

## Pool

`Book.pool_bytes` comes from `chronus.procurement.pool.load_pool()`:

- Pilot default: 64 GiB constant (`pilot_constant`)
- Override: `CHRONUS_PROCUREMENT_POOL_BYTES` (+ optional
  `CHRONUS_PROCUREMENT_POOL_SOURCE`)

Replenishment is operator-declared, not auto-scaled. Publish the source on
`GET /v1/capacity/pool`.

## Public vocabulary

Tier names (`TIER_GEOMETRIC` | `TIER_POLYNOMIAL` | `TIER_STATISTICAL` |
`TIER_SUSPENDED`) are the only permitted method vocabulary on the wire.
`GEOMETRIC` means "converges geometrically under our harness" — not a
decodable algorithm name. Mechanism tokens are banned from OpenAPI paths,
field names, and enum values.
