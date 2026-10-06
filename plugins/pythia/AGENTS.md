# PYTHIA — Devin Engineering Intelligence v0.3

This private repo-local plugin augments Devin's coding workflow. It does not
change Devin's model weights and it does not make Devin PYTHIA. It supplies the
same classes of augmentation the Enterprise service layer was designed to add
around a narrow AI: semantic context, memory/continuity, quality gates,
governed agent work, evidence, promotion discipline, deployment awareness and
rollback.

## Always-on attributes

For every task:

1. Repository truth over documentation or reviewer assumption.
2. Explicit owner decisions outrank external interpretations.
3. Preserve canonical subsystem authority.
4. Root cause before repair.
5. Evidence before completion.
6. Unknown/unmeasured stays UNAVAILABLE.
7. No silent fallback or authority substitution.
8. Checkpoint before significant mutation.
9. Minimal change consistent with the architecture.
10. Inspect callers/consumers before changing interfaces.
11. Finish the assigned job or record the exact blocker.
12. Never promote SOURCE_PRESENT into runtime/device/live evidence.

## Enterprise-derived augmentation map

- **Flow** → structured task intake and bounded execution.
- **Ontology** → repository/subsystem/authority/dependency map.
- **Quality** → independent correctness, freshness, lineage and drift gates.
- **Agent fabric** → bounded parallel delegation with explicit ownership.
- **Evidence/proof** → recorded commands, outcomes and content-addressed packs.
- **Model promotion** → engineering promotion state machine.
- **Vault/deploy** → rollback target, clean build/install, post-change proof.
- **Observability** → runtime plugin/skill/task evidence.
- **Learning** → preserve verified successful/failing patterns without
  replacing canonical source evidence.

## Core session protocol

1. Invoke `/pythia:pythia-plugin-status`.
2. Establish a stable task id and use it throughout the session.
3. Invoke `/pythia:pythia-long-context`.
4. For architecture-sensitive work invoke `/pythia:pythia-repo-ontology`.
5. Choose specialist skills appropriate to the job.
6. Record verification using the engineering evidence recorder.
7. Invoke `/pythia:pythia-engineering-quality` before promotion.
8. Invoke `/pythia:pythia-promotion-gate` for review/release work.
9. Invoke `/pythia:pythia-evidence-pack`, seal the task evidence, then run
   `/pythia:pythia-finish-the-job` and `/pythia:pythia-stop-check`.

## Checkpoint contract

Append one JSON line to `artifacts/pythia/devin-checkpoint.jsonl`.

Minimum final shape:

```json
{
  "task_id": "stable-task-id",
  "goal": "...",
  "done": "...",
  "next": "done",
  "files": ["..."],
  "plugin_source_sha": "...",
  "skills_invoked": ["..."],
  "verification": ["fresh command -> observed result"],
  "evidence_pack": "evidence/devin/<task>/<sha256>.json"
}
```

Append-only. Never rewrite history.

## Specialist skill routing

- unfamiliar subsystem / authority-sensitive change:
  `/pythia:pythia-repo-ontology`
- defect or regression:
  `/pythia:pythia-systematic-debugging`
- behavior change:
  `/pythia:pythia-tdd`
- parallel agents:
  `/pythia:pythia-agent-fabric`
- pre-review quality:
  `/pythia:pythia-engineering-quality`
- release/promotion:
  `/pythia:pythia-promotion-gate`
- packaging/deployment:
  `/pythia:pythia-deploy-rollback`
- any completion claim:
  `/pythia:pythia-evidence-pack`

## Canonical subsystem boundaries

- **EUCLID** — intelligence orchestration.
- **PYTHIA** — predictive/causal intelligence, mining intelligence and final
  mining SearchPlan. PYTHIA is not a HYBA product.
- **TURING** — independent VQC.
- **KELLOGG** — tensor capability only.
- **CHRONUS** — heterogeneous execution; not CUDA/NVIDIA by definition.
- **THESEUS** — durable custody, integrity, continuity, records, recovery and
  provenance.
- **OVID** — representation/state transformation and transform lineage; not
  durable custody.
- **SALAMANDER** — bounded healing and optimisation.
- **AL HARAS** — security, identity, capability, authorisation and governance.
- **hyba_db** — tenant-scoped ontology/query/projection persistence; not a
  replacement for THESEUS.

Existing PrimeDB/SQLite/snapshots/journals remain classified persistence
surfaces. Do not promote one into global authority without explicit approval.

## Mining doctrine

PYTHIA mining is canonical structured search with complete nonce-estate
coverage and Hendrix as the default production traversal. Do not replace it
with blind/flat search, transfer final SearchPlan authority, or weaken the
independent SHA256d/target proof boundary without explicit owner approval.

## Evidence claim boundary

A sealed engineering pack proves that this plugin revision and recorded skills
were observed and that the recorded commands produced the recorded outcomes.
It does not, by itself, prove that the plugin caused Devin to perform better.

Causal uplift requires comparable baseline and augmented task cohorts using the
same acceptance criteria.
