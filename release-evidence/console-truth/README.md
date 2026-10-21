# Console truth/journeys candidate evidence

Production/publication HOLD. These tests qualify the scoped candidate only. No merge/tag/deploy or manual paid CI run.

## Source identity

Base main: `4f71b5647e5cacd053e9a9d545ab5f26d38b4f34`. Branch: `fix/console-truth-journeys-20261020`. This is a genuine GitHub-MCP pinned partial source export, not an authenticated full checkout. Baseline blobs were byte/Git-blob checked; BASELINE_FETCH_MANIFEST records those identities. SOURCE_MANIFEST records candidate files. The commit containing this pack binds the candidate files and logs; a commit cannot embed its own SHA. Package manifests/lockfile were not changed. No clean git status or full source_identity(ROOT) is claimed. PR #128's unmerged mining fixes are not in this separate branch.

## Final local checks

| Check | Outcome | Evidence |
|---|---|---|
| TypeScript `tsc --noEmit` | PASS | release2-tsc.log (empty on success) |
| Vitest | 129 passed / 16 files | release2-vitest.log |
| Vite production build | PASS | release2-build.log |
| Isolated Python current-source contract/auth suite | 14 passed | release2-python-contract.log |
| Local browser matrix | 16 route/state captures at 1440/390px; no recorded overflow or page errors | ui-results.json; screenshot manifest |
| Expanded session/subscription/audit documents | 2 captures, no overflow | release-expanded-capture.log / screenshot manifest |
| Independent DOM render helper | 1 denied-state image inspected | screenshot manifest |

Frontend tests cover server-role gating, poll suppression for operator, role revocation, status 401/403/500/503, transport failure, hung-request abort, signout and late response suppression; no-mock import-graph checks; Python/TS envelope fixture binding; missing-data/zero preservation; Stratum current-vs-historical acceptance; separate CEO and guardian credentials; noninteractive denied polling. This is not full deployment or hardware proof.

`npm ci --ignore-scripts --no-audit --no-fund` succeeded with engine warnings. Actual Node is 24.14.1, package pins 24.21.0 (some dependencies require >=24.15); exact supported-engine qualification remains PENDING. No dependency lock was rewritten. Earlier failed development attempts are retained in the downloadable evidence archive, not erased or counted as final passes.

A second frozen-source rerun also passed (frozen-*.log); SHA-256 comparison after the rerun found zero changed files in SOURCE_MANIFEST. See FROZEN_RERUN.json. No production readiness is inferred.

## Reproduce from repo root

```sh
python -m pip install -r frontend/requirements-contract.txt
PYTHONPATH=frontend/scripts python -m pytest frontend/scripts/test_console_contract.py -q -p no:cacheprovider --basetemp=/tmp/hyba-console-contract-UNIQUE
cd frontend
npm ci --ignore-scripts --no-audit --no-fund
./node_modules/.bin/tsc --noEmit
npm run test:ts
npm run build
cd ..
PYTHONPATH=frontend/scripts python frontend/scripts/serve_console_fixture.py
```

The last command is a loopback-only UI TEST HARNESS at 127.0.0.1:8765, not the production backend. It extracts actual current route/session/status functions and injects deterministic owner fixtures. Guardian is deliberately unavailable; no receipt is fabricated. Screenshots carry a visible fixture warning. The archive includes the executed browser capture scripts and environment-specific reproduction paths. Killing this harness proves UI handling of a dead test transport, not a live Stratum failover drill.

## Required before review/merge or promotion

1. Full canonical Python service/caller regression with the new exact CEO-only read policy; deployed identity/proxy/CORS and separate subscription auth. No claim of complete read-surface security coverage.
2. Nested owner schemas and malformed-owner fuzz/compatibility qualification; this pack validates the envelope, not every Pydantic field. The canonical API is dict-producing, not a Pydantic server. The Pydantic model here is audit-only.
3. Backend tenant-scoped audit-export contract + isolation proof. Do not substitute global audit tail.
4. Producer-published qualified five-field receipts and per-number digest/evidence-class coverage. Renderer support is not producer qualification.
5. Server analyst/auditor roles and non-mining operator enterprise endpoints. Current console remains CEO-only and shows others a restriction, not a fake role journey.
6. Live share-submit/pool acknowledgement, device-bound execution, all outstanding product/runtime/legal/ops gates and owner signatures. No product production_ready flag changed.
7. Exact Node 24.21 supported-engine rerun and full deployed frontend/backend integration.

See frontend/JOURNEYS.md and frontend/WIRING.md for implemented vs unavailable paths. No frontend-computed truth, no new mining actuator, no consent/security bypass, no production promotion from these tests.
