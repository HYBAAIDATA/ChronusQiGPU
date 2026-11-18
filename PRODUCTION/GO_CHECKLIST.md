# Production GO checklist

## Decision rule

GO is permitted only when every mandatory item below is `PASS` or `PRESENT`
with an independently verifiable artifact tied to the exact release commit.
Anything marked `LOCAL_ONLY`, `MISSING`, `UNAVAILABLE`, or `GATED` blocks GO.

| Requirement | Current state | Evidence required to close | Current evidence / owner |
| --- | --- | --- | --- |
| Chronus → OVID → THESEUS wiring | PRESENT / LOCAL_ONLY | Exact-commit test and review record | `src/chronus/triad.py`; local suite |
| OVID reversible transformation contract | PRESENT / LOCAL_ONLY | Exact-commit contract tests and retained raw output | `src/chronus/ovid/transform.py`; local suite |
| THESEUS durable custody and restart continuity | PRESENT / LOCAL_ONLY | Hosted exact-commit result plus deployment profile | `src/chronus/storage/durable.py`; local product gate |
| Full Python test suite | PRESENT / LOCAL_ONLY | Hosted CI PASS for exact commit | `evidence/local-verification.json`; CI owner |
| Frontend build and acceptance | PRESENT / LOCAL_ONLY | Hosted build artifact or exact-commit CI result | `frontend/scripts/acceptance.test.mjs`; CI owner |
| Mandatory software gates | PRESENT / LOCAL_ONLY | Attested `ci-verdict.json` | `evidence/product-gates.local.json`; CI owner |
| Exact-current hosted CI | MISSING | Successful main-branch run for the exact release SHA | Release engineer |
| Artifact attestation | MISSING | Verified GitHub artifact attestation and invocation URI | Release engineer |
| Owner approval | MISSING | Signed/recorded owner approval packet | Andre Taylor-Morris / owner delegate |
| Azure Managed HSM custody | MISSING | Live sign/verify evidence and provider identity | Security/platform owner |
| Device certificate and physical execution | MISSING | Device-bound certificate and raw runtime evidence | Hardware/platform owner |
| Benchmark evidence | MISSING | Reproducible workload, host, raw timings, and reviewer | Performance owner |
| SBOM | MISSING | Generated SBOM for exact artifact and dependency lock | Build/release owner |
| Provenance | MISSING | Build provenance tied to exact source and artifact digest | Build/release owner |
| Rollback plan | PREPARED / UNAPPROVED | Approved, tested, profile-specific rollback record | Operations owner |
| Multi-region durability | MISSING | Deployment-specific failover/recovery evidence | Operations owner |
| Customer/external key custody | MISSING | Customer/provider-controlled custody evidence | Security/platform owner |
| Package-manager parity | BLOCKED | `pnpm@10.12.4` install/build/acceptance result | Build/release owner |

## Required close-out sequence

1. Provision `pnpm@10.12.4` and run the frontend checks under pnpm.
2. Run the full Python suite and product gates on a clean exact-commit runner.
3. Publish the CI verdict and retain GitHub attestation verification output.
4. Complete owner approval, SBOM, provenance, rollback, key-custody, device,
   benchmark, and deployment evidence.
5. Run:

```text
python scripts/ci/require_release_qualification.py \
  --repository HYBAAIDATA/ChronusQiGPU \
  --commit <exact-main-release-sha> \
  --verified-verdict-output PRODUCTION/evidence/ci-verdict.json \
  --provenance-output PRODUCTION/evidence/attestation-verification-receipt.json
```

6. Obtain the final owner decision. Until then, the release remains HOLD.

