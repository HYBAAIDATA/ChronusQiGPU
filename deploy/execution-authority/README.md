# Bounded execution service — candidate, not production admission

Use `chronus.service.execution_app:app` for the minimal CPU execution surface.
The general `chronus.service.app:app` also exposes the new endpoints, but its
legacy workload/tensor/admin paths do not inherit these bounds or custody.
Do not expose those legacy paths as an admitted bounded execution service.

The dedicated service requires a POSIX host with process groups, file locking
and `resource` limits. Windows is unavailable for this execution authority.

Configure these values through the target's local secrets/configuration system:

| Variable | Required value |
| --- | --- |
| `CHRONUS_EXECUTION_STATE_PATH` | Absolute path on customer-controlled persistent local storage, e.g. `/var/lib/chronus/execution.sqlite3` |
| `CHRONUS_EXECUTION_KEY_FILE` | Local file containing exactly 32 raw customer-supplied key bytes; restrict permissions to the service identity |
| `CHRONUS_TENANT_TOKENS` | JSON map from tenant IDs to distinct strong bearer tokens, or configure the existing stable local JWT identity path with `CHRONUS_JWT_SECRET` |
| `CHRONUS_EXECUTION_CONCURRENCY` | Host-wide concurrent epoch limit, default 2 |
| `CHRONUS_EXECUTION_WALL_SECONDS` | Maximum per-epoch wall budget including process startup, default 30 |
| `CHRONUS_EXECUTION_MEMORY_BYTES` | Per-worker address-space limit, default 2147483648 |

Run the approved immutable artifact using:

```sh
uvicorn chronus.service.execution_app:app --host 127.0.0.1 --port 8000 --workers 1
```

Bind/expose through the target's approved local TLS ingress. No external control
plane is required. The application does not implement TLS termination, HSM/TPM
attestation, container isolation, OS tenancy, device certification or WORM storage.
Customer-supplied file keys are not a claim of HSM-resident keys. Tenant IDs,
journal event types, ciphertext lengths and custody metadata remain visible.

All API processes sharing the same state path must use the same persisted
execution policy and key. Policy/key changes fail closed. Stop/drain every worker
before an approved migration; preserve and verify the old key, database, WAL and
policy root for recovery. Do not delete the policy file to change a running limit.
Locks are host-local; this is not a distributed quota or an NFS lock guarantee.
The service account must exclusively control the state directory and lock files.
Host/service/container controls must reap the entire process tree if the API host
is killed; application timeout handling alone is not a host-crash supervisor.

## Synchronous contract

`POST /api/v1/execute` accepts:

```json
{
  "workload": {
    "tenant_id": "customer-tenant",
    "workload_type": "scaling.v1",
    "payload_bytes": "base64:eyJpbmRleCI6MTB9",
    "backend_preference": "python-math-reference"
  },
  "wall_seconds": 10
}
```

The authenticated tenant must match the request. Supported bounded CPU contracts:
`EXACT_Q5_ALGEBRAIC`, `scaling.v1` / `LUCAS_PV_SCALING`, `METALLIC_SCALE`, and
`SHA256D_NONCE_SEARCH`. Mining search requires one worker and no child-local
`store` option. This endpoint does not submit shares to a pool. Physical backends,
remote execution, arbitrary operations and stateful child storage are rejected.

The HTTP request remains synchronous until execution and durable terminal custody
finish. A response has `COMPLETED`, `FAILED`, or `TIMED_OUT`, a run ID, input SHA-256,
backend identity, admission lineage, elapsed seconds and `receipt_object_id`.
HTTP 200 reports the terminal receipt; callers must inspect its status.
429 means no slot was available. 503 means custody/policy/supervision unavailable;
never retry a possibly executed request automatically. There is no exactly-once
or idempotent retry guarantee. If a client disconnects, bounded work may finish
and commit its receipt. A host crash after admission may leave an unresolved
admission; do not automatically treat it as completed or replay it as new work.

`GET /api/v1/execute/status?receipt_object_id=<sha256>` requires the producing
tenant's identity. `GET /api/v1/execute/replay` takes the same query and checks
ciphertext integrity, authenticated decryption, admission lineage and journal
continuity. Replay is read-only custody verification, not recomputation, semantic
validation, a checkpoint restart or proof of external pool acceptance.

Ingress rejects encoded bodies above 4 MiB, including chunked bodies. Decoded
payloads are limited to 1 MiB and worker result envelopes to 512 KiB. CPU/address
space/file limits and process termination bound the worker. Custody I/O and
shutdown have their own overhead outside the epoch execution deadline.

AES-256-GCM uses a fresh random 96-bit nonce per record and binds tenant identity
and envelope schema as authenticated data. Worker scratch results are encrypted
when customer-key custody is configured. SQLite THESEUS stores ciphertext and a
hash-chained journal. This is local durable custody with tamper detection, not an
independently anchored immutable ledger or geo-replication guarantee.

The TypeScript client is `frontend/lib/execution-authority.ts`. It uses this exact
HTTP contract and checks the submitted byte digest; it is not an integration
with an absent `HybaMiningEngine`.

## Live mining policy

The canonical `ChronusRealMiningEngine` retains SHA-256d target verification.
Geodesic Tensor scheduling, partial folded residency and reconstruction checks
now run inside its lane scheduler. Every output is checked to be exactly the
original lane permutation. Tensor operations do not decide share validity or
remove nonce coverage. The reference execution path is explicit CPU software.

Pool connection is denied unless `CHRONUS_ALLOWED_POOL_ENDPOINTS` is a JSON array
containing the exact canonical endpoint, including scheme, host and port. No
provider or external endpoint is implicitly approved. Both gateway RPC methods
independently verify submissions against current work before any bytes are sent.

Arming requires local encrypted THESEUS custody:
`CHRONUS_MINING_TENANT_ID`, `CHRONUS_MINING_KEY_FILE` (32 raw bytes), and
`CHRONUS_MINING_CUSTODY_PATH` (persistent SQLite path). CLI sessions additionally
require `CHRONUS_MINING_SUBMIT_ARMED=1`, a nonempty
`CHRONUS_MINING_APPROVAL_REFERENCE`, and positive
`CHRONUS_MINING_ACCEPTED_SHARE_TARGET`. These are operator configuration inputs,
not an invented external authorisation/attestation service. Unarmed sessions do
not search or submit. New connections disarm; the explicit CLI configuration may
arm the newly handshaken session. Correlated literal pool acknowledgements alone
count toward the accepted target. Outstanding submissions reserve target capacity;
reaching the target disarms and stops the session. Arming, authorised candidates,
acknowledgements and shutdown are durably recorded with encrypted payloads.
No live pool has been contacted for this change.

## Admission still required

Before the first sovereign workload, bind the exact approved input/output
contract, owner, jurisdiction, backend, target host and immutable artifact digest.
Run the Notion Workflow 01 and 05 checks on that target: isolation/security review,
local identity/customer keys, immutable retention, sustained execution, backup,
restore/replay, upgrade/rollback rehearsal, incident path and owner admission.
Physical devices require their own device-bound certification. Local tests and
loopback HTTP evidence cannot confer sovereign production status.
