# Migration closeout (2026-11-16)

Closing this repository for migration. Remaining polish lands in the new repo.

## Shipped on `cursor/carmichael-index-address-4a62` (#107)

- Sealed procurement: quote → reserve → admit (tenant-scoped, server-rebuilt quotes)
- Carmichael index addressing + HD-01 index baseline (honest probe accounting)
- Millennium bridge (internal): `chronus.research.millennium_bridge` cites
  `GoldenArithmetic` in `chronus.math.unified_quantum_engine` (outside purity gate)
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

## Qodo Fix PR #108 (evaluated, not blindly merged)

Automated remediation on `fix/remediation-9247aee8-17f447` (#108, closed for cherry-pick):

| Finding | Disposition |
|---------|-------------|
| Tenant scoping / cross-tenant admit | Already fixed on #107 (`tenant_id` required; scoped idempotency) |
| Server-side quote rebuild | Already fixed on #107 (`_server_quote`) |
| Persist ledger on compose volume | Cherry-picked: `CHRONUS_PROCUREMENT_LEDGER` in `docker-compose.yml` |
| Deploy app missing routes | Already fixed: `chronus.service.app` mounts `/v1/capacity/*` |
| OpenAPI seal only checks api.app | Fixed: seal script seals api OpenAPI + deploy `/v1/capacity/*` |
| Mechanism seal / full deploy scrub | Deferred — legacy AL HARAS/Euclid routes still carry tokens |
| Workload gate requiring reservation | Deferred to new repo (pilot surface is advisory→binding book only) |
| In-memory book lost on restart | Deferred (ledger durable on compose volume; book remains process-local) |

## Explicit non-claims

- The millennium bridge does not solve any Millennium problem; link labels are honest (PROVED / OPEN / ANALOGY / …).
- Procurement pool bytes are a pilot declaration, not an autoscaler or DRAM-savings SLA.
- Quantum / mining branding remains out of Chronus customer surfaces per AGENTS.md.
