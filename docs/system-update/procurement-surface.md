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
and fails if a mechanism token appears in a path, field name, or enum value.
`scripts/ci/check_mechanism_seal.py` scans external surface prefixes.

## Evidence

- Unit tests: `tests/test_procurement.py`, `tests/test_carmichael_address.py`
- Index microbench: `scripts/benchmarks/index_baseline.py` (claim HD-01)
- Claims sheet: `docs/claims/claims-hyba-data.yaml`
- Contracting: `docs/contracts/avoided-capex.md`
- Internal research reading (not a customer surface): `chronus.math.millennium_bridge`
  citing `chronus.math.unified_quantum_engine.GoldenArithmetic`

## Explicit non-claims

- Payload bytes are not reduced (HD-08 not claimed)
- No DRAM-savings SLA until HD-01/HD-04/HD-06 are run at hyperscaler scale
- Pool constant is a pilot declaration, not an autoscaler
