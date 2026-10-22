# TURING enterprise service delivery · 0.2.0

**Private alpha implementation; not a production approval or public release.**
This is the **Enterprise Service Delivery and Commercialisation** workstream,
separate from mathematical correctness and package qualification in PR #96.

## Implemented service

- Customer/contract onboarding (legacy account labels are metadata only) against exact-term commercial
  approvals; bounded global logical reservations, project allocations and renewal.
- Separate internal operator, commercial approver and customer roles; OIDC bearer
  API and code/PKCE browser login, RS256/JWKS validation, server-side sessions,
  secure cookies, CSRF/origin enforcement and current membership on each operation.
- SQLite transactional admission, per-contract/project allowances, idempotency,
  cancellation, revocation, durable execution quarantine and operator resolution.
- Bounded child process consuming **the existing TURING pipeline**, memory/CPU/
  output/time limits, process-group fencing and tenant-keyed durable result files.
  No alternate mathematics, QPU simulation claim or replacement identity system.
- Three connected, same-origin interfaces: `/ops`, `/admin`, `/workspace`;
  authenticated OpenAPI at `/api/openapi.json`. No browser-stored API tokens.
- Append-only operational completion facts, stable event identities and audit
  chains. Contractual usage-based billing is **DEFERRED**; no provider, financial
  spending authority, rates or invoices are enabled in production composition.
- Backup/restore commands, retention-gated live-input/report deletion, local
  reconciliation, readiness probes, non-root reference deployment and fail-closed
  independent signed promotion evidence bound to the running image's source.

A slot is **one logical concurrent admission**, not a VM, QPU or dedicated device.
The reference worker executes serially; extra reserved slots admit bounded queued
work, not a throughput/SLA guarantee. Configure capacity against measured host
limits. SQLite WAL needs one local POSIX filesystem; this is not multi-region HA.
The process boundary is **not** a sandbox for arbitrary Python or native code.
Only the admitted QASM request schema reaches the canonical runtime. The reference
worker container has no network, no added capabilities and a read-only root.
Separate trust domains/stronger per-job isolation require deployment qualification.

`verified_execution.v1` is a legacy technical completion-counter identifier,
**not an approved chargeable unit, tariff or invoice**. New operational records
carry `billing_scope: deferred` and `chargeable: false`; historical records are
unchanged. Only a PASS pipeline envelope with execution/verification, certificate,
witness and program identity creates a completion fact. The configured adapter
remains responsible for canonical verification. No financial bill is generated.
Ambiguous work is never automatically re-executed.

Hermitten's avoided-cost data model is separate and is not a TURING/VQC dependency.
Retained experimental billing helpers are unreachable through the service's default
composition; explicit billing or spend configuration is rejected, not silently
ignored. No future provider or commercial terms are selected by those helpers.

## Install and validate

From the repository root:

```bash
python -m pip install -e 'services/turing-enterprise[server,test]' black build
python -m pytest services/turing-enterprise/tests -q
python -m black --check --line-length 100 services/turing-enterprise/src services/turing-enterprise/tests services/turing-enterprise/integration
python -m build services/turing-enterprise
```

Unit/contract tests use real SQLite, the repository's AL HARAS verifier, generated
RSA/Ed25519 cryptographic test keys and explicitly labelled runtime/billing peers.
They **do not** certify live enterprise SSO, live financial integration or real VQC execution.
The separate, non-skipping canonical-runtime CI job builds/installs the actual
VQC and Kellogg then runs `services/turing-enterprise/integration`. Missing runtime
fails that job; it cannot silently fall back to a mock. Remote success must be
observed, not inferred from workflow source.

Optional visual/interaction smoke uses explicit API fixtures, not live accounts:

```bash
# With Playwright installed in the execution environment:
CHROMIUM_PATH=/path/to/chromium node services/turing-enterprise/tests/portal-smoke.cjs
```

## Operate

Read [deployment and operations](deploy/OPERATIONS.md), the withdrawn historical
[Hermitten adapter proposal](deploy/HERMITTEN_CONTRACT.md), and the
[requirements/acceptance matrix](../../docs/TURING_ENTERPRISE_SERVICE_DELIVERY.md).
Example config contains placeholders, never deployable credentials.

`turing-service {serve,worker,billing,backup,restore,release-check} --config PATH`
reads trusted deployment configuration. API callers cannot supply signing keys,
identity issuer, actor, runtime, DB path, clock, custody path or billing adapter.
Use distinct customer/operator signing keys, private secret files and distinct
operator/approver identities. API action capabilities are issued internally only
after verified OIDC identity/current role checks. Library AL HARAS single-use
`jti` consumption is durable in SQLite; this is not a claim of full Guardian/AL
HARAS policy integration or distributed identity revocation. IdP logout/revocation
latency is bounded by token/session expiry (up to one hour for browser sessions);
service membership revocation is immediate on subsequent checks.

Production mode requires fresh independently signed retained evidence. The
explicit `controlled-pilot` mode permits evaluation without promotion approval or
independent signed promotion evidence; it is **not** production readiness and must never receive a
public production route. Do not turn unavailable commercial data into zero cost.
No deployment, invoice, source-rights transfer, tag or public upload is performed
by this package or its CI.

## Current qualification boundary

The complete requirements-to-evidence record is `../../docs/turing/ACCEPTANCE_REGISTER.md`.
Local service tests include real SQLite/cryptography and labelled runtime/IdP
peers; browser tests use transport fixtures. These do not qualify live enterprise
identity, canonical installed execution, container isolation or operations.
Production still requires every non-financial independently signed promotion gate.
The manifest explicitly binds `billing_scope: deferred`; older scope-less bundles
must be reviewed and re-signed by the independent approval owner, never fabricated
or rewritten by the service. There is no customer charge migration in this change.

`portal-release-scope.cjs` adds fixture regressions for history/filter cursors,
cancellation confirmation, unchanged report export and stale-tenant responses.
Set `AXE_CORE_PATH` to a test-only axe-core script to run automated WCAG-tagged
scans. This is not full accessibility conformance or manual assistive-tech evidence.
