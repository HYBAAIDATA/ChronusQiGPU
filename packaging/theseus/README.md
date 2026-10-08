> Publication naming is owner-approved under `hyba-<system>-<capability>`. Qualification and registry/upload approval remain separate and unverified.

# THESEUS publication candidate — hyba-theseus-storage 1.0.0

**Prepared, not qualified or published.** The public distribution name remains
proposed until the owner decision is recorded. First-public version: **1.0.0**.

## Canonical implementation and compatibility

This distribution owns **`aethel/**`**, copied byte-for-byte from the frozen
repository checkout during the build. No domain implementation is forked,
renamed, simplified or rewritten. Existing imports remain canonical.

THESEUS retains durable custody, authentic envelopes, replica/journal recovery,
phyllotaxis placement and producer-contract admission. Aethel's existing OVID
transform helpers and shared Chronus/triad adapters remain bundled because the
canonical package initializer exports them; their authority is NOT transferred
to THESEUS. Hardware and external intelligence integrations are not certified
by installing this package. Optional absent integrations must remain explicit.

The proposed distribution is named `hyba-theseus-storage`, not `aethel`. Aethel's existing
`__version_source__` may consequently remain `source_fallback`; the build checks
actual distribution metadata separately and does not relabel that flag. Any
future alias/distribution migration needs its own parity proof.

CLI (preserved): `hyba-theseus --help` invokes the existing `aethel.__main__:main`.
The existing `python -m aethel` interface remains available.

## Build and installed verification

From a full checkout of a frozen candidate, with build/twine tooling installed:

```bash
python packaging/storage-release/build_and_verify.py --product theseus
```

The OVID build requires the exact same-candidate THESEUS build first. The script
builds wheel and sdist, checks metadata and file ownership/identity, installs
outside the repository, imports shipped modules, executes the existing CLI,
then runs canonical custody/projection voyages in separate fresh processes.
Output is in `packaging/theseus/dist/`. Required product suites, registry
installation smoke, owner naming decision and publication checks are separate;
no local smoke alone yields production readiness.

## Publication sequence (not yet executed)

Freeze candidate → required suites with zero skips → installed wheel/sdist
verification → custody/replay and negative voyages → identity approval →
TestPyPI OIDC upload → clean registry install/import/CLI/voyage → promote the
same verified archives to PyPI → clean PyPI verification → evidence-linked
GitHub release. See `docs/STORAGE_PUBLICATION_PREPARATION.md`.
