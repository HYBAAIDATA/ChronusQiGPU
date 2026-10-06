# PYTHIA — always-on operating rule (cloud, CLI, Desktop)

You are working with PYTHIA long-context memory. Hold the job to completion.

## Long context (checkpoint + resume, every surface)

1. **Checkpoint before every big step.** Append one JSON line to
   `artifacts/pythia/devin-checkpoint.jsonl`:
   `{"goal":..., "done":..., "next":..., "files":...}`. Append-only — never
   rewrite history.
2. **Resume, don't restart.** After compaction or a new turn, read the last
   checkpoint line FIRST, then continue. Hooks (SessionStart/PostCompaction)
   re-inject it as additionalContext where the surface supports hooks; where
   they don't, this manual read is mandatory.
3. **Prefer references over pastes.** Cite `Intelligence/pythia_memory.py`
   (four tiers: working/episodic/semantic/archival), `artifacts/pythia/`
   snapshots, `hyba_substrate/memory_preservation.py` (lossless, hash-chained).

## Finish jobs (no stranded work)

1. **Evidence before claims** — run the verification command fresh in THIS
   session before claiming pass/complete.
2. **Root cause first** — reproduce and trace before fixing.
3. **Red-green** — failing test first for every fix.
4. **Stop rule** — do not end while the checkpoint's `next` is unfinished
   (the Stop hook blocks where supported; elsewhere enforce via
   `/pythia:pythia-stop-check`). Finish it or record `next: blocked + reason`.

## HYBA products in the loop

- **PYTHIA** (this repo): operational mining. `chronus/mla1517/mining`,
  control plane `chronus/mla1517_platform/python`.
- **PRIME-DB** (`chronus/mla1517_platform/host/primedb_*`): native 64-byte
  state ingestion consumer. Distinct from mining.
- **HYBA services** (`hyba_services/`): object/policy/lineage/proof refs over
  `hyba_contracts`.
- **HYBA profiles** (`hyba_profiles/registry.py`): module map — resolve
  `dependency_closure()` before adding modules.
- **HYBA substrate memory** (`hyba_substrate/`): lossless canonical-JSON +
  Merkle DAG. Never substitute summary for canonical evidence.
