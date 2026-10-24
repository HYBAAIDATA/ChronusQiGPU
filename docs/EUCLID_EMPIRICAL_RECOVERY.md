# Prepared empirical publication recovery

## Contract and limits

This maintenance API completes durable evidence for a publication that already
happened. It never replays the transition, edits custody bytes, resets an audit,
imports memories as identity, grants runtime rights, or claims that the original
request completed before its deadline. It is not an automatic rollback and not
a distributed transaction protocol. One host writer owns an empirical stream.
Stop **all** writers before reconciliation and keep them stopped until finished.
The newest binding is checked again after durable recovery admission; this is
not a cross-process compare-and-swap or a distributed lease.

Normal writes now retain `ADMITTED -> PREPARED -> COMMITTED`. The PREPARED event
binds the exact envelope hash, owner, receipt, prior state hash and prior binding
before touching shared custody. Failed execution still restores local state and
records ROLLED_BACK. A failed preparation restores local state, touches no
custody and quarantines that bridge instance. An uncertain publication remains
quarantined, including after a failed recovery.

## Host procedure

1. Stop the canonical runtime writer and obtain the deployment's independent
   recovery/operator authorization. Normal dispatch permission is **not** an
   implicit recovery grant. No default authorizer is installed.
2. Open the existing shared CompositionRoot and its EUCLID data port. Open the
   existing `HashChainAudit` with corruption quarantine **disabled**. Preserve
   the original key, tenant and owner mapping. Never create a replacement store
   or an empty ledger to force recovery.
3. Inspect the latest binding and its immutable bytes. Approve that exact binding
   ID and SHA-256 envelope digest, with the original owner and a bounded deadline.
4. Call `euclid.capabilities.empirical_recovery.reconcile_publication` with a
   `PublicationRecoveryRequest` and an explicit `recovery_authorizer` backed by
   the real host AL HARAS/operator policy. Its return must be exactly `True`.
   This callback is a host dependency, not an authentication implementation or a
   token-length check. Credentials are never written to the audit.
5. Recovery verifies exact PREPARED and earlier ADMITTED records, the actual
   latest custody bytes, receipt identity, owner and prior committed lineage.
   It rejects stale targets, digest mismatch, conflicting completions,
   rolled-back executions and missing preparation. It durably appends
   RECOVERY_ADMITTED before recording a recovered COMMITTED event, attributed to
   the recovery actor. The original receipt is retained; recovery time is separate.
6. Inspect retained evidence on any exception. A completion append may have
   succeeded before the response failed. A separately authorized retry against
   the same exact target is idempotent. Do not blindly retry the original state
   mutation. A corrupt/truncated audit requires separate forensic recovery.
7. Construct a **fresh** canonical runtime binding and verify its restored state
   and receipts. Existing quarantined bridge objects are never silently reopened.
   Resume only after the authorized maintenance owner approves the outcome.

Legacy orphans without a durable PREPARED intent remain refused: an envelope's
self-reported receipt is not evidence of an authorized prepared transition.
This API does not automatically resolve unknown store outcomes with no visible
binding, divergent writers, or missing/corrupt prior evidence.

## Installed acceptance

`scripts/run_clean_install.py` builds a verification candidate from a clean,
commit-bound checkout. It now builds the existing `hyba-turing-vqc` and
`hyba-kellogg-tensor` owner projects alongside `euclid-engine`, rather than
vendoring their files. It rejects file overlaps, records wheel/member hashes,
resolves dependencies, and installs from that wheelhouse with `--no-index`.
The installed verifier checks original wheel members (except pip-rewritten
RECORD), canonical owner versions, source revision and site-packages isolation.

The expanded verifier exercises real EUCLID -> TuringQuantumOrgan -> SharedTuring
-> VQCPipeline dispatch and shared-custody restart replay. Its recovery fixture
loses a response after the **actual** shared data port publishes; only that
fault and the ephemeral authorization policy are fixtures. The standalone unit
suite instead uses a DiskPort double and is not installed-package evidence.

Run from an authentic clean checkout, using a fresh external evidence directory:

```bash
python scripts/run_clean_install.py --expected-commit "$(git rev-parse HEAD)" \
  --output-dir /absolute/external/fresh-euclid-evidence
```

The orchestrator runs installed regressions and native acceptance normally and
under `-O`. For entirely offline resolution add `--offline --wheelhouse` with a
compatible complete dependency wheelhouse; build tools must already be installed.
The wheelhouse is interpreter/platform-specific, not a universal offline bundle.
Neither this documentation nor focused unit passes establish that the installed
candidate has passed. Read the qualification ledger and retained run evidence.
