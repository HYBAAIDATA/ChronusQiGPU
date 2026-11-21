# Triad reconciliation generator

Produces `docs/production/TRIAD_RECONCILIATION.md` and `TRIAD_RECONCILIATION.json` from evidence that
was actually executed on a candidate SHA. Nothing is inferred from documentation.

1. `run_candidate.sh <sha>` runs the full pytest suite with junit output, `scripts/ci/triad_cross_checks.py`,
   the evidence gates, benchmarks on SHA-pinned public UCI data, and wheel/sdist builds with SHA256SUMS,
   all on a clean worktree of `<sha>`.
2. `build_cfg.py <sha> <run_dir> <outdir> <extra.json>` collects push-event CI runs whose head SHA is `<sha>`,
   with their jobs and runner labels.
3. `gen.py cfg.json` builds one row per requirement in `rows.py`. Each row has the 35 mandatory fields
   plus the evidence class.
4. `render.py cfg.json` writes the Markdown report and the JSON matrix.

Paths in these scripts point to the host where the run was made, so adjust them to reproduce elsewhere.
