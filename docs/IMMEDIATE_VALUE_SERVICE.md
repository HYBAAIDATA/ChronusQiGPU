# HYBA — mission-to-outcome service: reviewed foundation and first implementation

Status: engineering candidate, not a deployment, public release or new commercial approval.
Reviewed source: `f58ccc7c4f1d406f1cc1c190faace72d1c6b57cd`.
Owner direction: onboarding begins immediately upon contract signature; first usable value the same day.
This change implements the first inspectable service milestone, not that entire promise.

## Product vision

Deliver an intelligence service whose unit of engagement is a customer outcome, not a chat session.
A customer supplies an objective, permitted data, constraints and an acceptance criterion. The
instantiated intelligence develops and tests candidate approaches through the existing authorities;
only authorized actions run. Each delivered outcome includes reproducible evidence and a route to
acceptance, revision, continued operation or rollback. Dialogue is an interface, not the product.

EUCLID must be exercised through its instantiated orchestration path, not replaced by an LLM,
standalone solver or an impressive-looking dashboard. TOE supplies its actual supported reasoning;
Kellogg and TURING retain mathematical authority; AL HARAS governs access/actions; Ovid and Theseus
retain their version-specific transformation/custody boundaries. SALAMANDER governs bounded recovery.
No new central authority or duplicate intelligence engine is introduced here.

Paradigm-shift ambition: compress the distance between a customer's intention and a verified,
operational outcome, while retaining permission, provenance, learning lineage and reversibility.
Novelty, learning and customer impact must be demonstrated, not inferred from the label AI.

## What we have — scoped review, not a whole-repository audit

| Foundation | Evidence reviewed | Consequence |
| --- | --- | --- |
| Enterprise infrastructure strategy | HYBA Cloud architecture in Notion | Storage, Movement, Tensor and Custody are enterprise outcomes; mining is optional |
| Canonical console closeout | Notion journey/wiring record | Current mining console is not a general enterprise workspace; do not silently reuse its CEO-only policy |
| Enterprise service | `services/turing-enterprise/README.md`, `control.py`, `enterprise.py`, `api.py`, `runtime.py` | Real transactional approval/reservation/project/authorization/job lifecycle exists; extend it |
| Contract approval | `EnterprisePlane.register_approval`, `_check_approval`, `approve_customer` | Exact approved terms exist; these records are not electronic signatures |
| Native execution boundary | `ControlPlane.execute`, `ProcessRuntime`, `DurableRuntime` | Service invokes configured runtime and preserves outcome uncertainty; do not compute answers in this view |
| Instantiated intelligence | Previously source-traced `euclid/runtime.py` production and adaptive composition | Native mission integration needs runtime execution evidence; not exercised by this change |
| Exact mathematical capability | TURING product lock and public facade review | Supported finite-domain exact computation; not unrestricted scaling or physical-QPU equivalence |
| Commercial scope | Current enterprise-service README and `commercial.py` | TURING billing remains deferred; no Hermitten/provider/spend activation here |

The source retrieval for some `hyba_services`/`hyba_contracts` paths was inconsistent (directory
entries were returned but selected file reads failed). Those modules are not qualified by this
review, and retrieval failures are not evidence that their implementations are absent.

## Enhancement delivered in this candidate

`EnterprisePlane.activation_status(token, actor, tenant=..., project=..., job=None)` and
`GET /api/customer/{tenant}/activation-status?project=...&job=...` expose the existing service's
point-in-time activation and selected-job evidence through its existing identity boundary.

- Rechecks identity, tenant membership, submission-capable role and project access.
- Reports contract state/window, customer/project capacity and allowance blockers.
- Reads existing job states: queued, executing, failed, cancelled, reconciliation required or result available.
- Binds completed service facts to tenant, current contract, project, job and retained report digest.
- A completed prior-contract job cannot become the new contract's first outcome.
- Does not provision, submit, execute, retry, mint commercial authorization or turn on billing.
- Returns `runtime_health: not_probed`, `signature_status: not_assessed`,
  `customer_acceptance: not_recorded`, `business_value: not_established` and
  `deployment_qualification: not_assessed` rather than inventing those facts.
- Snapshot digest is content identity, not a signature, independent mathematical verification,
  capacity lease or authorization. Standard auth nonce/rate/security-audit bookkeeping still applies.

`result_available` means an existing service-accepted runtime envelope is retained and identity-bound.
It does not mean a customer accepted the result or achieved a financial benefit. The existing adapter
remains responsible for canonical mathematical verification. The new status view is not a second verifier.

## Immediate onboarding: prepare before signature, activate at signature

There is no arbitrary five-day lead time. The service should prepare a tenant-isolated, approved
engagement before signature, without unauthorized customer work or granting live access early.

Before signature:
1. Agree one first outcome and acceptance criterion; identify the customer's authorized acceptor.
2. Qualify the required runtime, service mode, data/access boundary and supported task representation.
3. Prepare capacity, identity mapping, approved exact terms, data prerequisites, support owner and recovery plan.
4. Retain fresh readiness evidence. Do not sell an unavailable integration as instantly active.

At signature:
1. A trusted commercial workflow verifies the executed contract and binds its exact terms.
2. Authorized operator calls the existing approval, provisioning, member and project APIs.
3. Customer receives access; existing project/job submission and worker paths perform the admitted task.
4. Activation-status view exposes blockers and the selected job's actual progress/result.
5. Customer receives the first usable deliverable with its evidence and explicit acceptance decision.

The current service does NOT implement a signature-provider event connector, automatic orchestration
of these operator steps, or a customer-acceptance register. This candidate does not claim otherwise.
Those are the next integration boundaries, not reasons to reimplement the underlying control plane.
Do not use an unauthenticated webhook, arbitrary approval reference or caller-supplied actor as a shortcut.

Same-day target measurement must start at the verified signature event, not from an invented timestamp.
Measure access granted, first admitted task, first result, first accepted outcome and operational handoff
separately. Preserve blocked/failed engagements in the denominator. Report latency distribution and
actual same-day attainment; do not turn a service objective into an observed SLA without measurements.

## Mission-to-outcome roadmap — enhancement, not implementation claims

### Next increment: native mission intake and trace
Bind customer objective, data identity, allowed actions, success criterion, budget, baseline and
customer acceptor to a versioned mission. Extend the canonical EUCLID runtime interface after proving
its actual task contract; do not force all missions into TURING QASM or create an external solver.
Trace which native authorities produced each candidate and verification result. Refuse unsupported
missions with actionable alternatives rather than route them to an undisclosed substitute.

### Next increment: preparation and signature-triggered activation
Use an approved signature-verification adapter with replay protection, exact-term binding and a
stable event identity. Reuse existing operator APIs and idempotency commands. Preserve separate
commercial approver/operator authority, project isolation, capacity contention and revocation.
No production mutation is authorized simply by a planning document or an AI recommendation.

### Next increment: outcome acceptance and continuous improvement
Record the authorized customer's decision against an immutable result/mission version. Corrections
are new decisions, not rewritten history. Distinguish service-envelope acceptance, independent
verification and customer acceptance. Where the instantiated system supports persistent learning,
record experience origin, permitted feedback, state version, transfer tests and rollback. Learning
must not rewrite policy, proof authority or benchmark targets.

### Next increment: outcome workspace
Build a non-mining customer journey: objective → constraints → admitted plan → live progress →
evidence → accept/revise → continued operation. Bind every panel to actual backend state, with
unknown, unavailable, denied and stale states. Do not copy mining authority or fabricate live telemetry.
Use the new activation endpoint for its limited purpose, not as a universal health/readiness score.

## Initial service offers — proposed packaging, not qualified products

1. Decide: a traceable analysis/recommendation from approved customer data and an explicit model.
2. Optimize: a bounded, independently checked workload improvement against an agreed baseline.
3. Verify: an admitted mathematical task and its reference/evidence package.
4. Operate: monitored, bounded adaptation/recovery after permissions and deployment are qualified.

Select the first engagement from a lane that can actually execute on available infrastructure.
Same-day value might be a usable decision artifact, verified computation or measured diagnostic;
it is not automatically a completed migration, production rollout or guaranteed saving.

## Acceptance evidence for this candidate

33 new tests: 24 real EnterprisePlane/SQLite tests and 9 actual FastAPI-route tests. Identity issuers,
authority transports and runtime reports are explicitly labelled test peers. Tests exercise native
service methods and persistence, not AST extracts, but do not instantiate EUCLID/TURING or enterprise SSO.

Run from a full checkout with the service/test/server dependencies installed:

```bash
python -m pytest services/turing-enterprise/tests/test_activation_status.py \
  services/turing-enterprise/tests/test_activation_status_api.py -q
```

Retain the existing full-service suite and canonical-runtime integration gate before promotion.
This environment ran only the new scoped suite against byte-verified copies of the required source
subset. No paid CI dispatch, main merge, container/service deployment or production-state change occurred.

## Sources

- <mention url="https://app.notion.com/p/a52099f8cf0e4850990766dd2ed86aa2">HYBA Cloud strategy</mention>
- <mention url="https://app.notion.com/p/394b68149fd0480fa219b660b0753ba5">console closeout</mention>
- <mention url="https://app.notion.com/p/f1ea1e2825114d54986de07910b99dca">EUCLID authority contract</mention>
- <mention url="https://app.notion.com/p/1a5b141389d74611a21714e71b54cd7c">TOE authority/capability contract</mention>
- <mention url="https://app.notion.com/p/b91c055f741345f6bcb1b831553d041a">mathematical quantum position</mention>
- <mention url="https://app.notion.com/p/3f113476fb44496e99a2fcbb37546ccb">release/commercial boundaries</mention>
- Source paths above are pinned to the reviewed base commit, not unqualified product certifications.
