# Target-filesystem storage reference — implementer closeout

**Classification:** Bounded software measurement on supplied real source bytes. **Not** block-device IOPS, power-loss durability or independent production qualification.

## Why this code exists

The original production-readiness checklist asked for physical storage evidence, not merely an in-memory reference benchmark. The existing `scripts/benchmarks/storage_closeout.py` deliberately uses a temporary SQLite database and generated reference inputs; the new `benchmarks/qualify_storage_performance.py` uses SHA-256-pinned **operator-selected existing files** on an **explicit target filesystem**. No test payloads are generated in the benchmark.

## Correct contract

Inputs are declared through `chronus.real-workload-manifest/1` and validated using the existing safe `benchmarks.real_workload_benchmark` discovery/hash contract. Files are not changed. Duplicate content is rejected so repeated content-addressed storage cannot masquerade as multiple real writes. The temporary SQLite WAL database is placed in the user-selected target directory, and removed after an independently reopened THESEUS service verifies every original byte. Timing covers application calls, not a physical disk controller.

### Usage

Install the maintained project first; run from the repository root:

```bash
python -m benchmarks.qualify_storage_performance \
  --manifest /secure/operator/manifest.yaml \
  --target-directory /secure/device-mount/chronus-benchmark \
  --output /secure/evidence/storage-app-measurement.json
```

The target directory must already exist and cannot be a symlink; it must be access-controlled because the benchmark temporarily persists copies of genuine source bytes. Evidence files must be new and may not overwrite any source/manifest. The example source manifest is `benchmarks/data_manifest.example.yaml`; populate it with real SHA-pinned data. Public observed datasets can be prepared with `scripts/benchmarks/prepare_public_uci_data.py`, following `docs/production/PUBLIC_UCI_BENCHMARK_20261116.md` for provenance and restrictions.

### Output

The report contains exact source commit when available, input SHA and source classification, bytes stored, selected directory and `st_dev` identifier, Python/SQLite environment, per-source distinct write/read application latencies, p50/p95/p99, measured call rate, checkpoint and fresh-reopen byte-identity evidence. It does not infer the physical drive model from a filesystem path or fabricate hardware metrics.

Fields `physical_device_iops`, `power_loss_recovery`, `sustained_soak`, `independent_attestation` and hardware model remain null; `production_qualified=false`. An app-call count divided by wall-clock time is *not* raw NVMe/SSD IOPS. Two or sixteen files cannot establish a sustained-load SLA. No claim in `claims/register.json` is promoted.

## Tests and acceptance

Run `python -m pytest -q tests/test_storage_device_qualification.py` and the existing real-workload, custody, triad and PULVINI contracts. These contract tests use explicitly marked nonproduction fixtures and cannot furnish runtime, hardware or performance evidence.

**Remaining before production admission:** get a known, independently identified target device; measure raw block-level activity, compare like-for-like baselines, run sustained/cold/warm workload tests, verify crash and power-loss recovery with an appropriate fault model and safety controls, collect signed evidence tied to the current commit, and pass the existing exact-SHA release gate. Restore CI execution and require branch-protection CODEOWNERS enforcement separately. Do not replace the stronger current release verifier with an echo-qualified shortcut.

## Preservation of authority

THESEUS owns durable custody and replay; OVID owns representation transforms; Chronus executes; PULVINI formal maths is owner-controlled; AL HARAS owns approval and attestation. No mining/quantum authority changes were made.
