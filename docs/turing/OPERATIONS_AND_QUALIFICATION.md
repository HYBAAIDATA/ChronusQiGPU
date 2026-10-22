# TURING operations and qualification

## Current reconciliation

Current acceptance is tracked in `ACCEPTANCE_REGISTER.md` and its machine-readable
`requirements-evidence.json`. The previously stated draft PR stack is closed:
#96/#97/#99 merged; #98 closed unmerged. Main now contains the separate enterprise
service. Do not treat the historical native pilot's process-local persistence
limits as an assessment of that service's SQLite/custody implementation.

The service runbook is `../../services/turing-enterprise/deploy/OPERATIONS.md`.
Its current non-financial production gates remain fail-closed. Hermitten is not
a dependency, and future contractual usage-based billing is deferred. Actual
SSO, installed canonical execution/custody, container isolation, target-host
load/backup+custody recovery/rollback, CI and manual accessibility acceptance
remain distinct from local fixture/unit evidence.

Fresh service local qualification: 93 passed, zero failed/skipped, one
Starlette/httpx deprecation warning; separate installed-wheel tests also passed
93. The non-skipping actual installed-runtime test FAILED for missing
`hyba-turing-vqc` distribution metadata; it was not skipped or replaced by a
fixture. Isolated actual-source stabilizer tests passed 11; research gates passed
11 plus 4 subtests. Those do not establish whole-package or hardware correctness.
New browser fixture checks cover 12 interaction groups and 2 automated axe scans
with zero violations; manual accessibility remains unexecuted.

## Historical native evaluation report — NOT fresh qualification

The remainder preserves the earlier pilot report and its historical counts and
architecture. Its statements about draft dependencies and missing enterprise
implementations are superseded by the current register above. None of its old
passes is counted as a fresh result for the present candidate.

# Evaluation operations and qualification

## Scope correction — billing deferred

The user's clarification supersedes the original billing requirements: the
intended model is **usage-based**, billing is **on hold**, and **Hermitten is not
an integration dependency**. Do not implement Hermitten, pricing/rating, invoicing,
payments or financial reconciliation in the current scope. Do not request
Hermitten access or hold non-billing implementation/acceptance on it. Keep
execution/usage evidence distinct from charges; any future billing work needs a
separate authorised scope. Operational usage accounting must not invent a
measurement unit or financial event. Identity, authorisation, provisioning,
execution, evidence and recovery work remain in scope.

## Environment and rollout (not executed)

Use the existing Python control API and Vite static build; do not add another
server/database or rewrite to Next merely for branding. PR98 depends on PR96's
TURING package organisation. Maintainers must review that dependency first.
The pilot is disabled by default. An authorised non-production operator may
set `TURING_WORKSPACE_PILOT_ENABLED=1` only after configuring the legitimate
AL HARAS authority, dependency/evidence availability, TLS, secrets and audit.
Never add a token bypass, fabricate a subscription or publish privileged tokens.

Qualify one approved process before pilot access. Memory-local jobs and keys do
not support transparent restart or replicas. Shared durable enterprise backend,
custody, deduplication and recovery qualification are separate gates. Registry
limits256global/32peridentity retain completed jobs as well, with no silent
history eviction; exhaustion429 is not a billing event or auto-scaling trigger.

## Local engineering evidence

- Python: 33 tests run, 32 passed, 1 opt-in real-native smoke skipped.
- Frontend: 53 client/history/route/unavailable-boundary tests passed in isolated Vitest.
- Strict TURING TypeScript check passed with isolated TypeScript5.9.3/React19 declarations.
- Standalone TURING React/CSS bundle compiled with sandbox esbuild, NOT the full locked Vite build.
- Chromium UI transport fixtures: 24 automated axe/overflow scans and 12 workflow groups passed, no runtime page errors. Public pages at1440/390px and key workspace states individually visually inspected.
- Fixtures explicitly identify browser-only evidence; placeholder hashes/reports are NEVER native execution, authentication, custody or commercial acceptance.

All counts describe local targeted runs, not remote CI. The isolated validation
toolchain is not a product dependency audit: its npm audit reported findings
associated with stale/symlink lock entries even after the installed test runner
was upgraded. Do not call it a clean audit. Run the repository's locked scans in
a clean environment and triage their real output before release.

Not qualified: live native computation/AL HARAS/evidence provider, full host
regression, locked frontend build/lint/audit, remote checks, distributed or
enterprise persistence, operational usage integrity (financial billing deferred), load/soak/penetration tests,
manual assistive technology and complete WCAG conformance. The GitHub token
could not read check runs (403); this is not evidence of passing or failing CI.
The targeted GitHub secret-scanning tool was unavailable because Advanced
Security is not enabled for this repository; no successful GitHub secret scan
is claimed. Repository-approved secret scanning remains a release gate.

## Reproduce targeted and locked checks

```bash
python -m unittest discover -s tests -p test_turing_workspace_pilot.py -v
npm --prefix frontend ci
npm --prefix frontend run lint
(cd frontend && npx --no-install tsc --noEmit -p tsconfig.turing.json)
npm --prefix frontend run test:ts -- src/turing/
npm --prefix frontend run build
TURING_RUN_ENGINE_SMOKE=1 turing_universal_quantum_computer/.venv/bin/python \
  -m unittest discover -s tests -p test_turing_workspace_pilot.py -v
```

`.github/workflows/turing-workspace-pilot.yml` requests the locked TURING Python
environment, opt-in smoke and frontend checks. Inspect actual run results and
existing repository security workflows; merely committing workflow YAML proves
nothing about success. Dependency access/download failures must not be bypassed.

Optional local browser QA: compile the TURING entry in an isolated toolchain,
serve with SPA fallback, and run `scripts/turing_browser_qa.cjs` with
`TURING_PREVIEW_URL`, `TURING_QA_OUTPUT` and optional `CHROMIUM_PATH`. Requires
Playwright and @axe-core/playwright installed outside production dependencies.
It intercepts API traffic with explicitly labelled fixtures and tests review,
invalid input, unknown acknowledgement, expired access, same-identity/key retry,
queued/running cancellation, unchanged report download, history search/paging,
local enquiry export, disconnect and no browser credential storage/mining calls.
It is NOT a substitute for the actual guarded HTTP/native integration.

## Monitoring and incident handling

Deployment operator must supply health/dependency readiness, guardian audit
write failures, denial classes, request/error/latency counts, process restarts,
registry occupancy, queue/running age and resource pressure. Keep secrets/raw
inputs/reports out of logs. No metrics collector or incident endpoint is invented.
Owner-approved thresholds, paging and access/retention policy are required.
Service telemetry does not determine billable quantities. Future outbox lag,
dead-letter volume, ingestion and reconciliation exceptions belong to the actual
operational metering owner; financial reconciliation remains deferred. Record incident correlation, impact, mitigation, audit
refs and reconciliation outcome; approved external status channel required.

## Recovery / customer communication

- **Lost acknowledgement:** retain exact program and request key. Retry only that request, same identity, while original process continuity is confirmed.
- **401/403:** clear access, reconnect with legitimate renewed credentials and same tenant/actor to recover retained context. Do not change the key or interpret denial as proof prior execution failed.
- **404:** job may be foreign, lost on restart or unknown. Do not disclose foreign job existence or manufacture a result.
- **409:** key reused with changed content; stop and investigate. Never silently replace the original computation.
- **429:** bounded retained-job capacity exhausted; operator reviews active work and recovery implications. No silent evictions or blind restart.
- **503/dependency failure:** fail closed; check enabled flag, authority/evidence dependencies and approved environment. No auth bypass.
- **Cancellation:** confirm; queued cancellation can succeed; running native work may finish. Display backend state and accepted flag, not optimistic cancellation.
- **Restart:** announce potential loss of history/dedupe and reconcile acknowledged/uncertain work with operator records BEFORE any resubmission. There is no durable restore promise in this pilot.
- **Disconnect:** clears in-memory credentials and displayed results, not server jobs, audit or customer service. Not data deletion or termination.
- **Export exposure:** local report may contain confidential content; use approved storage/retention and incident process, never paste credentials into tickets.

Rollback: disable the pilot flag, withdraw evaluation access, account for live
native work and preserve required operator audit, then revert the PR if needed.
Do not tear down unrelated mining/operator routes. Restart alone is not safe
rollback or data deletion. No production setting was changed by this work.

## Security acceptance matrix

| Threat | Current mitigation / local evidence | Required release proof |
| --- | --- | --- |
| Cross-tenant/actor access | Server owner scope; foreign404; list exposes no input/report/key; unit tests | Actual guardian identities, forged headers, direct HTTP and audit evidence |
| Compromised account/token | Memory-only, same origin, redirect rejection, no cookie credentials | Credential issue/expire/revoke; host CSP/XSS review; IdP MFA/session/offboarding |
| Operator abuse | No new privileged admin/impersonation endpoint | Scoped/time-bound approved grants, least privilege and audited revocation |
| Injection/secret leakage | Strict schema/bounds, escaped text rendering; workspace guardian exception sanitisation | Full host log/error review, CSP, secret/dependency scanning and supply-chain qualification |
| CSRF | Explicit bearer/custom JSON headers, cookies omitted, no CORS broadening | Origin/deployment review; explicit CSRF controls if later switching to cookie sessions |
| Denial of service | Admission and retained-job bounds only | Approved edge rate limits, process resource/timeout policy and abuse/load tests |
| Manipulated usage / duplicate charge | No browser meter/charge endpoint shipped | Trusted immutable operational facts and idempotent ingestion; financial charging/reconciliation deferred |
| Unauthorised allocation | No allocation endpoint fabricated | Capacity authority verifies role, effective contract, inventory/version, policy and approval |
| Retention/backup/residency | Missing guarantees stated, guardian custody separate from UI | Approved data map, store bindings, recovery exercise, deletion/legal-hold and export policies |

Release signoffs are role-owned: TURING maintainer (native/API), identity/security
owner (auth/isolation/audit), capacity/commercial owners (provisioning/contract),
meter owner (operational usage integrity; billing deferred), service operator (deploy/recovery),
legal/product (terms/data/claims), plus explicit user authorisation for deployment.
