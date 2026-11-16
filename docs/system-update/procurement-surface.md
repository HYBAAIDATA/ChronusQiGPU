# Procurement surface (quote → reserve → admit)

## Problem

A quote alone is advisory. An SLA needs a binding, an expiry, and a refusal
when the actual run exceeds what was reserved.

## Routes

| Method | Path | Role |
|--------|------|------|
| GET | `/v1/capacity/pool` | Declared pool bytes, source, replenishment, committed |
| POST | `/v1/capacity/quote` | Advisory quote for size + tier |
| POST | `/v1/capacity/reserve` | Bind reservation (idempotent) |
| POST | `/v1/capacity/admit` | Admit actual size; record utilisation |

All fail closed. Refusal codes are stable and listed in the commercial
refusal schedule.

## Seal

`scripts/ci/check_openapi_seal.py` loads the **live** FastAPI OpenAPI document
(not a hand-kept `OPENAPI` map) and fails if a mechanism token appears in a
path, field name, or enum value. Capacity routes are extracted from that live
document on both `chronus.service.api.app` and the deploy `chronus.service.app`.
`scripts/ci/check_mechanism_seal.py` scans external surface prefixes.

Tier names (`TIER_GEOMETRIC` | `TIER_POLYNOMIAL` | `TIER_STATISTICAL` |
`TIER_SUSPENDED`) are the only permitted method vocabulary on the wire.
`GEOMETRIC` means "converges geometrically under our harness" — not a
decodable algorithm name. Mechanism tokens (`phi`, `pisot`,
`vijayaraghavan`, …) are banned from customer-visible surfaces.

## Binding rules

- Quote is advisory until `is_binding` and it matches live
  `contract_version` + `evidence_hash` (server rebuilds economics).
- Reservation: one quote, one size, one expiry, one tenant-scoped
  idempotency key (`DEFAULT_TTL_S` = 900s).
- Admission refuses overages beyond `ADMISSION_GRACE` (default 2% —
  measurement jitter; tighten to 1% when the harness is stable).
- Pool: `load_pool()` declares bytes, source, and replenishment
  (`GET /v1/capacity/pool`). Pilot constant is fine; hyperscalers get the
  declared source, not an inline magic number.
- Reconciliation: `admit` → utilisation ledger; quarterly
  `space_bytes × utilisation` vs client baseline (`no baseline, no fee`).

## Evidence

- Unit tests: `tests/test_procurement.py`, `tests/test_carmichael_address.py`
- Index microbench: `scripts/benchmarks/index_baseline.py` (claim HD-01)
- Claims sheet: `docs/claims/claims-hyba-data.yaml`
- Contracting: `docs/contracts/avoided-capex.md`
- Internal research reading (not a customer surface): `chronus.research.millennium_bridge`
  citing `chronus.math.unified_quantum_engine.GoldenArithmetic`

## Explicit non-claims

- Payload bytes are not reduced (HD-08 not claimed)
- No DRAM-savings SLA until HD-01/HD-04/HD-06 are run at hyperscaler scale
- Pool constant is a pilot declaration, not an autoscaler
