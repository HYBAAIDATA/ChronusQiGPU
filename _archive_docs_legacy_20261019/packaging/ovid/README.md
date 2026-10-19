> Publication naming is owner-approved under `hyba-<system>-<capability>`. Qualification and registry/upload approval remain separate and unverified.

# OVID publication candidate — hyba-ovid-data-organisation 1.0.0

**Prepared, not qualified or published.** The public distribution name remains
proposed until the owner decision is recorded. First-public version: **1.0.0**.

## Canonical implementation and compatibility

This distribution owns **`hyba_db/**`**, copied byte-for-byte from the frozen
repository checkout during the build. No domain implementation is forked,
renamed, simplified or rewritten. Existing imports remain canonical.

OVID retains organisation, versioned transform lineage, tenant-scoped queries
and indexes. `hyba_db` is a rebuildable projection; THESEUS remains the durable
system of record. This package consumes `hyba-theseus-storage==1.0.0` rather than
shipping another copy of `aethel`. TheseusFileCustody is an existing protocol
adapter, not a competing custody implementation.

The existing `pythia-storage-db-gate` CLI is preserved unchanged. Its help output
or package existence is not a successful production gate. Pending producer
semantic revalidation remains pending; this release tooling never inserts an
always-PASS producer validator.

## Build and installed verification

From a full checkout of a frozen candidate, with build/twine tooling installed:

```bash
python packaging/storage-release/build_and_verify.py --product ovid
```

The OVID build requires the exact same-candidate THESEUS build first. The script
builds wheel and sdist, checks metadata and file ownership/identity, installs
outside the repository, imports shipped modules, executes the existing CLI,
then runs canonical custody/projection voyages in separate fresh processes.
Output is in `packaging/ovid/dist/`. Required product suites, registry
installation smoke, owner naming decision and publication checks are separate;
no local smoke alone yields production readiness.

## Publication sequence (not yet executed)

Freeze candidate → required suites with zero skips → installed wheel/sdist
verification → custody/replay and negative voyages → identity approval →
TestPyPI OIDC upload → clean registry install/import/CLI/voyage → promote the
same verified archives to PyPI → clean PyPI verification → evidence-linked
GitHub release. See `docs/STORAGE_PUBLICATION_PREPARATION.md`.
