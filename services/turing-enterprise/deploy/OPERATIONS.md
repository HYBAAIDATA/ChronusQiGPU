# Deployment, onboarding, recovery and publication

## Deployment envelope

This is a bounded single-host reference topology, **not production acceptance**.
Docker is unavailable in the local authoring environment; image build/run is a
separate non-skipping CI job. Review its results before use. Pin approved image
and dependency digests, retain SBOM/vulnerability review and verify the platform's
native sandbox/cgroup behaviour before promotion. No host cloud/registry/IdP credentials were supplied or invented.

1. Build from the complete repo, not a service-only checkout:

   ```bash
   docker build --build-arg SOURCE_COMMIT="$(git rev-parse HEAD)" \
     -f services/turing-enterprise/deploy/Dockerfile -t APPROVED-PRIVATE-IMAGE .
   ```

2. Copy `service.example.json` to `service.json`. Configure approved IdP issuer,
   client/audiences, JWKS and code-flow endpoints, exact HTTPS service origin,
   `billing_scope: deferred` and actual service limits. Register exact
   callback `https://SERVICE/auth/callback`. Customer and operator signing keys
   are independent base64 random keys (at least 32 random bytes); session key is
   a Fernet key. Keep all in private secret files owned by UID 10001, mode 0600.
   Operator and commercial-approver subject allowlists must be disjoint. Do not
   put secrets in source, command arguments, browser storage or `.env` commits.
3. Configure retained independently signed approval bundle/public key and reviewed
   source commit. The image bakes `/opt/service-source-commit`; production refuses
   a mismatch or missing/stale evidence. Do not substitute self-generated PASS
   evidence. An isolated evaluation may explicitly select `controlled-pilot`;
   this deliberately omits production promotion requirements, not safety
   permissions. It must not be routed as an approved enterprise service.
4. Use the Compose topology behind TLS ingress. Host port is loopback-only. The
   configured origin must match the browser origin. Do not trust arbitrary
   forwarded headers. Restrict API egress to approved IdP/JWKS endpoints;
   the worker has `network_mode:none`. Configure ingress login/readiness/body/
   connection rate limits and timeouts. Public login must not be an unbounded
   identity-provider or SQLite write amplifier.
5. Image UID 10001 owns local SQLite/result volumes. Verify permissions, volume
   encryption, backup encryption/residency and resource limits. WAL requires local
   POSIX locking, not NFS. No horizontal HA or physical hardware allocation is
   promised. One worker processes jobs serially; reservations are admission slots.
6. Send traffic only after `/health/ready` succeeds with the canonical VQC report,
   valid promotion evidence. Liveness alone is
   not readiness. Monitor request errors, queue age, disk/memory, unknown outcomes,
   contract expiry and retained usage integrity; configure an alert
   receiver and human on-call. No external monitoring service is assumed.

## Onboard a customer

No named institution from a planning example is treated as an actual account.

1. Commercial owner approves the exact terms envelope: `tenant`, `billing_account`,
   `contract`, integer UTC epoch `starts`/`expires`, `contracted`, `allowance`.
   Hash the canonical JSON with `hyba_turing_service.control.digest`.
2. A separately allowlisted approver calls
   `POST /api/ops/customers/{tenant}/approval` with
   `{approval, contract, terms_hash, expires}`. This records the human decision;
   it is not a contract-signature integration or legal approval generator.
3. Operator calls `/approve` with the terms **except tenant** plus `approval` and
   unique `command`. Approval hash must match exactly. `/provision` takes `slots`
   and `command`, enforcing contracted and global budgets. A reservation records
   commercial entitlement; readiness is checked separately.
4. Operator `/member` bootstraps the nominated admin using IdP subject, `role:admin`,
   `active:true`. Customer admin creates projects with `slots`, `allowance`,
   `members` (IdP subjects), `active:true`. Sum of active project slots cannot
   exceed customer allocation. Admin may manage customer access; analysts cannot.
5. Confirm customer login, negative cross-tenant/project checks, revoked-member
   denial, supported/unsupported work and durable results. Operational completion
   facts are not invoices. Do not configure a billing receiver or spend ceiling.
6. Activate only within approved window and accepted service policy. Reserve one
   bounded pilot workload first; do not provision hypothetical 100-instance deals.

The `/ops` commercial action form accepts the same action-specific JSON (without
`tenant`, actor, keys or runtime). `/api/openapi.json` is authenticated. Paginated
list APIs take `limit` (1..100) and `after` (last lexical identifier; audit uses
last numeric cursor). Job history uses server-side filters and cursor next/previous controls; other
inventories show the first 50. Use the API for full permitted exports.

## Operational reconciliation — billing deferred

Contractually agreed usage-based billing is the future direction, not an enabled
commercial integration. Hermitten's separate avoided-cost data model is not a
TURING/VQC dependency. No billing scheduler, spend reservation, statement or invoice
is activated. The `billing` command and financial APIs refuse operation; explicit
billing-provider/spend configuration fails closed. Retained legacy helpers and
outboxes are historical non-financial observations, not pending required charges.
Operational reconciliation reports retained fact counts separately from issues.

Suspension prevents new admission; operators must inspect/drain active work and
cancellation before resolving it. Membership/project changes are checked during
worker polling, not just at login. Killing work produces an ambiguous outcome,
not an automatically billable completion. `running`/`unknown` on restart remain
quarantined; inspect retained result/custody and execution evidence, then use the
explicit operator resolution with a reason. Never automatically retry an unknown
job under a new ID. No financial authorisation is inferred from an execution state.

## Backup, restore, renewal and deletion

- Take consistent SQLite backup via `backup --destination NEW_PATH`; snapshot
  custody together under an execution maintenance window. Export the audit head
  to an independent immutable store. The local hash chain is not WORM and cannot
  defeat a privileged database administrator by itself.
- Restore only to a new destination via `restore --destination NEW_PATH` and
  configured `backup_source`. Validate integrity, keys/config, report files and
  outboxes before routing traffic. Restoring a DB alone is not result recovery.
  Do not overwrite the active database or re-execute old running work.
- Renewal requires a drained organisation and separately approved exact next
  contract terms. Existing contract is archived; current allowance is scoped to
  the new contract, state becomes suspended until explicit activation. Existing
  usage, project configuration, approvals and job identities remain retained.
- Retire only after draining; schedule contractual retention. `/purge-data`
  requires an operator reason, retired state and elapsed retention. It deletes
  live report files and clears live job input/report fields; immutable audit,
  usage and financial references are deliberately retained. Backup expiry,
  legal holds, cryptographic erasure and residency are separately governed by
  the deployment owner. This is not a blanket GDPR-erasure claim.

## Incident and support policy template (commercial owner must approve)

Assign named on-call, incident commander and customer administrator contact before
pilot. Suspected tenant leakage, incorrect verified results or evidence corruption:
suspend affected admission, preserve evidence, revoke affected membership/keys,
pause dispatch if necessary, record timeline and contact security/commercial owners.
Recover to a verified state before resumption. Publish a customer-specific service
notification under the approved communications policy. Response/restoration times,
maintenance windows and SLA credits are negotiated; no unsupported availability
promise is embedded in the UI or package.

## Production and publication promotion

`release-check --config PATH [--publication]` is an evidence-only, read-only
preflight. It reads the policy/config, image identity and approval artifacts,
without opening runtime signing/session secret files or initializing the customer
database/custody. It does not validate runtime secret availability, IdP access,
installed native execution, readiness or deployment. Production `serve`/`worker`
verify promotion admission before initializing authorities and persistent state;
accepted startup still requires all existing runtime secrets and authorization.
`controlled-pilot` remains an explicit evaluation mode, never implicit production
approval, and its explicit `release-check` still requires signed evidence.

The command verifies the read-only image source,
Ed25519-signed `approval.json`, matching commit, <=7-day freshness, expiry, named
reviewers and SHA-256-bound retained artifact for each required gate. Envelope:
`{manifest:{schema:"turing.promotion.v1",commit,billing_scope:"deferred",issued_at,expires_at,gates:{...}},signature}`.
Each gate entry has `state:"PASS"`, `reviewer`, `executed_at`, relative `artifact`,
`sha256`; signature is base64 over canonical JSON manifest. Verification public
key is deployment-owned, independent of service signing keys. Runtime, identity,
recovery/load, package and commercial approval gates are mandatory; publication
also requires `publication_rights`. Missing evidence fails closed. Do not use
unit-test generated fixture approvals in deployment.

Separate acceptance: real canonical package suite/clean install; actual IdP tenant
policy and security review; measured target
load, restart/backup/custody restore; approved non-financial contract/support; source/IP/license
and public-claim review. Validate public claims against retained evidence; no
physical QPU, arbitrary scale, validated tariff or customer endorsement is implied.
The command checks evidence, **does not** deploy, create a release tag, upload to
PyPI, change repository visibility or publish company IP. Those actions follow a
separately approved release procedure only after these gates pass.

## Scope migration and denial audit

1. Back up database and custody under the documented maintenance window.
2. Remove legacy billing URL/token/import/spend configuration; set
   `billing_scope: deferred`. Do not erase historical records or change contracts.
3. Independently review/re-sign the promotion manifest with the explicit deferred
   scope and all remaining gates. Old scope-less approval is deliberately invalid.
4. Validate health/readiness and negative authorization; no deployment is implied.
5. Rollback requires a separately reviewed configuration: old binaries may require
   financial wiring. Do not blindly roll back to a build that reinstates billing.

Backend operation denials append a correlation-bound audit event under the reserved
`__service_security__` namespace. Subjects and target tenants are hashed; no bearer,
request payload, raw subject or raw target is logged. Hashes are pseudonymous, not
anonymity. They are not placed in a foreign customer's audit feed. Audit failure
returns unavailable and never authorizes work. These events still require approved
security monitoring, retention, access controls and independent audit anchoring.
Unauthenticated denial logging is subject to the required ingress rate limits;
this is not a claim of a complete IdP/security event export integration.

## Explicit operator risk acceptance

The default qualification policy remains `strict`. An operator-authorized release
may explicitly configure `qualification_policy: operator-risk-acceptance`.
Only that opt-in allows required qualification entries to be `WAIVED` rather
than `PASS`. A waiver does not claim the test ran or passed. Each waived entry
retains its relative `artifact` and `sha256` and replaces `reviewer`/`executed_at`
with `risk_acceptance: {approver, reason, authorization_reference, accepted_at}`.
All three text fields must be nonempty; `accepted_at` is a UTC epoch integer.
Do not include `executed_at` in a waiver. The normal signature, commit binding,
artifact-integrity, seven-day freshness and expiry checks still apply.

The existing deployment-authority key may attest the operator decision; a new
secondary qualification reviewer is not required by this policy. This is not
permission to invent a deployment private key or substitute fixture signatures.
`publication_rights` cannot be waived through this qualification policy.
Authorization, identity, tenant isolation, request validation, custody integrity,
resource bounds and readiness computation are unchanged. Missing host access,
real secret bindings or an actual identity configuration are execution
prerequisites, not failed tests that a waiver can supply.

The operator's current decision is retained in
`../evidence/operator-risk-acceptance/decision.json`. That record is not itself a
signed promotion bundle and does not start a deployment. Build and sign against
the final pushed candidate commit, not the historical baseline SHA. A production
host must supply its real configuration and deployment-authority signature.

## Authenticated recovery of a retained service result

The configured worker writes the original report and then an immutable
`turing.service-recovery.v1` receipt before returning for SQLite completion.
The receipt authenticates the tenant, job, original request digest, admission
hash (including actor/project), and report digest. This is service-output
integrity, **not** a replacement for canonical mathematical verification or
shared THESEUS/OVID custody.

After investigating a `running` or `unknown` job, an authorized operator may call:

```text
POST /api/ops/customers/{tenant}/recover-result
{"job":"ORIGINAL_JOB_ID","reason":"ACTUAL_INCIDENT_REFERENCE_AND_FINDINGS"}
```

Use the existing operator identity/session, CSRF and `turing.ops.manage`
authorization rules. The server supplies its configured custody object; HTTP
input cannot choose a recovery source. Recovery never runs the computation.
The same transport-validation rules used for normal completion apply; a retained
FAIL remains failed. Completion, deferred non-chargeable operational usage,
delivery reference and audit commit atomically. Repeating a completed recovery
returns the same report without duplicating usage. An operator-resolved failed
job is not resurrected. Recovery records observation time explicitly; it does not
invent the original execution timestamp.

By default, a distinct recovery HMAC key is derived from the private base64
`operator_key_file` with domain `turing-service-recovery-v1`. Prefer a separate
private base64 `custody_integrity_key_file` (>=32 random bytes) for independent
rotation. Both API and worker must receive the same current key configuration.
`previous_custody_integrity_key_files` is an optional list of private master-key
files retained for authenticating older receipts. Old receipts are not rewritten
on rotation. Retain required historical keys until their reports expire; removing
a key deliberately makes its receipts unrecoverable. Never expose these keys to
worker children, HTTP requests, logs or source control. HMAC does not protect
against an attacker who controls the parent service and its keys.

Back up and restore the database, report files, `.receipt` files and appropriate
key/configuration versions together under the existing maintenance procedure.
Reports without valid matching receipts (including legacy unsigned reports),
missing keys, corrupted output and crashes before receipt durability remain
quarantined. Do not sign old files merely to make recovery pass or automatically
resubmit unknown work. Existing reasoned `resolve` remains failure resolution,
not proof of successful execution. Use an incident-specific custody investigation
for the remaining cases.

Local acceptance evidence and explicit limitations are retained at
`../evidence/authenticated-recovery/`. This closes only the report-durable /
database-incomplete service window. It does not close the standalone-vs-shared
composition-root gap, all orphan windows, target-host recovery/load tests,
remote CI, live identity acceptance or deployment.

### Distribution dependency boundary

The service wheel is not a self-contained platform distribution. Its configured
entry point consumes the real `al_haras.entitlements` authority; shared-custody
integration tests also consume `aethel`. The reference image supplies platform
source from the full repository, while the computational worker uses installed
TURING/Kellogg distributions. Installing only the service wheel and server extras
in an otherwise empty environment is not a supported full deployment: the
retained standalone test run fails at the two configuration/composition cases
because AL HARAS is absent. No mock authority, copied verifier or hidden fallback
was added to disguise this boundary.

The passing artifact runs use a fresh environment, installed wheel/sdist and
actual TURING/Kellogg, with the supplied platform source on `PYTHONPATH` as in the
reference topology. Recorded import locations and hashes distinguish these
inputs. A wholly installed multi-distribution platform needs its own real
AL HARAS/platform dependency closure and conformance evidence before it can claim
standalone installation. The complete current-main platform was not substituted
for the supplied archive or falsely described as installed.
