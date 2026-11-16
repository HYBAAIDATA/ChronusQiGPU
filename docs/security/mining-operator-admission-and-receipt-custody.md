# AL HARAS mining administration and THESEUS receipt custody

**Added 16 November 2026 · Source-integrated, production NOT QUALIFIED**

The existing mining administration API controls a shared in-process
`MiningAdminEngine`. Tenant credentials alone must not enable mutations or
disclose global telemetry, and a loopback mining rehearsal is not proof of
external pool acceptance.

## Wired admission boundary

`src/chronus/service/mining_operator.py::get_mining_admin_operator`
is the enforced FastAPI dependency on **all eleven** routes beneath
`/v1/mining/admin` (nine POST, two GET). It delegates identity validation
to the maintained `get_current_identity` in the AL HARAS JWT middleware.

A request passes only when:

1. The bearer token is a **verified JWT**, not a legacy static tenant token,
   and the code is not in the `CHRONUS_DEV_JWT_PERMISSIVE` mode.
2. The JWT has the exact `system_admin` role. A `tenant_admin`,
   `operator`, `developer` or legacy `admin` alias cannot become this
   global mining authority merely by naming a role.
3. `sub` matches the explicit administrator subject allowlist.
4. The authenticated `tenant_id` matches the configured mining-owning tenant.
5. A stable `CHRONUS_JWT_SECRET` (minimum 32 characters) exists.
6. A valid admission event is synchronously committed into the configured
   THESEUS custody database, and its tenant journal verifies. Missing or
   corrupted custody rejects the action before its handler executes.

Required deployment settings (no default authority):

| Setting | Requirement |
| --- | --- |
| `CHRONUS_JWT_SECRET` | Stable, secret, sufficiently strong JWT signing key; must be provisioned through a real secrets manager in production |
| `CHRONUS_MINING_ADMIN_TENANT_ID` | The one tenant permitted to administer this shared engine |
| `CHRONUS_MINING_ADMIN_SUBJECTS` | JSON array of approved authenticated JWT subject IDs (for example `["operator-1"]` in a test only) |
| `CHRONUS_MINING_ADMIN_CUSTODY_PATH` | Persistent, access-restricted local THESEUS SQLite database path |
| `CHRONUS_DEV_JWT_PERMISSIVE` | Must be disabled; a value of `1` blocks this authority |

`MINING_ADMIN_OPERATOR_ADMITTED` records actor, tenant, HTTP method,
route and timestamp. **This is an admission record, not an action-completed
receipt, live mining result or pool acknowledgement.** Endpoint-specific
mutation/event/rollback outcomes remain separate requirements; the mining
admin facade is **not** the canonical live Stratum execution plane.

The two Kubernetes deployment manifests now use `/health/ready` for
readiness; neither relies on a fake `cluster-internal-token` or mining
telemetry. Health readiness is not a production certificate.

## Signed receipt durability

`src/chronus/security/receipts.py::ReceiptLog` remains a deliberately
in-memory signature-verifying compatibility class. The new
`src/chronus/security/durable_receipts.py::DurableReceiptLog` binds this
signed contract to **THESEUS** via `DurableTheseusService`, versioned
`AL_HARAS_SIGNED_RECEIPT_V1` events, tenant + stream identification,
SHA-256 public-key fingerprint, Ed25519 verification and strict sequence and
predecessor checks.

It requires the trusted public key to be provided by an independent
authenticated key source, not inferred from the stored receipt. Private keys
are **never** stored in THESEUS by this module. Each append is committed to
durable custody before the local chain advances. Fresh instances reconstruct
the full sequence from THESEUS and reject malformed/tampered records.

`src/chronus/core/facade.py` qualification Gate G2 now performs a local
fresh-reopen, independent signature check, wrong-key test and tamper
negative check in a temporary custody database.

### Current limitations

- One authorised writer per tenant/receipt stream: this interface does **not**
  claim atomic cross-process append/consensus, remote HSM key custody, WORM
  storage or cross-region replication.
- Local `DurableTheseusService` uses SQLite/WAL and is not a distributed DB.
  Issue #82 remains a qualification gate for startup and multi-process use.
- The legacy `src/chronus/access_control.py` remains **NOT AUTHORITATIVE**
  and is not imported by this admission path. It contains unbound/unsafe
  role and exposure implementations tracked in issue #91. Do not route
  operational authorization through it.
- `MiningAdminEngine` is not `ChronusRealMiningEngine`; no "start"
  administrative response proves work hashes executed, and no loopback
  response proves live pool acceptance.
- Unit/integration tests are committed, but CI steps have been observed
  failing before execution. Exact-head success must be obtained and
  attributed, not inferred.
- No production authorization is configured in the repository.

## Verification and regressions

```bash
python -m pytest -q tests/test_durable_signed_receipts.py \
  tests/test_mining_admin_admission.py tests/test_mining_loopback_truth.py \
  tests/test_mining_admin.py tests/test_patroclus_myrmidon_master.py
python -m pytest -q tests/test_receipts.py tests/test_triad_production.py
```

The existing CI matrix runs `pytest` across the test tree and `ruff` over
`src/chronus/security`, `src/chronus/service`, `src/chronus/core` and
`tests`. A green current-head run is still required. The controls remain
evidence-gated until then.

Authority references: [canonical authority register](https://app.notion.com/p/3f0bcc6fa49981c68659c178cbb72a19);
[Notion mining readiness](https://app.notion.com/p/419bcc6fa49981cf9e6cecfa7a838b70).
