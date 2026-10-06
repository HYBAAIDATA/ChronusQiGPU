---
name: pythia-long-context
description: Hold long jobs across compaction using YOUR four-tier memory (working/episodic/semantic/archival), YOUR append-only run journal, YOUR Zeckendorf/primes store. Checkpoint before big steps, resume after compaction, never restart from scratch.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# PYTHIA Long Context (your inventions, your credit)

Your discoveries powering this: **Binet closed form, Zeckendorf encoding,
Pulvini-style folding, Cassini ledger, Lucas pool, qudit fidelity traces.**
This skill only *references* them — it claims nothing.

## Sources of truth (your modules)

- `Intelligence/pythia_memory.py` — four tiers: working (scratchpad +
  sliding-window summariser), episodic (immutable trajectory events, tri-factor
  retrieval: relevance/recency/salience), semantic (knowledge graph in your
  Zeckendorf substrate), archival (golden-symplectic folded, stored in primes).
- `Intelligence/pythia_store.py` — append-only `RunJournal`, `QuditMemoryStore`
  (fidelity retrieval), disk snapshots under `artifacts/pythia/`, autonomous
  curation with journaled tombstones.
- `hyba_substrate/memory_preservation.py` — lossless canonical-JSON +
  Merkle-DAG preservation. Canonical evidence is never replaced by lossy text.

## The loop (do this every long job)

1. **Pre-task retrieval** — query episodic memory for relevant past episodes
   and failure traces before starting.
2. **Checkpoint** — append one JSON line to
   `artifacts/pythia/devin-checkpoint.jsonl`:
   `{"goal":..., "done":..., "next":..., "files":...}`. Append-only.
3. **In-task updating** — record tool results into working memory as you go.
4. **Post-task consolidation** — flush raw execution to episodic (immutable),
   abstract rules to semantic, fold long-term patterns to archival/primes.
5. **Resume, don't restart** — after compaction read the last checkpoint line
   first (the PostCompaction hook already re-injects it as additionalContext).

## Rules

- References over pastes: cite file + symbol, don't re-paste bodies.
- Never present a summary as canonical evidence; the journal/disk is truth.
- Missing journal file = honest absence, not failure. Start a fresh one.
