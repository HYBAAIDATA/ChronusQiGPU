# Integrated THESEUS shard custody — bounded single-erasure recovery

**Implementation:** `src/chronus/storage/protected.py`, exported from `chronus.storage` and reachable from the existing canonical `ProductionTriad.protect_payload` / `recover_protected_payload` methods. This is production-shaped software storage, **not yet independently production-qualified**.

## What actually operates together

The existing `chronus.storage.erasure.encode_stripe` produces 2–32 immutable shard byte strings and one XOR parity value. `ProtectedTheseusService` writes shards to the operator-selected filesystem using exclusive-file creation and fsync. It records the parity-bearing, SHA-256-identified manifest through the **existing `DurableTheseusService`** and commits a THESEUS custody-journal event. The manifest, not an unverified file path, is the authoritative record of the shard SHA-256 digests, input hash, tenant namespace, boundaries and parity.

A caller can restart the process, construct a fresh `ProductionTriad` against the same SQLite/WAL database, and recover bytes after one named shard file has actually been deleted or changed. A second erasure, damaged parity, tenant mismatch or untrusted symlink fails closed. Recovery is byte-identical, verified against the original full-payload SHA-256.

### Canonical API

```python
from chronus.triad import ProductionTriad

triad = ProductionTriad('/secure/theseus.sqlite3')
receipt = triad.protect_payload('tenant-001', b'actual bytes', '/secure/theseus-shards', shard_count=4)

# An independently reopened triad can use the original receipt:
reopened = ProductionTriad('/secure/theseus.sqlite3')
original = reopened.recover_protected_payload(receipt, '/secure/theseus-shards')
```

The OVID `put`/`materialise` contract is unchanged; this is an additional protection surface under THESEUS authority, **not a competing custody backend**. The existing `ProductionTriad.production_posture()` and signed release admission remain authoritative; this extension cannot approve releases or grant security authority.

## Independent correctness tests and provenance

Tests committed in `tests/test_protected_theseus.py` instantiate the real maintained `DurableTheseusService`, exercise restart and shard deletion, single-corruption repair, multiple-failure refusal, tenant separation and protection against symlinks and conflicting writes. These must be executed in a full maintained checkout before representing them as proven complete-repository tests.

A separate isolated test environment executed ten corresponding file-deletion, restart, isolation and integrity checks using a SQLite-backed **interface test double**, and five benchmark-reconciler contract checks (15 passing tests total). A genuine UCI Wine observational `.npy` source (SHA-256 `09af9db3ce2a52b3f168d5d9eb1d4d4ceba584fad9e0e9aba63ff536c192c6a6`) also survived a real shard-file deletion and fresh-process-style reconstruction in that local harness. This does **not** assert full-repository test verification.

## Failure envelope and evidence boundaries

- The manifest and all parity are stored with the same SQLite/WAL database. Losing the entire database **cannot** be repaired from the shards alone.
- A single missing or corrupt shard can be reconstructed **in memory**; the function does not silently rewrite damaged files. Remediation requires an authorised policy and separate audit.
- The caller must retain the `ProtectedReceipt`. The API deliberately does not invent an untrusted tenant-wide discovery or create a new system of record.
- Creating an exclusive shard file is crash-detectable but directory-level power-loss guarantees, independent fault domains and raw physical IOPS are **not measured**.
- File and manifest SHA-256 digests are integrity anchors, not actor authentication. AL HARAS must authorise privileged restoration paths and THESEUS remains responsible for custody.
- Cross-process/restart recovery is distinct from a verified physical power-loss event.

## Benchmark reconciliation wired to the existing records

`scripts/reconcile_benchmarks.py` accepts an operator-curated list of actual JSON evidence artifacts with full SHA-256, checks every file byte and its **embedded source commit**, classifies missing, modified, stale and historical/unbound records, and produces a never-overwritten reconciliation report. It cannot silently interpret a successful reference script as physical performance or promote a held `RS-WORK` claim.

Example input structure (replace both digest values with the real measured artifact and its exact source commit):

```json
{
  "schema": "chronus.benchmark.reconciliation-input/1",
  "source_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "artifacts": [
    { "path": "evidence/reference.json", "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" }
  ]
}
```

Run with `python scripts/reconcile_benchmarks.py --root . --manifest /secure/inputs.json --expected-sha $(git rev-parse HEAD) --output /secure/reports/reconciliation.json`. A result `all_source_bound=true` is source reconciliation **only**, never production qualification. Historical benchmark outputs missing a SHA must remain `UNBOUND_HISTORICAL`; no fabricated current evidence.
