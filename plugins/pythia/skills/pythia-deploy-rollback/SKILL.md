---
name: pythia-deploy-rollback
description: Apply the Enterprise deploy/vault pattern to coding changes: build from a clean environment, install outside the checkout, attest the artifact/commit, verify, and preserve a rollback path.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# Deploy and Rollback

Record use first.

For release-affecting work:

1. Record exact source SHA and dependency/environment facts.
2. Build the deployable artifact.
3. Install/use it outside the source checkout where practical.
4. Execute the critical acceptance path from the installed artifact.
5. Record artifact digest and verification.
6. Preserve the previous known-good commit/artifact as rollback target.
7. If post-deploy verification fails, rollback rather than rationalising failure.

Checkout tests and installed-artifact tests are separate evidence classes.
