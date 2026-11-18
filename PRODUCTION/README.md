# Production readiness packet

## Current decision

**HOLD — not approved for production release.**

This folder is the working release-readiness packet for Chronus, OVID and
THESEUS. It separates evidence that is present locally from evidence that must
come from hosted CI, an owner, a managed custody provider, or a deployment
environment. A green local test result does not change the release decision.

The canonical authority boundary is preserved:

- Chronus executes computational workloads.
- OVID transforms and materialises representations.
- THESEUS stores, preserves, and verifies durable records.
- AL HARAS owns authorization, security policy, and security evidence.

## Contents

- `GO_CHECKLIST.md` — requirement-by-requirement decision matrix.
- `GO_DECISION.json` — machine-readable fail-closed release decision.
- `evidence-register.json` — evidence inventory with status and owner/action.
- `evidence/product-gates.local.json` — locally generated software-base gate result.
- `evidence/local-verification.json` — local test/build observations and limits.
- `templates/` — templates for artifacts that cannot be honestly generated in
  this checkout.

## How to use this packet

1. Re-run the commands in `GO_CHECKLIST.md` on the exact candidate commit.
2. Attach the hosted CI verdict and GitHub attestation receipt.
3. Attach owner approval, managed-key custody evidence, SBOM/provenance, and
   deployment-specific evidence.
4. Run the release verifier. Do not change `GO_DECISION.json` by hand to claim
   GO; the verifier must consume the externally verified artifacts.

