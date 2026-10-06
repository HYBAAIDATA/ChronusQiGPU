---
description: Mandatory EUCLID aptitude bootstrap. SessionStart invokes the complete plugin and Intelligence skill libraries before Devin works.
trigger: always_on
---

# Mandatory Session Bootstrap

No task work begins before SessionStart has completed.

SessionStart must:

1. identify the exact plugin/aptitude source SHA;
2. enumerate every `plugins/pythia/skills/*/SKILL.md`;
3. enumerate every `Intelligence/skills/*/SKILL.md`;
4. mark the complete set invoked;
5. write the runtime receipt;
6. inject the active Euclidean aptitude instructions into context;
7. restore the latest continuity checkpoint if present.

If mandatory invocation is incomplete, block the session rather than silently
continuing with reduced aptitude.

## Skills are not task-scoped

Do not ask whether a task "needs" a skill before loading it.

All skills are active from SessionStart.

Relevance determines which instructions/actions are applied during the work,
not whether the aptitude exists.

## Task evidence is separate

When a concrete assignment begins, establish its task identity and record its
engineering evidence. That task ledger proves the work performed and observed
outcomes. It does not own or control the session's skills.

Before completion:

1. run proving commands through the engineering evidence recorder;
2. record a truthful completion decision;
3. seal/publish the task evidence pack where required;
4. append the final continuity checkpoint;
5. allow the Stop hook to verify both:
   - complete session-wide EUCLID aptitude activation; and
   - valid task outcome evidence.
