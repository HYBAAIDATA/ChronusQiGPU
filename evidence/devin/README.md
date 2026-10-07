# Devin EUCLID Aptitude Evidence

The proof model separates **session augmentation** from **task outcome**.

## Session augmentation proof

SessionStart writes:

`artifacts/pythia/devin-plugin-runtime.json`

A valid receipt records:

- exact plugin/aptitude source SHA;
- plugin version;
- SHA-256 digest of the full active aptitude surface;
- `augmentation = EUCLID_APTITUDE`;
- complete plugin skill inventory;
- complete `Intelligence/skills` aptitude inventory;
- complete mandatory invocation set;
- `mandatory_skills_complete = true`;
- observed SessionStart/PostCompaction lifecycle events.

Skills are session-wide capabilities. They are not owned by individual tasks.

The evidence recorder fails closed before task verification or sealing unless
the current runtime receipt proves an observed `SessionStart`, a non-empty
mandatory skill inventory, and complete invocation of that inventory. Stop
re-validates the same set relationship and aptitude digest; an incomplete pack
cannot be used as a completion artifact.

Evidence state:

`EUCLID_APTITUDE_SESSION_OBSERVED`

## Task outcome proof

Task work is recorded independently in:

`artifacts/pythia/devin-engineering-evidence.jsonl`

Published content-addressed packs live under:

`evidence/devin/<task>/<sha256>.json`

A task pack can prove:

- task identity;
- exact workspace/plugin revisions;
- tamper-evident event-chain integrity;
- verification commands and exit status;
- output digests;
- completion decision;
- a snapshot showing mandatory EUCLID aptitude was active during that session.

Evidence state:

`TASK_OUTCOME_VERIFIED`

## Measuring whether it helps

Neither a session receipt nor one successful task proves causal improvement.

Use comparable tasks and identical acceptance criteria. Useful measures include:

- first-review pass rate;
- post-completion changes requested;
- escaped defects;
- regressions;
- authority/boundary drift findings;
- unsupported evidence claims;
- failed verification attempts before final pass;
- reopen/rework rate;
- post-merge verification success;
- long-session continuity failures;
- percentage of tasks with valid evidence packs.

Then distinguish:

```text
PLUGIN_CONFIGURED
→ EUCLID_APTITUDE_SESSION_OBSERVED
→ TASK_OUTCOME_VERIFIED
→ UPLIFT_OBSERVED
→ CAUSAL_EFFECT_ESTABLISHED
```

Aggregate published task packs with:

```text
python plugins/pythia/scripts/evaluate_augmentation.py evidence/devin
```

Do not infer causal uplift from ordinary PR success.
