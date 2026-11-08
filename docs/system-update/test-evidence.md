# Test evidence and limitations

## Status of this document

This is a correction to historical test and release statements. On 2026-11-08, the repository was reviewed statically at commit `a2768d11847de113d26535e33cfe9d4a79a009db`. **No tests, CI runs, frontend build, hardware tests, deployment tests, or security conformance tests were run as part of that review.**

## What can be said

- Test files and a CI workflow configuration exist in the repository.
- Their existence does not establish that a current run passed, that every test is meaningful, or that a release is qualified.
- Previously published totals (including 120/120, 242/242, 88 invariants, and 10/10 CI) have not been independently verified against the current commit and are withdrawn as current evidence.
- Historical reports that say “passed,” “qualified,” or “production-ready” are not current attestations. See [historical report status](../reports/README.md) and the [claim audit](../claim-audit.md).

## How to publish valid test evidence

For each result, preserve the exact commit SHA, environment/runtime and dependency versions, command or workflow URL, start/end time, exit status, raw logs, skipped/xfail tests, and reviewer. Keep unit, integration, security, performance, hardware, and deployment results separate. Do not turn a test count into a security, compliance, or production claim.

A future run can start with:

```bash
python -m pytest -q
```

That command has **not** been run for this update. A passing local run alone would not qualify a release. Frontend build and API integration need separate verification; physical accelerator claims require actual device runs and reproducible benchmark artifacts.