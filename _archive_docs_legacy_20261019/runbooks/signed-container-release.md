# Signed container release

## Scope and authority

The signed-container workflow publishes a PYTHIA image to GHCR. It does not deploy
infrastructure, start workers, submit shares, or publish Python/npm packages.
The operator frontend is private and bundled into the image, not an npm release.
Existing consumer and EUCLID Python workflows retain their separate TestPyPI/PyPI
release paths. This runbook is not a production-readiness certificate.

## Gates

1. Run release-boundary regressions, core tests, platform tests, import audit,
   drift sentry, deployment sentry and changed-file style checks on Python 3.12/3.13.
2. Reuse the dependency audit, non-empty CycloneDX SBOM and history secret-scan gates.
   Advisory lookup covers the complete resolved third-party environment; in-tree
   HYBA distributions are explicitly excluded from PyPI advisory lookup and must
   be assessed through code review/tests. No failed audit falls back to a clean
   runner environment.
3. A release requires a strict `vMAJOR.MINOR.PATCH` annotated tag, a valid signature
   verified by GitHub, the exact tagged commit and ancestry on `origin/main`.
   Unsigned/lightweight tags, prerelease names and substituted objects fail closed.
4. The publishing job waits for the `DOCKER_USER` environment reviewer. Its current
   reviewer is `pythiaphi`; self-approval is allowed, so this is not a two-person gate.
5. Publish only the version tag, retaining its immutable image digest. BuildKit emits
   SBOM/provenance attestations; cosign signs the published digest using GitHub OIDC.
   Keyless signing sends the signing identity and artifact digest to a public
   transparency log. Verify that this disclosure is acceptable before approving.

Actions are pinned to commit SHAs; Dependabot proposes reviewed updates for Actions
and frontend dependencies. The Gitleaks binary has a fixed SHA-256 check.

## Prepare a release

- Merge the PR only after GitHub checks and required review are green.
- Confirm protected-branch settings and a reviewed version/changelog; this change
  does not configure branch protection or PyPI trusted publishers.
- Verify environment approvals, registry namespace and tag signer identity.
- Review the signed-tag commit and its entire ancestry. A valid signature does not
  replace authorization review or prove that the signer is a particular release manager.
- With an existing authorized signing key, create and push the release tag:

```bash
git tag -s v1.2.3 -m 'release v1.2.3'
git push origin v1.2.3
```

Replace the example version with the approved version. Do not push this tag merely
to test the workflow: after its gates/approval, it publishes an image.

PR builds use no registry credentials and cannot push. They retain an OCI candidate
archive when all checks succeed. Release builds target linux/amd64 only: the current
vendor ICD installation has not been qualified on arm64. Image byte reproducibility,
floating Docker base images, installed-image runtime smoke tests, and independent
hardware qualification remain separate release work; do not infer them from a build.

## Verify before any production rollout

- Download `signed-container-release` and retain its commit/tag/image digest.
- Verify the signature using the exact repository/workflow certificate identity,
  with issuer `https://token.actions.githubusercontent.com`.
- Inspect the embedded SBOM and provenance for the expected source commit.
- Install/pull by digest, never by `latest`; run a staged control-service health and
  authorization smoke test with live submission disabled and no production pool keys.
- Use the canonical runtime-config identity/approval gates; never substitute a
  generic dry-run flag, assumed credentials or hardware availability.
- No tag push is permission to start actual mining or move funds.

## Rollout and rollback

The deployment platform has not been supplied, so no cluster-specific commands are
invented here. Before deployment, identify the owner, previous stable digest,
configuration revision, database backup/restore procedure and migration compatibility.
Canary a small isolated instance set with live submission disabled. Define an observation
window, error-rate/latency thresholds, heartbeat checks and alert ownership. Promote only
with recorded approval and green smoke/monitoring evidence. On breach, stop promotion,
restore the previous digest/configuration using the deployment platform's reviewed
procedure, verify health and record the incident. Never roll back irreversible data
changes without a reviewed restoration/migration plan.

## Validation record for this PR

Local execution used Python 3.13 and Node 24, against source snapshot
`3365bb3c28fe1aeb672e2309556d5979cb8f5d71`. The branch was created from
`eb15dd16fc1ff45d1e7c7a1e64e89c70a9502a68`; its intervening production-preflight change
was checked for overlap and preserved, not locally requalified.

- Initial targeted release regressions: seven failures reproduced before the fixes.
- Expanded release/authority/publication/sentry regression set: 116 tests passed.
- Frontend: 51 tests passed; TypeScript check and Vite production build passed.
- npm audit: no reported vulnerabilities.
- Resolved Python advisory audit: no known vulnerabilities after upgrading isolated pip;
  the original sandbox pip 24.2 was flagged. CI upgrades pip before auditing.
- Both generated SBOMs were parsed as non-empty CycloneDX documents.
- Gitleaks snapshot scan passed after clarifying an empty scaffold password. No
  scanner rule was relaxed. Full remote Git history still needs the GitHub check.
- Actionlint passed for all five changed workflows; changed-file lint/style passed.
- Core suite stopped at `test_asi_core.py::test_start_schedules_both_loops_without_deadlocking`:
  315 passed, one failed. Do not describe the whole core suite as passing.
- Platform unittest discovery ran 427 tests: six failures and six skips. Failures
  concern governance evidence wiring, Stratum difficulty telemetry and TOE throttle wiring.
- Drift sentry passed. Import audit passed with no findings on a clean local snapshot. Deployment sentry
  still reported two DS07 findings for `python -m build` in the existing resident-Hendrix
  workflow and six warnings; those gates remain blocking until resolved.
- The standalone TURING suite was stopped after a prolonged run without completion;
  no full-suite pass is claimed.
- Docker was unavailable locally. Container builds, multi-version CI, tag verification
  against an actual release, publication, hardware tests and rollout were not executed.

The PR is deliberately draft/blocked pending broader CI and remediation of the failed
baseline gates. There was no package publication, production deployment or live mining.
