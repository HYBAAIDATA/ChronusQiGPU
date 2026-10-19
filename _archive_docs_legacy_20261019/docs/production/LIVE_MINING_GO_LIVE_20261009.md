# PYTHIA LIVE MINING GO-LIVE — 9 October 2026

**Owner intent:** live submission is authorised for deployment after the fail-closed
runtime checks pass. Authorisation to build/enable the capability is NOT evidence
that a pool share was accepted or that the current source is production certified.

## Canonical path — never use the legacy bridge as certification

control_api / supervisor -> mining_runtime.py -> M3PythiaProductionMiningCoordinator
-> AL HARAS policy -> PYTHIA candidate SHA256d/target verification -> THESEUS
custodied candidate/verified proof -> Stratum mining.submit -> pool result.
Replays, stale jobs, duplicate shares, TCP write ambiguities and failures
must never be counted as accepted. The legacy mining/stratum_bridge.py
one-share smoke only qualifies that legacy bridge, not this path.

On this branch canonical M3 coordinator refuses live submit unless strict M3
is enabled, a configured gate is bound and no prior M3 block exists.
The control API requires an actual JSON boolean for live_submit.enabled and
rejects enablement without PYTHIA_M3_REQUIRED=1. Direct --submit refuses
startup without strict M3.

## 1. Precondition — full qualified Mac deployment

- Clean exact approved git revision and installed distribution artifacts; no
  overlapping wheel ownership. Read APPLE_M5_TRANSFER_20261009.md first.
- Mac M5 runtime/device evidence independently verified. CPU is permitted
  only when honestly labelled CPU; never claim M5 acceleration from CPU hashing.
- GitHub jobs have executed, not failed at zero steps. Complete M3, EUCLID,
  installed-package and attack regressions on exact-head source.
- Capture pre-cutover backups of SQLite/CAS/THESEUS custody and configuration.
- Confirm no duplicate supervisor, obsolete checkout path or stale lock.
- Confirm AL HARAS policy, tenant/actor and token admission, independent
  monitoring, incident-stop capacity and bounded operational exposure.

## 2. Secure M3 configuration and one-time tenant provision

Use the operator's macOS application-state volume (not /tmp) for the SQLite,
CAS and HMAC custody store. Set in the service secret manager:

    PYTHIA_M3_REQUIRED=1
    PYTHIA_STORAGE_DB=<persistent SQLite path>
    PYTHIA_STORAGE_ROOT=<persistent CAS path>
    PYTHIA_STORAGE_CUSTODY_ROOT=<persistent THESEUS path>
    PYTHIA_STORAGE_TENANT=<approved slug>
    PYTHIA_STORAGE_INTEGRITY_KEY_HEX=<32+ bytes hex, secret>
    PYTHIA_STORAGE_CUSTODY_KEY_HEX=<different 32+ bytes hex, secret>
    PYTHIA_M3_ACTOR=<authorised actor>
    PYTHIA_M3_AL_HARAS_TOKEN=<valid tenant-scoped subscription token>

These do not replace the canonical AL HARAS guardian's independent
configuration, policy or audit persistence requirements. Do not print secrets.

With the operator's authorisation, before starting the strict worker:

    .venv-m5/bin/python scripts/provision_m3_tenant.py \
      --tenant "$PYTHIA_STORAGE_TENANT" \
      --max-records 1000000 --max-bytes 10000000000 --approve-tenant

This is an explicit idempotent storage-admission action, NOT a replacement for
AL HARAS policy validation. The runtime guardian evaluates live lease and proof
requests; a bogus token fails closed. Do not auto-provision unknown tenants.

## 3. Real pool identity and shadow evidence

Set a genuine pool account.worker identity and password using the approved
secret manager, along with the current pool endpoint, network and backend
policy. Keep one initial pool, since a pool switch invalidates approval.
Do not put worker passwords or AL HARAS tokens in argv, logs or GitHub comments.

Start the canonical supervisor with live approval disabled. Require one live
Stratum subscription, authorised worker, fresh jobs/target, independent
SHA256d candidate verification, stable worker heartbeat, correct backend
provenance, no storage/AL HARAS unhealthy state, and durable restart/replay.

## 4. Arm exactly this identity through the operator API

The secure Runtime Control interface uses the operator credential for
PUT /api/v1/config (not the separate privileged mining subscription token).
Once steps 1–3 pass, arm with explicit JSON boolean:

    {"live_submit":{"enabled":true}}

The control plane derives approval bound to the active pool endpoint+worker.
The worker re-reads config and may begin sending real candidate shares after
full M3 proof custody and current-job checks. Alternatively a directly launched
canonical worker using --submit requires the same M3 prerequisites; avoid
simultaneous supervisor and direct worker processes.

**Do not set blanket HYBA_* bridge environment gates to bypass the canonical
approval path.** Those belong to the legacy smoke bridge and are NOT canonical
production proof. Use one approved pool identity with a bounded trial duration
and immediate-stop mechanism.

## 5. Acceptance evidence and stop conditions

Record actual mining.submit socket write evidence, matching session/job and
candidate hash, independent proof and custodied AL HARAS authorisation,
pool's literal accepted/rejected response, and the external pool-side account
receipt if available. No socket write => NOT_SUBMITTED; post-write disconnect
=> OUTCOME_UNKNOWN, not automatically retryable or ACCEPTED.

Disable live_submit (enabled:false) and stop the operator worker on: missing
HMAC custody/projection/replay, AL HARAS denial, stale parent, unknown target,
backend fallback, SHA256d disagreement, persistent disconnect, unbounded
energy/cost, or unreviewed intelligence/ontology changes. Revoke config before
pool failover; reauthorise exact new identity separately.

## GO / NO-GO

Source-level patches and historical ViaBTC connections do not prove
deployment readiness. Until same-head tests, installed Mac stack and runtime
M3/AL HARAS/THESEUS voyage pass: **NOT_CERTIFIED / QC_HOLD**.
A real production-share success is only a verified pool acknowledgement
on a real approved account; network receipts are never invented.
