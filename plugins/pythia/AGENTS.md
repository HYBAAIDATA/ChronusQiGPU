# PYTHIA — always-on operating rule (cloud, CLI, Desktop)

You are working in the private repository-local PYTHIA Devin plugin. Hold the
assigned job to completion and preserve the repository's canonical authority
boundaries.

## What this plugin does — and does not do

The plugin automatically provides checkpoint/resume instructions, lifecycle
hooks where Devin supports them, completion discipline, and runtime provenance
for the plugin revision in use.

The plugin does **not** claim that merely loading it automatically executes the
full PYTHIA four-tier memory stack. When a task requires working/episodic/
semantic/archival memory, call the repository's real PYTHIA memory interfaces
explicitly and retain evidence of those calls. A checkpoint summary is not a
substitute for canonical evidence.

## Long context (checkpoint + resume, every surface)

1. **Run plugin status first.** Invoke `/pythia:pythia-plugin-status` and
   retain the reported plugin version and source SHA.
2. **Checkpoint before every big step.** Append one JSON line to
   `artifacts/pythia/devin-checkpoint.jsonl`. The minimum shape is:

   ```json
   {
     "goal": "...",
     "done": "...",
     "next": "...",
     "files": ["..."],
     "plugin_source_sha": "...",
     "skills_invoked": ["pythia-long-context"],
     "verification": ["pending"]
   }
   ```

   Append-only — never rewrite history.
3. **Resume, don't restart.** After compaction or a new turn, read the last
   checkpoint line first, then continue. SessionStart/PostCompaction hooks
   re-inject the latest checkpoint where supported; otherwise the manual read
   is mandatory.
4. **Prefer references over pastes.** Canonical evidence stays in repository
   files, tests, journals and custody records. Never replace evidence with a
   lossy summary.

## Finish jobs (no stranded work)

1. **Evidence before claims** — run the verification command fresh in this
   session before claiming pass/complete.
2. **Root cause first** — reproduce and trace before fixing.
3. **Red-green** — failing test first for every code fix where applicable.
4. **Record skill use** — the skills themselves record invocation into the
   local plugin runtime receipt.
5. **Stop rule** — do not end while `next` is unfinished. The Stop hook is
   fail-closed: a missing/malformed checkpoint, missing plugin provenance, or
   missing verification evidence blocks completion. Finish the work or record
   `next: "blocked: <reason>"`.

## Canonical subsystem boundaries

Do not reinterpret these while performing a task:

- **EUCLID** — intelligence orchestration.
- **PYTHIA** — predictive/causal intelligence, mining intelligence and final
  mining SearchPlan. PYTHIA is **not a HYBA product**.
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
- Existing PrimeDB/SQLite/snapshots/journals are producers, adapters, caches or
  legacy surfaces according to the canonical storage registry. Do not promote
  one into global authority without explicit owner approval.

## Mining doctrine

PYTHIA mining is canonical structured search with complete nonce-estate
coverage and Hendrix as the default production traversal. Do not replace it
with blind/flat search, transfer final SearchPlan authority, or weaken the
independent SHA256d/target proof boundary without explicit owner approval.
