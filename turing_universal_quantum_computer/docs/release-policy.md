# Release policy and approval evidence

## Quality standard

Optimize for rigor, clear interfaces, excellent defaults and low cognitive load,
not organizational name-dropping or an elaborate empty architecture. Every
promised feature needs a working path, a failure contract, a test, a useful
example and an accurately scoped explanation. A public claim must be traceable
to an implementation and appropriate evidence. Research hypotheses remain labelled.

## Contract freeze and versioning

Review public signatures, schema versions, defaults, capabilities and exception
semantics. Preserve documented behavior within a release line; announce
intentional incompatible changes through the approved version/deprecation policy.
Do not remove or reinterpret public names silently. Maintainers must publish an
actual supported-version/security-fix window before promising one; none is
fabricated here. Existing metadata is not an authorization to republish 1.0.0.

## Decision and blockers

- **Blocking:** incorrect mathematics, wrong source/observable/parameter binding,
  unverifiable or mismatched artifacts, data/credential exposure, unexplained
  regressions in an advertised path, lifecycle leaks in the release scope,
  missing required qualification or unresolved critical security findings.
- **Needs explicit disposition:** known out-of-scope defects and platform or
  integration limitations; document narrowed scope, affected users and risk.
- **Not equivalent to approval:** passing focused tests, presence of CI YAML,
  a successful build, a draft manuscript, or a signature on an untested artifact.

Run the complete applicable existing release workflow. Do not mark unrun security,
license, mutation, long-soak or dependency-minimum checks passed. SAST/SCA findings
need severity/impact review and accountable disposition. SBOM/attestations must
be generated from the exact resolved build, not a manually assembled dependency
list. Public claims and redistribution/license permissions need review too.

## Immutable candidate record

Retain source commit/tag, clean source state, lock and exported-resolution hashes,
builder/tool versions, artifact hashes, wheel/sdist content parity, interpreter/OS,
consumer/JUnit results, security/SBOM/attestation references, known limitations,
reviewers and approval timestamps. Sign or attest through the existing approved
release mechanism where supported. A signed tag alone does not prove a wheel
was built from that tag. SOURCE_DATE_EPOCH should come from the actual candidate
commit for repeat-build studies; normalized file equality is not automatically
byte-for-byte reproducibility.

## Publish and verify

After approval, publish the already tested artifacts through the existing gated
workflow. Download/install the candidate from its intended registry in a fresh
environment, verify expected hashes/metadata/imports and a representative native
computation, then run downstream consumer checks. A private local install does
not prove registry availability. Add a real DOI only after archival creation.

Withdraw/yank/supersede when mathematics, security, compatibility or artifact
integrity is materially broken. Do not overwrite a version or silently replace
its wheels. Announce affected versions, impact, workaround and replacement;
rehearse rollback separately from registry withdrawal. Post-release verification
and human approval remain open until actual evidence exists.
