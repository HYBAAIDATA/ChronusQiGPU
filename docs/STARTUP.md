# PYTHIA production handover and bring-up runbook


## Startup architecture and finite state contract

`main.py` acquires the boot lock, resolves canonical Stratum identity, starts
the control API, and supervises three production workers:

```text
main.py -> control_api.serve
       -> mining_runtime.py     (agentic-mining)
       -> salamander_engine.py  (salamander)
       -> discovery_runtime.py  (discovery: experiments on a simulated twin only)
```

The production worker topology is process-based inside `pythia-main`:
`control_api.py` starts `mining_runtime.py`, `salamander_engine.py` and
`discovery_runtime.py` as local child processes (`PYTHIA_CONTROL_WORKERS`
selects them). The workers share what they learn through the knowledge
fabric journal (`$PYTHIA_INTELLIGENCE_DIR/knowledge.jsonl`), served at
`/api/v1/knowledge`. It does not mount `docker.sock` and cannot start, stop, or
signal another container. Docker's `on-failure:5` policy watches only the
`pythia-main` supervisor process. The optional `pythia-braiins` and
`pythia-viabtc` Compose profile services are dry-run integration sidecars, not
workers controlled by `pythia-main`; production Host A/B bring-up should start
only `pythia-main` with the respective profile-specific env file.

The allowed states are `disabled`, `armed_no_device`, `starting`, `ready`,
`running`, `restarting`, `stopping`, `stopped`, and `failed`. `running` is
never asserted optimistically: it requires authenticated, fresh heartbeat
evidence. A process can be alive while not ready, and a worker can be ready
without being effective; liveness, readiness, and effectiveness remain
separate fields.

## Review record and merge order

The startup hardening changes were accidentally pushed directly to `main` in
`8487731` and `e7bf9b7`. That was a workflow regression, not a deliberate
exception. This document and the authenticated-heartbeat correction are being
submitted through a review PR; the earlier commits remain traceable by hash,
but GitHub cannot retroactively turn an already-landed tree diff into a real PR
diff. The corrective PR is therefore the review record for the remaining
production boundary and explicitly references both commits.

PR #11 (`TOE 3.5.0`) is still open and unmerged. Merge order:

1. Review and merge the startup/handover correction into `main`.
2. Update `toe/elevation-expansion` from current `main`.
3. Run the full TOE and platform CI together.
4. Merge PR #11 only after the combined checks are green.

The current production control plane does not import the TOE research modules,
so the startup correction does not require TOE 3.5.0 to boot. Updating PR #11
onto current `main` is still required before merging so the review and CI run
against the actual deployment base.

## Four decisions required before host bring-up

### 1. Heartbeat ownership and authenticity

The worker owns its heartbeat file under `PYTHIA_WORKER_HEARTBEAT_DIR`; the
supervisor reads it. Because the file is worker-writable, each binary payload
now contains an HMAC-SHA256 over `worker_id || heartbeat_body`, using the
supervisor-epoch secret inherited by the worker. Invalid or missing HMAC is
reported as malformed evidence and cannot produce readiness.

This authenticates against accidental or unrelated writers. A fully compromised
worker can read an inherited secret and can therefore forge its own heartbeat;
that is outside this file-channel threat boundary. A hostile-worker boundary
requires a supervisor-owned pipe or asymmetric signing key and is not claimed
by this implementation.

### 2. Restart budget behavior

The selected policy is **option A**: after the sixth attempt inside the
10-minute window, the worker transitions to `failed`, the supervisor thread
stops retrying, the control API remains alive, `/readyz` remains a control-plane
health check, and `/ready-to-mine` returns `503` with
`reason=supervisor_degraded`. The Prometheus reason gauges are exported with
one current reason set to `1` and all other reasons set to `0`.

### 3. Directory fsync policy

The code default is **STRICT**. The Windows Docker/WSL2 Compose profile opts
into **LENIENT** explicitly. File fsync and atomic rename remain mandatory.
Only `EINVAL`, `ENOTSUP`, and `EOPNOTSUPP` from directory fsync are tolerated
under LENIENT; unrelated I/O errors still fail the heartbeat. The startup
self-check records filesystem type, configured policy, and recommendation in
`BOOT_AUDIT.log`.

### 4. Cross-host identity

Host A and Host B must use distinct pool worker identities even when they use
the same account. Recommended examples are `account.pythia-a` for Braiins and
`account.pythia-b` for ViaBTC, subject to each pool's username format. Do not
copy one host's complete `.env` file to the other. The canonical identity
commitment includes profile, endpoint, worker identity, and password hash; the
password itself is never emitted.

### Runtime durability and threat notes

The HMAC is over a fixed-length binary body (`magic`, `version`, `epoch`,
`sequence`, and worker monotonic timestamp) prefixed by the UTF-8 `worker_id`;
there is no JSON whitespace or key-order ambiguity. Verification uses
`hmac.compare_digest`, and the worker ID is bound both to the tag and the
expected file path. The secret is inherited through the container environment,
which is visible to Docker-daemon administrators; it is not a defense against
a compromised container or host.

Restart timestamps are persisted under the shared data volume. A supervisor
restart therefore does not erase the worker's five-in-ten-minutes budget.
Budget exhaustion increments `pythia_worker_restart_budget_exhaustions_total`
with a worker label. Identity rotation is intentionally one event per
supervisor process epoch; a supervisor crash loop produces one event per new
epoch and invalidates prior in-flight commitments by design.

The short race test is specifically an atomic-rename test: readers poll the
path while the writer replaces complete files. It does not claim safety for
non-atomic writers or a full SIGKILL-at-every-fsync fault matrix.

## Evidence ladder: do not collapse the stages

| Stage | Proof | Primary source | Failure meaning |
|---|---|---|---|
| Process alive | HTTP `200` from `/healthz` | `pythia-main` HTTP log / Docker health | control process is down |
| Control ready | HTTP `200` from `/readyz`, `reason=ok` | `pythia_identity_verify_ok 1` | identity/HMAC/control API problem |
| Worker heartbeat | fresh authenticated heartbeat | `pythia_worker_up{name=...} 1`, heartbeat phase metrics | worker dead, stale, malformed, or unauthenticated |
| Stratum connected | explicit client connect/auth log | worker logs; `pythia_stratum_connected` when emitted by client | DNS/TCP/TLS/auth failure |
| Job received | `mining.notify` with job id | worker log and job counter | connected but pool is not assigning work |
| Search executed | positive measured work counter/hashrate | worker telemetry and benchmark counters | job received but device/dispatch path idle |
| Share submitted | explicit `mining.submit` write | worker log / submission counter | candidate never reached network submit |
| Share accepted | pool response `result=true` or equivalent | pool client response log | rejected, stale, duplicate, or malformed share |
| Credited | pool dashboard/account credit | pool-side accounting | acceptance was not yet credited |

`mining.notify` is not submission. Submission is not acceptance. Acceptance is
not credit. The handover status remains unproven until the pool-side response
and, where applicable, account credit are observed.

## Bring-up commands

On each Windows Docker Desktop host, use a distinct env file and profile:

```powershell
# Host A
$env:PYTHIA_MAIN_ENV_FILE='.env.braiins'
$env:PYTHIA_BRAIINS_ENV_FILE='.env.braiins'
docker compose -f docker-compose.pools.yml up -d --build pythia-main

# Host B
$env:PYTHIA_MAIN_ENV_FILE='.env.viabtc'
docker compose -f docker-compose.pools.yml up -d --build pythia-main
```

Then inspect, in order:

```powershell
docker compose -f docker-compose.pools.yml ps pythia-main
curl.exe -fsS http://localhost:8377/healthz
curl.exe -i http://localhost:8377/readyz
curl.exe -i http://localhost:8377/ready-to-mine
curl.exe -fsS http://localhost:8377/metrics

docker compose -f docker-compose.pools.yml logs --since=10m pythia-main
```

Do not treat `/ready-to-mine=200` as pool acceptance. Confirm the explicit
Stratum and pool-side evidence ladder above.

## Rollback and stop procedure

For an identity conflict, wrong worker, unexpected endpoint, or first unsafe
submission:

```powershell
docker compose -f docker-compose.pools.yml stop pythia-main
# The optional dry-run profile sidecars are not part of the live worker path.
```

Stopping `pythia-main` stops the supervisor and its worker children; killing a
child alone invokes the bounded restart policy. Preserve `BOOT_AUDIT.log` and
container logs before removing volumes. Never edit credentials while the
supervisor is running; change the ignored env file, validate the identity
conflict gate, then start the affected host only.

## Schema and observability stability

The version discriminator is an envelope field, not a URL convention:
`schema_version` is present in `/healthz`, `/readyz`, `/ready-to-mine`, and
`/api/v1/mla1517/status`. Consumers must reject unknown major schema versions.

The minimum bring-up metrics are:

- `pythia_worker_up{name=...}`
- `pythia_worker_hashrate{name=...}`
- `pythia_ready_to_mine{reason=...}`
- `pythia_heartbeat_write_duration_seconds_*{worker=...,phase=...}`
- `pythia_identity_verify_ok`
- `pythia_boot_audit_lines_total`
- `pythia_boot_audit_last_write_timestamp_seconds`

The short PR chaos suite only probes concurrent authenticated reads/writes and
epoch-vs-regression semantics. It is not a 10-minute SIGKILL-during-each-fsync
matrix. The long fault-injection suite remains a nightly/pre-release
responsibility and must run on the target CI platform before making a stronger
availability claim.

## Verification and reversion boundary

The rollback commands above are documented from the Compose contract; they have
not been executed on a Windows Docker Desktop host in this workspace. The PR
review must include that host test. The direct-to-main commits `8487731` and
`e7bf9b7` have no PR-level revert record; if either is found defective, revert
them explicitly with a reviewed follow-up commit or use the corrective PR.
