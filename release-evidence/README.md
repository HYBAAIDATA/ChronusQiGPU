# Release evidence

Executed registry receipts and publication records for the HYBA package
portfolio, consumed by `packaging/portfolio_release_audit.py`.

## What belongs here

Download the artifact sets a publication workflow emits after a real
dispatch and commit them here — one directory per product:

```text
release-evidence/
  hyba-kellogg-tensor/     *-smoke-*/receipt.json, *-final-publication/*.json
  hyba-turing-vqc/         …
  hyba-theseus-storage/    theseus-testpypi-smoke-*, theseus-pypi-smoke-*, …
  hyba-ovid-data-organisation/  …
  hyba-toe-intelligence/   …
  hyba-euclid-intelligence/     …
  hyba-pythia-consumer/    consumer-testpypi-smoke-*, consumer-pypi-smoke-*, …
```

Receipt schemas the audit recognises:

- `hyba.registry-execution.v1` — executed install/smoke on a named registry,
  bound to `source_commit`, per interpreter (`python` field), `status` and
  `checks` all true.
- Publication records — `published: true`, `testpypi_verified: true`,
  carrying the artifact digests and `ci_run_url` (the evidence-linked release
  record written by each workflow's `github-release` job).

## Rules

- Only executed evidence lands here. A scheduled or in-progress run produces
  nothing; a failed run's receipt lands with `status: "FAIL"` — do not
  discard it, the audit uses it to flag incidents.
- Receipts are immutable once committed. A re-run produces new files; never
  overwrite a receipt to change its verdict.
- The audit rejects receipts whose `source_commit` predates the audited RC
  (`--sha`), so only same-RC evidence advances a product's state.
