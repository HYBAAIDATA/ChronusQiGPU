# HYBA_DATA recovery and evolution

## Current state

This is a provenance-preserving recovery checkpoint, not a completed integration.
The Notion import inventory contains **867 attachment paths**. **Three Python
artifacts** have been recovered byte-for-byte; **864 remain pending**.
The parent import report additionally records four import failures; this inventory
is not proof that the original repository itself was imported completely.

The existing TOE/EUCLID runtime remains authoritative. No replacement intelligence
engine, automatic adapter registration, or production deployment is introduced.
Source files here are archival inputs to integration, not executable qualification.
Do not run the recovered main.py or install recovered binaries before review.

## Layout

- `manifest.json`: every indexed source path and containing Notion page; recovered
  files additionally have byte size and SHA-256. Hashes are not authenticity signatures.
- `source/`: unmodified recovered bytes with their original relative paths.
- `package.py`: standard-library-only reproducible ZIP assembler.
- `test_package.py`: offline validation tests for the assembler.

## Assemble a recovery ZIP

From the repository root:

```sh
python -m unittest recovery.hyba_data.test_package -v
python -m recovery.hyba_data.package --output /tmp/HYBA_DATA.zip
```

The second command intentionally refuses an incomplete collection. To export
the currently recovered subset, explicitly label it partial:

```sh
python -m recovery.hyba_data.package \
  --allow-partial --output /tmp/HYBA_DATA_RECOVERED_PARTIAL.zip
```

To assemble the full collection after obtaining an extracted source tree whose
root contains `hyba_data/`:

```sh
python -m recovery.hyba_data.package \
  --source-root /path/to/extracted-tree --output /tmp/HYBA_DATA.zip
```

The assembler verifies recovered checksum anchors, refuses unsafe/duplicate paths
and symlinks, excludes unindexed files, and includes a manifest of bytes actually
packaged. It reads source only; it never executes recovered modules. Binary
artifacts may be packaged but are not thereby trusted. This version keeps bytes
in memory; use sufficient memory for the input collection. ZIPs have stable entry
order, timestamps and permissions and use stored entries for reproducibility.

**Before publishing additional recovered files:** review licensing and scan for
secrets. The assembler is an integrity/completeness gate, not a secret scanner.

## Evolution contract

Preserve one continuous inquiry across evidence, representation, analysis,
forecasting, alternatives, governed decisions and observed consequences. Domain
adapters supply semantics; execution backends must not silently change meaning.
Keep statistical association, causal evidence, action authorisation, and numerical
exactness distinct. Arithmetic exactness alone does not certify empirical claims.

## Remaining integration gates

1. Recover remaining attachment bytes and reconcile failed imports/documents.
2. Compare recovered files with existing active TOE/EUCLID equivalents; preserve
   provenance without overwriting current source or creating a parallel learner.
3. Map data, runtime, identity, custody, policy and feedback contracts against
   current executable owners; resolve naming conflicts explicitly.
4. Add regression tests before behaviour changes; qualify one end-to-end workflow.
5. Execute domain/backend conformance and isolation/restart tests.
6. Retain CI results and evidence; make only scoped readiness claims.

## Verification scope

Twelve recovery-tool tests were executed in the reconstruction workspace. No
repo-wide suite, recovered application, hardware performance, causal validity,
production readiness, or commercial savings has been qualified by this checkpoint.
