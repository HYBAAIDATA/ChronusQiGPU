# Production closeout: one integrated system on main

## Release target

Certify the complete integrated system, not a mining console or a set of isolated packages. `main` is the integration and certification branch. Every result binds to an exact source commit, source/artifact digests, commands, environment and evidence. A later source change requires affected tests to rerun. AI Studio is a separate deployment and is not changed by this closeout.

Do not rearrange more directories during qualification. Complete the in-progress migration first; reconcile with origin/main; repair imports, packaging, Docker paths and CI; leave a clean local checkout on main with HEAD equal to origin/main. Never discard another agent's work or bypass protected-branch requirements. The local checkout and migration have not been verified by this remote inspection.

## Architecture acceptance

TURING owns its quantum/operator authority; TOE provides its full inference/certification role, not just an invariant checklist. VQC and canonical TENSOR implementations execute the requested operators under CHRONUS dispatch. OVID supplies representation/addressability; THESEUS supplies accountable custody. Governance, economics, healing and verification preserve their declared authority and supply their own evidence. An aggregate status page cannot substitute for those integrations.

Native mathematical quantum execution is substrate-agnostic: no blanket physical GPU/QPU prerequisite and no emulation label inferred solely from software execution. A requested device-bound lane must report its actual binding or refusal. Real pool acceptance and financial settlement remain external outcomes, distinct from mathematical correctness. No fixed performance or universal speedup claim follows from the focused tests below.

## Journey register

These are acceptance requirements. SOURCE MAPPED is not a passing deployed journey.

| ID | User/workflow | Required execution and failure cases | Current closure evidence / open gate |
|---|---|---|---|
| J01 | Sign in, load workspace, sign out | Login -> Secure HttpOnly session -> server entitlement -> authorized data; invalid credentials, non-CEO denial, expiry/revocation, late responses, server identity change, subscription rebind | Client defect reproduced and fixed; 53 focused tests including rendered form/hook integration. Real Python service, TLS/CORS and browser deployment still require end-to-end execution. |
| J02 | Configure, authorize, execute, stop | Server-owned allowlists/caps; authorized native execution; approval checks; target auto-stop; cancellation/retry/restart; no client-generated actuator success | Console mutation paths mapped in frontend/WIRING.md; native-focused work merged in PR144. Complete service and deployment journey pending. |
| J03 | Quantum/tensor work to verified result | Authorized TURING/TOE/CHRONUS/VQC/TENSOR path with requested/executed route, exact or numeric scope, receipt binding, independent correctness, tenant boundaries and repeat safety | Existing native qualification is a subset, not full facade/operator/installed-package coverage. Full integration pending. |
| J04 | Ingest, address, retain, corrupt, recover | OVID lossless roundtrip; THESEUS durable custody; quarantine; quorum recovery; fresh-process restart; consistent data/model/audit restoration | Contract requirements mapped. Destructive recovery and complete product-facing route qualification pending. |
| J05 | Connect, analyze, train, promote | Authenticated tenant adapter -> ingest -> TOE analysis -> lineage/receipt; denied roles; quarantine exclusion; held-out evaluation; safe promotion; vendor outages | SYSTEM_CONTRACT.md gives source and installed-package gates; deployment identity/vendor/durability/load gates remain open. |
| J06 | Observe, investigate, export | Current source timestamps; failures not stale green; tenant-scoped authorized audit/evidence download; digest verification and independent retention | Console observability mapped. Current audit lens explicitly lacks a tenant-export contract; a system-wide evidence ZIP is not automatically tenant-safe. |
| J07 | Customer provisioning and treasury | Authorized customer lifecycle, backend-only balances, gain-share inputs/formulas, dual approval, custody-backed signing, settlement/reconciliation, honest offline state | Complete UI/API/ledger/settlement journey not qualified. Do not infer completeness from endpoint existence. |
| J08 | Install, deploy, upgrade, roll back | Clean wheel and rebuilt sdist; actual image builds; proxy health/readiness; secret rotation; backups/restores; upgrade and demonstrated rollback | Full checkout, clean installs, current CI and target deployment access are needed. Migration snapshot not yet confirmed. |

## Performance acceptance

For each representative journey record workload size/distribution, arithmetic scope, requested and executed route, correctness result, warm/cold behavior, concurrency, latency distribution, throughput, peak memory and errors. Include overload, cancellation, dependency outage and recovery. Establish workload-specific release budgets before the acceptance run; do not invent thresholds after seeing measurements. Compare any optimization with a named baseline under equivalent work and correctness, retaining raw observations. The 53-test runtime is test-suite duration, not a product benchmark.

## Exact-head qualification sequence

1. Confirm the completed migration is pushed; local branch is main; worktree clean; HEAD equals origin/main. Record the SHA. No broad staging or force-push to hide unresolved changes.
2. Inventory all tracked test roots and package projects. Root pytest testpaths do not imply every nested component was collected. Retain collection errors, skipped tests, missing dependencies and unavailable external checks as explicit gaps.
3. Run canonical source tests and role/security/integration suites; build and test clean installed wheels and rebuilt sdists, frontend typecheck/tests/build and each retained Docker image. Repair reproduced failures; rerun affected gates at the new main SHA.
4. Execute J01-J08 against actual composed services, then the target deployment. Bind logs/receipts to tenant, operation and source/artifact versions. Fixture-based client tests alone cannot close these journeys.
5. Run performance, failure, soak, corruption, backup/restore and rollback acceptance. Verify secrets/redaction, role and cross-tenant denials, audit retention and evidence export.
6. Generate the release pack and inspect all digests. Issue READY only when every required journey and release gate has fresh passing evidence and there are no unresolved release blockers. Missing/inaccessible evidence is not PASS.

## Executed closeout slice

Source baseline: main merge `6c8d71fc6f41f5b43514039bab3ee83bb55a14c1` (PR144). Unchanged frontend source was retrieved through GitHub MCP into an isolated partial-source harness; original Git blob hashes were verified for the changed modules. No transitional developer filesystem was searched or modified.

Reproduced existing frontend gate: 10 failed, 21 passed. The API had removed JS-readable operator keys but the entitlement helper still required one, preventing successful cookie login from opening the console. Identity-string deduplication also missed cookie-only session changes; in-flight check changes and tenant rebindings needed explicit invalidation.

Fixes: entitlement comes exclusively from the current server cookie session; no operator bearer or client role grant added. Queue a new entitlement check after session changes; invalidate snapshots on all session/subscription events and server principal transitions; reject late replies; refresh entitlement before polling. Update obsolete bearer-era test assumptions and transport documentation.

Fresh focused verdict: 53/53 tests passed across access, API, console lifecycle and rendered ControlSession journeys; changed modules and tests typechecked against actual status/evidence types. Retained evidence under `evidence/2026-10-23/production-closeout-auth/` includes the partial harness configuration, dependency versions, logs, JUnit and digests. Reproduce in a full checkout with `cd frontend && npm ci && npm run test:ts -- src/lib/__tests__/access.test.ts src/lib/__tests__/api.test.ts src/lib/__tests__/console-lifecycle.test.tsx src/components/__tests__/ControlSession.journey.test.tsx`, then `npm run lint` and the complete test/build gates.

No full frontend build, full repository suite, deployment, live external action, product benchmark or complete production certification was performed by this slice. GitHub MCP can read/write source, but its token cannot read check runs; the local CLI has not been authenticated for a full private checkout. Those are concrete execution blockers, not completed gates.
