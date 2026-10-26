# Nine-Agent Operating Model

The governance pipeline that wraps the substrate. Ten agents in three
layers; code is hypothesis, CI and the substrate are evidence.

## Layers

| Layer | Agents | Write access |
|-------|--------|--------------|
| TRUTH | auditor(1), math_verifier(6), security_verifier(7), quantum_checker(8), precision_sentinel(9), pin_verifier(10) | none — read-only |
| CHANGE | remediator(2), test_engineer(3) | draft bundles only; remediator capped at 4 files / 128 KiB / cyclomatic 10 / fanout 3; test_engineer writes tests/ only |
| CONTROL | governance(4), provenance(5) | verdict only / `docs/provenance/<sha>.json` only |

No agent approves. No agent merges. `may_approve`/`may_merge` return
False for every id.

## Ordered gates (`hyba/operating_model/`)

1. `freeze_substrate()` — verifies M15 = ((219,98),(98,121)) in
   GL(2, Z/256Z): both-order inverse ≡ I, det ≡ −1, bit-exact
   fold/unfold round-trip over 8192 deterministic vectors (all byte
   values, lengths 0..511), Cassini for the golden generator, no floats
   in the fold path. Writes `docs/substrate_freeze.json`.
2. `require_lemma()` — `docs/lemma_lucas_polynomial.md` (≤200 lines)
   must state tr(Qⁿ)=Lₙ and carry reviewer signoff lines; writes
   `docs/lemma_signoff.json`. `theorem_proven` stays pinned False.
3. `write_failure_modes()` — 10 named failure modes, each with a real
   test in `tests/test_operating_model.py` and a TRUTH-agent owner;
   writes `docs/failure_modes.json`.
4. `.github/agents/*.agent.md` — ten profiles, isolated vocabularies.
5. `run_pipeline()` — preconditions → auditor traces declared claims →
   truth agents in parallel → governance verdict
   (PASS / FAIL / NOT_PROVABLE + reason) → provenance.
6. `live_run()` — 8 cycles × {happy, adversarial}; five real injections
   (impossible target, two-consecutive-block demand, fabricated ladder
   rung, plateaued surrogate, folded-ratio check). Transcripts:
   `experiments/live_mining_run_results_{happy,adversarial}.json`.
7. Full test battery green.
8. This document.
9. Provenance is replayable: same seed + agent version shas +
   freeze/lemma shas → byte-identical record.

## Honesty invariants

Every cycle asserts `theorem_proven == False`,
`raw_buffer_materialized == False`, `surrogate_trustworthy == False`,
`lucas_scale ∈ {12,15,18,20}`. Winners are re-verified with hashlib —
the search's own claim is never trusted.
