---
name: pythia-promotion-gate
description: Apply the Enterprise model-promotion concept to engineering changes. Do not allow PATCHED to become COMPLETE without progressively stronger evidence states.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# Engineering Promotion Gate

Record use first.

Use this state machine:

```text
DISCOVERED
→ UNDERSTOOD
→ PATCHED
→ LOCALLY_TESTED
→ E2E_VERIFIED
→ INSTALLED_ARTIFACT_VERIFIED
→ READY_FOR_REVIEW
→ MERGED
→ POST_MERGE_VERIFIED
```

Rules:

- No skipped state may be silently inferred.
- A state may be `UNAVAILABLE` when the environment cannot provide it.
- CI unavailable is neither PASS nor FAIL.
- Runtime/device/live-pool claims require their own evidence class.
- Promotion to READY_FOR_REVIEW requires a sealed engineering evidence pack.
- Promotion to POST_MERGE_VERIFIED requires verification against the merged SHA.

Record every promotion as event `PROMOTION` with from/to state and evidence.
