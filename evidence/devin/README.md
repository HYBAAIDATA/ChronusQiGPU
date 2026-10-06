# Devin Engineering Intelligence Evidence

This directory stores **published, content-addressed task evidence packs** from
the private PYTHIA Devin plugin.

## What one evidence pack proves

A valid pack can prove that, for the recorded task:

- a specific plugin source SHA was observed;
- named plugin skills were runtime-observed;
- the append-only engineering event ledger verified;
- one or more proving commands ran and their exit codes/output digests were
  recorded;
- a completion decision was recorded;
- the pack itself has not changed since sealing;
- if committed, Git history binds the pack to repository history.

It does **not** prove that the plugin caused better engineering performance.

## Evidence states

Use these terms precisely:

1. `PLUGIN_CONFIGURED` — repository declares the plugin.
2. `PLUGIN_RUNTIME_OBSERVED` — runtime hook/status receipt executed.
3. `SKILL_RUNTIME_OBSERVED` — skill invocation recorded.
4. `VERIFICATION_OBSERVED` — proving command outcome recorded.
5. `TASK_OUTCOME_VERIFIED` — completion gate plus sealed pack pass.
6. `UPLIFT_OBSERVED` — comparable baseline and augmented cohorts show a
   better measured outcome.
7. `CAUSAL_EFFECT_ESTABLISHED` — reserved for a controlled design strong
   enough to support causality.

## Evaluating whether the augmentation helps

Use comparable tasks and the same acceptance criteria. Prefer prospective
paired or matched task sets over anecdotes.

Useful outcome measures:

- first review pass versus changes requested;
- escaped defects found after completion;
- regressions introduced;
- authority/boundary drift findings;
- unsupported evidence claims;
- verification failures before final pass;
- reopen/rework rate;
- post-merge verification success;
- percentage of tasks with complete evidence packs.

Do not optimize for lines changed, endpoint count, token count, or self-reported
confidence.

Aggregate published packs with:

```text
python plugins/pythia/scripts/evaluate_augmentation.py evidence/devin
```

The evaluator reports observed outcomes only and preserves the causal claim
boundary.
