# HYBA Enterprise — Planning-to-Code Audit (non-mining)

## Decision: repair the assurance gaps, then prove a complete enterprise journey

**The enterprise vision is not yet demonstrated by the reviewed product surface.** The primary frontend is a CEO-authorized mining console, not the planned tenant enterprise experience. Three real defects in common enterprise reference services are repaired on this branch. This is a scoped audit and repair pass, not an exhaustive repository/security audit or a release certificate.

Audit baseline: `HYB-APHIDATA/HYBAEnterprise` at `b131edc408a37ff7c03534d694bfcdaf0c827abb`, 25 October 2026. The new branch was created at that exact SHA. Mining operation, pool connections, credentials and mining implementation changes are excluded. The existing console was inspected only to determine whether the non-mining enterprise journey exists at that entry point; no mining functionality was changed or exercised.

## What the plans require

Active Capacity and Cloud architecture call for one coherent Capacity Fabric, outcome products Storage / Movement / Tensor, enterprise/cloud/sovereign editions, governed Intelligence, explicit custody and evidence-backed economics. Engine names belong in technical assurance, not a substitute for customer tasks. The user's consulting/design/academic references are quality aspirations, not affiliations, endorsements or proof of superiority.

Planning sources:
- [Active Capacity strategy](https://app.notion.com/p/2bcce10d45314dc49a58d81de2654dbb)
- [Cloud product architecture](https://app.notion.com/p/a52099f8cf0e4850990766dd2ed86aa2)
- [Product lock register and HYBA-CUSTODY-001](https://app.notion.com/p/3f113476fb44496e99a2fcbb37546ccb)
- [Whole-repository capability map, historically scoped](https://app.notion.com/p/89ed31ab028d49f8ba4549eb2c7fc1de)
- Current source `docs/HYBA_STYLE_GUIDE_FRONTEND_PRODUCT.md`.

## Three defects are repaired, not merely described

1. `capture_notebook` previously marked every captured session `reproducible=True`, including contradictory outputs, without replay. It now preserves capture/provenance but reports `reproducible=False`, `replay_status=NOT_RUN`. This does not implement a replay engine.
2. `ProofService.certify` accepted an empty invariant mapping and coerced arbitrary truthy values into proof success. It now refuses empty invariants and requires literal boolean `True`. A local signature is not independent attestation.
3. `ModelRegistry.promote` accepted an empty check iterable, arbitrary truthy check results and direct jumps to deployment when metadata fields were present. It now requires nonempty checks, literal `True`, and the declared sequential lifecycle. Rejections leave persisted state unchanged in the tested serial cases. This is not a substitute for tenant/principal authorization, signed approvals, concurrency control or crash-safe registry publication. Re-registering an existing model and filesystem tenant/path boundaries need further adversarial review.

Compatibility: notebook evidence is intentionally more conservative; callers must not equate capture with successful replay. Promotion callers that skipped lifecycle states or used integer/string success values must migrate to explicit validated stages and booleans. No existing data migration, deletion, authority reassignment or provider activation is included.

## Product experience remains the largest observed planning gap

`frontend/src/App.tsx` routes every view through the mining console's shared status/access context and explicitly says the non-mining workspace is unavailable. This establishes a gap at that primary frontend entry point, not absence of all enterprise code elsewhere in the monorepo. Do not remove the existing mining authorization check, rename mining telemetry as enterprise data or fabricate provider endpoints.

`frontend/src/index.css` uses `--pythia-*` and `--pythia-gold: #635bff`; the current brand guide specifies HYBA blue/gold tokens. Existing focus, reduced-motion and responsive treatments are positive, but neither static CSS inspection nor token substitution demonstrates accessibility or a finished customer journey. No visual rendering, browser usability or screenshot acceptance was run in this pass.

### Required enterprise information architecture — target, not shipped

- **Overview:** the customer's objective, verified outcome, constraints and next decision.
- **Workloads:** Storage, Movement and Tensor jobs with actual state, scope, cost and evidence.
- **Intelligence:** common TOE-backed Optimize / Simulate / Decide / Verify / Scientific tasks, with admitted domain and uncertainty; EUCLID orchestrates rather than replaces authority.
- **Resources:** capabilities, placement, capacity and approved fallback; hardware truth comes from actual probes.
- **Assurance:** policies, approvals, custody lineage, signed/exportable evidence and recovery history.
- **Economics:** measured baseline/overhead/net savings where contractually applicable; unapproved billing stays deferred.
- **Administration:** tenant identity, roles, residency, retention, deployment, support and version history.

Design acceptance: executive answer-first hierarchy; official HYBA asset/approved typography; navy/blue structure and restrained gold; verified/unknown/unavailable visually distinct; keyboard and screen-reader workflows; WCAG 2.2 AA target measured, not asserted; responsive views; empty/loading/error/permission/expired-session states; no mock fixtures presented as production evidence. Do not touch the excluded mining console to manufacture enterprise completion.

## Current authority and billing facts must replace stale generalizations

`aethel/ovid_authority.py` already labels itself a legacy Ovid-root profile. It should not be reported as an unqualified second enterprise root. Historical OWNER_DECLARATIONS D4/D9 still need explicit reconciliation with the newer Theseus-custody / Ovid-transformation decision, without rewriting historical quotations or silently migrating stores. The canonical enterprise adapter, interrupted-write/restart paths and tenant isolation have not been rerun on this candidate.

TOE and Kellogg manifests retain explicit authorities and capability limitations; reading those manifests does not execute their capabilities. TOE's manifest still separates implementation from production qualification. This review does not reduce TOE to a mining helper or claim universal domain performance.

The current TURING Hermitten contract expressly withdraws the old adapter experiment and defers billing. Do not force the Data avoided-cost commercial model into TURING, invent a billing provider or block the compute engine on a withdrawn integration. Commercial readiness is a separate acceptance track.

## Requirements ledger

Status distinctions matter: CONFIRMED GAP is observed source divergence; RUNTIME OPEN/NOT TESTED is an evidence gap, not proof the feature is absent. REPAIRED ON BRANCH is not merged or deployed. `requirements.csv` includes source, accountable role and concrete closure acceptance for each row. Accountable roles are proposed work ownership, not assignments to named people.

| ID | Requirement | Finding | Priority |
|---|---|---|---|
| ENT-01 | Enterprise-first customer journey | CONFIRMED GAP | P0 |
| ENT-02 | Brand system in actual product | CONFIRMED GAP | P1 |
| ENT-03 | Notebook reproducibility evidence | REPAIRED ON BRANCH | P0 |
| ENT-04 | Non-vacuous proof issuance | REPAIRED ON BRANCH | P0 |
| ENT-05 | Model promotion lifecycle | REPAIRED ON BRANCH | P0 |
| ENT-06 | Offering-specific readiness | CONFIRMED GAP | P1 |
| ENT-07 | One current custody decision | DOCUMENTATION DRIFT; PARTIAL CODE ALIGNMENT | P1 |
| ENT-08 | TOE domain-general intelligence | MANIFEST REVIEWED; RUNTIME NOT TESTED | P0 |
| ENT-09 | Kellogg exact and bounded mathematics | MANIFEST REVIEWED; RUNTIME NOT TESTED | P1 |
| ENT-10 | Theseus durable custody and Ovid transforms | LEGACY PROFILE REVIEWED; CANONICAL RUNTIME OPEN | P0 |
| ENT-11 | SALAMANDER enterprise bounded recovery | PLANNING REVIEWED; CURRENT RUNTIME NOT TESTED | P0 |
| ENT-12 | EUCLID orchestration and domain authority | CONTRACT CODE REVIEWED; EUCLID RUNTIME OPEN | P1 |
| ENT-13 | PULVINI fold bounds | PLANNING REVIEWED; CURRENT RUNTIME NOT TESTED | P1 |
| ENT-14 | TURING VQC bounded computation | BILLING SCOPE REVIEWED; COMPUTE RUNTIME OPEN | P1 |
| ENT-15 | Chronus heterogeneous non-mining execution | PLANNING REVIEWED; CURRENT RUNTIME NOT TESTED | P1 |
| ENT-16 | Storage / Movement / Tensor outcomes | REFERENCE LAYER REVIEWED; MANAGED JOURNEYS OPEN | P0 |
| ENT-17 | Sovereign / offline edition | PLANNING REVIEWED; DEPLOYMENT NOT AUDITED | P0 |
| ENT-18 | Economics and commercial delivery | SCOPE DIFFERENCES CONFIRMED; BILLING NOT QUALIFIED | P1 |
| ENT-19 | Provider-backed integrations vs references | REFERENCE CODE REVIEWED; EXTERNAL BINDINGS OPEN | P1 |
| ENT-20 | Installed releases and supportability | PLANNING REVIEWED; RELEASE NOT AUDITED | P0 |

## Closeout sequence: build vertical slices, not a cosmetic dashboard

**P0 assurance:** review/merge the scoped repairs after full-package compatibility tests; bind real identity/policy/tenancy; qualify custody and denial paths. Resolve registry path/race/re-registration risks before exposing it as a multi-tenant service.

**P0 enterprise slice:** begin with verified backup-and-restore or model/checkpoint distribution. Exercise tenant sign-in → approved workload → bounded execution → durable commit → deliberate failure/recovery → independently checked result → evidence export. Retain commit, installed artifacts, configuration, commands, logs and outputs. The same workflow must reject unauthorized/cross-tenant requests and report missing dependencies honestly.

**P1 outcome expansion:** run independently scoped Storage, Movement, Tensor and Intelligence journeys; test real provider adapters, revocation, timeouts, concurrency and recovery. Replace all-offering readiness assumptions with versioned applicability rules rather than globally deleting gates.

**Release and design acceptance:** supported-platform clean installs, offline/sovereign cases where offered, package imports and dependencies, full regressions, load/soak/restore drills, accessibility/user acceptance, documentation/API parity, approved legal/support/commercial terms, and one signed candidate-specific release decision. Never transfer historical passes to a new candidate or label deferred CI passing.

Differentiation should be demonstrated by the closed loop: governed reasoning → bounded execution → durable custody → independently checkable evidence → measured customer outcome. The modules suggest this architecture; this pass has not proven a whole-system superiority claim or a financial benefit.

## Executed evidence and limitations

The five logs and `test-evidence.json` were regenerated on 26 October 2026 because
the historical invocations did not retain recoverable per-run source identities.
The results below describe these fresh reproductions, not a recovered identity
for the earlier runs. The JSON records the current Python/platform, command,
timestamp, exit status and log digest for each invocation.

- Readiness baseline: 34 tests passed; unchanged after repairs: 34 passed. These are repeat runs of the same suite, not 68 distinct tests.
- New enterprise regressions before fixes: 14 tests, 8 failures (expected defects reproduced).
- After fixes: 14/14 passed normally; the same 14/14 passed under `python -O`. These are not 28 distinct tests.
- Actual retrieved `hyba_services` modules and actual `hyba_contracts` package initializer were executed with synthetic fixture data. Only `hyba_services.__init__` was bypassed in the partial-export harness because the full tree is not materialized. No repaired function was replaced by a double. The full package import and existing cross-product suites remain unexecuted.
- The original audit used a selected, blob-verified export: authenticated GitHub MCP reads worked but terminal Git could not authenticate. The fresh reproduction used the local Git checkout to reconstruct isolated exports; each test invocation still ran only the manifested files. The original audit's exact branch base was independently confirmed by GitHub's ref result.
- No current TOE/Kellogg/TURING/Chronus/PULVINI/SALAMANDER/EUCLID engine-wide runtime suite, HTTP service, device execution, real provider sandbox, Docker end-to-end, installed artifacts, paid CI, penetration test or production soak was executed in this pass.
- One attempted custody path `aethel/custody_binding.py` did not exist; `aethel/enterprise/` was subsequently enumerated. That unsuccessful lookup is not evidence that custody is absent.
- No full-system production/publication approval, deployment, tag or release is performed by this audit.

### Evidence files and reproduction

See `source-manifest.json` (input file identities), `test-evidence.json`, failed-first/passing logs, `requirements.csv`, and the adjacent explicit partial harness. From repository root:

```bash
python docs/qualification/non-mining-enterprise-audit/run_partial.py
python -O docs/qualification/non-mining-enterprise-audit/run_partial.py
python -m unittest discover -s tests -p test_tomorrow_readiness.py
# Required next: normal full installed imports and complete enterprise suite.
# The partial harness intentionally does NOT establish that acceptance.
```

### Source identity for the reproduced runs

`source_revision` remains the original base-export identifier. Each run's
`tested_source` instead binds an immutable SHA-256 manifest of every source file
in its isolated export. These exports combine revisions and an uncommitted runner
repair, so no commit is claimed as the tested source.

- `tested-source-before.json`: the base-export versions of the service modules,
  contracts and readiness files, overlaid with the current guardrail tests and
  guarded `run_partial.py`. This export produced the baseline readiness and red
  guardrail runs. The red run deliberately executes the original defective service
  implementations; its eight failures are expected.
- `tested-source-after.json`: the current versions of the same files, including
  the repaired services. This export produced the green, optimized and unchanged
  readiness runs.

To reconstruct either export, copy only its listed paths into an empty directory
with the same layout and verify every file's `sha256` before running the recorded
command from that directory. For the before export, retrieve all paths except
`tests/test_enterprise_audit_guardrails.py` and `run_partial.py` with
`git show b131edc408a37ff7c03534d694bfcdaf0c827abb:<path>`; copy those two overlays
from this repair. The after export uses this repair's files. The manifest digest
is checked against `tested_source.manifest_sha256`; log bytes are checked against
`log_sha256`. The reproduction verified the original base manifest against Git
and checked source hashes before and after every run.

The runner rejects zero discovered cases before invoking `TextTestRunner`.
`tests/test_enterprise_audit_runner.py` checks empty, passing, failing and
import-error discovery in normal and optimized Python without importing the
enterprise services.
