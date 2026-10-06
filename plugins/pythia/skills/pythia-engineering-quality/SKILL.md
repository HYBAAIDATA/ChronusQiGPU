---
name: pythia-engineering-quality
description: Apply the Enterprise quality-service pattern to engineering work: validate correctness, freshness, lineage, contract compatibility, drift, consumer impact, and verification before promotion.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# Engineering Quality

Record use first:

```text
python plugins/pythia/scripts/plugin_status.py --record-skill pythia-engineering-quality --write-receipt
```

Evaluate the change across independent channels. Do not collapse them into one
optimistic score.

- **Correctness** — does the implementation satisfy the requested behavior?
- **Tests** — did the relevant test fail before the fix where applicable, then pass?
- **Freshness** — was evidence produced against the current branch/SHA?
- **Lineage** — can the result be traced to inputs, changes, and exact commit?
- **Contract compatibility** — are callers/consumers still valid?
- **Authority drift** — did ownership or semantics move without approval?
- **Runtime truth** — source/test evidence must not be promoted to runtime evidence.
- **Deployment truth** — clean-installed artifact behavior is separate from checkout tests.

Unknown/unmeasured channels remain `UNAVAILABLE`, never zero or pass.

Before completion, record the quality result into the task evidence ledger with
event `QUALITY_GATE`.
