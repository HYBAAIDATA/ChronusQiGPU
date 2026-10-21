# Deployment, onboarding, recovery and publication

## Deployment envelope

This is a bounded single-host reference topology, **not production acceptance**.
Docker is unavailable in the local authoring environment; image build/run is a
separate non-skipping CI job. Review its results before use. Pin approved image
and dependency digests, retain SBOM/vulnerability review and verify the platform's
native sandbox/cgroup behaviour before promotion. No host cloud/registry/IdP or
Hermitten credentials were supplied or invented.

1. Build from the complete repo, not a service-only checkout:

   ```bash
   docker build --build-arg SOURCE_COMMIT="$(git rev-parse HEAD)" \
     -f services/turing-enterprise/deploy/Dockerfile -t APPROVED-PRIVATE-IMAGE .
   ```

2. Copy `service.example.json` to `service.json`. Configure approved IdP issuer,
   client/audiences, JWKS and code-flow endpoints, exact HTTPS service origin,
   account-scoped Hermitten credential and actual service limits. Register exact
   callback `https://SERVICE/auth/callback`. Customer and operator signing keys
   are independent base64 random keys (at least 32 random bytes); session key is
   a Fernet key. Keep all in private secret files owned by UID 10001, mode 0600.
   Operator and commercial-approver subject allowlists must be disjoint. Do not
   put secrets in source, command arguments, browser storage or `.env` commits.
3. Configure retained independently signed approval bundle/public key and reviewed
   source commit. The image bakes `/opt/service-source-commit`; production refuses
   a mismatch or missing/stale evidence. Do not substitute self-generated PASS
   evidence. An isolated evaluation may explicitly select `controlled-pilot`;
   this deliberately omits production promotion/spend requirements, not safety
   permissions. It must not be routed as an approved enterprise service.
4. Use the Compose topology behind TLS ingress. Host port is loopback-only. The
   configured origin must match the browser origin. Do not trust arbitrary
   forwarded headers. Restrict API egress to approved IdP/JWKS/billing endpoints;
   the worker has `network_mode:none`. Configure ingress login/readiness/body/
   connection rate limits and timeouts. Public login must not be an unbounded
   identity-provider or SQLite write amplifier.
5. Image UID 10001 owns local SQLite/result volumes. Verify permissions, volume
   encryption, backup encryption/residency and resource limits. WAL requires local
   POSIX locking, not NFS. No horizontal HA or physical hardware allocation is
   promised. One worker processes jobs serially; reservations are admission slots.
6. Send traffic only after `/health/ready` succeeds with the canonical VQC report,
   real receiver capabilities and valid promotion evidence. Liveness alone is
   not readiness. Monitor request errors, queue age, disk/memory, unknown outcomes,
   contract expiry, outbox lag and billing reconciliation; configure an alert
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
   denial, supported/unsupported work, durable result and real billing statement.
   Set commercial spending ceiling through `/api/customer/{tenant}/spend-limit`
   with `amount` decimal string, uppercase `currency`, unique `command`.
6. Activate only within approved window and accepted service policy. Reserve one
   bounded pilot workload first; do not provision hypothetical 100-instance deals.

The `/ops` commercial action form accepts the same action-specific JSON (without
`tenant`, actor, keys or runtime). `/api/openapi.json` is authenticated. Paginated
list APIs take `limit` (1..100) and `after` (last lexical identifier; audit uses
last numeric cursor). GUI shows first 50; use the API for full exports.

## Billing and operational reconciliation

Run `turing-service billing --config PATH` with the configured machine identity,
or invoke the separately authorised operator billing action. Schedule it through
the approved host scheduler; no polling scheduler with credentials is silently
installed. Deliver usage and commercial outboxes, alert on pending receipts and
reconcile account statements to the receiver. Never convert an ACK into an invoice.

Suspension prevents new admission; operators must inspect/drain active work and
cancellation before resolving it. Membership/project changes are checked during
worker polling, not just at login. Killing work produces an ambiguous outcome,
not an automatically billable completion. `running`/`unknown` on restart remain
quarantined; inspect retained result/custody and execution evidence, then use the
explicit operator resolution with a reason. Never automatically retry an unknown
job under a new ID. Do not release spend authority for a potentially completed job.

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
pilot. Suspected tenant leakage, incorrect verified results or billing duplication:
suspend affected admission, preserve evidence, revoke affected membership/keys,
stop billing delivery, record timeline and contact security/commercial owners.
Recover to a verified state before resumption. Publish a customer-specific service
notification under the approved communications policy. Response/restoration times,
maintenance windows and SLA credits are negotiated; no unsupported availability
promise is embedded in the UI or package.

## Production and publication promotion

`release-check --config PATH [--publication]` verifies the read-only image source,
Ed25519-signed `approval.json`, matching commit, <=7-day freshness, expiry, named
reviewers and SHA-256-bound retained artifact for each required gate. Envelope:
`{manifest:{schema:"turing.promotion.v1",commit,issued_at,expires_at,gates:{...}},signature}`.
Each gate entry has `state:"PASS"`, `reviewer`, `executed_at`, relative `artifact`,
`sha256`; signature is base64 over canonical JSON manifest. Verification public
key is deployment-owned, independent of service signing keys. Runtime, identity,
billing, recovery/load, package and commercial gates are mandatory; publication
also requires `publication_rights`. Missing evidence fails closed. Do not use
unit-test generated fixture approvals in deployment.

Separate acceptance: real canonical package suite/clean install; actual IdP tenant
policy and security review; actual Hermitten invoices/corrections; measured target
load, restart/backup/custody restore; approved offer/rates/support; source/IP/license
and public-claim review. Validate public claims against retained evidence; no
physical QPU, arbitrary scale, validated tariff or customer endorsement is implied.
The command checks evidence, **does not** deploy, create a release tag, upload to
PyPI, change repository visibility or publish company IP. Those actions follow a
separately approved release procedure only after these gates pass.
