# Migration closeout (2026-11-16)

Closing this repository for migration. Remaining polish lands in the new repo.

## Shipped on `cursor/carmichael-index-address-4a62` (#107)

- Sealed procurement: quote → reserve → admit (tenant-scoped, server-rebuilt quotes)
- Carmichael index addressing + HD-01 index baseline (honest probe accounting)
- Millennium bridge (internal): `chronus.math.millennium_bridge` cites
  `GoldenArithmetic` in `chronus.math.unified_quantum_engine`
- Deploy app (`chronus.service.app`) mounts the same `/v1/capacity/*` routes

## Local verification (this closeout)

```text
pytest tests/test_millennium_bridge.py tests/test_procurement.py tests/test_carmichael_address.py
pytest tests/test_api_contract.py
PYTHONPATH=src python3 scripts/ci/check_openapi_seal.py
```

All of the above passed in the agent environment.

## Merge status (owner action required)

This agent cannot merge pull requests (`gh` is read-only; ManagePullRequest has no merge action). Open PRs marked MERGEABLE at closeout include, among others:

| PR | Branch | Notes |
|----|--------|-------|
| #107 | `cursor/carmichael-index-address-4a62` | Procurement + bridge (this work) |
| #104 → #102 | `order/seed-publish-followup` | Seed publish follow-up (stacked) |
| #102 | `cursor/tier-seal-qualification-4a62` | Tier seal |
| #99 | `cursor/stratum-smoke-endian-4a62` | Stratum smoke |
| #109, #105, #101, … | various | MERGEABLE; many have pre-existing red CI |

**Owner:** merge the intended stack in GitHub UI (or squash into the migration target), then continue cleanup in the new repository. Do not treat red CI on older branches as release evidence.

## Explicit non-claims

- The millennium bridge does not solve any Millennium problem; link labels are honest (PROVED / OPEN / ANALOGY / …).
- Procurement pool bytes are a pilot declaration, not an autoscaler or DRAM-savings SLA.
- Quantum / mining branding remains out of Chronus customer surfaces per AGENTS.md.
