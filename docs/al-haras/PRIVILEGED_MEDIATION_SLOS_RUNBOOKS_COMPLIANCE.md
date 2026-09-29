# Privileged mediation, SLOs, runbooks, and compliance automation

## Privileged-path result

The audit now discovers concrete FastAPI decorators and table-driven `BaseHTTPRequestHandler` routes while excluding tests, artifacts, legacy trees, and policy constants. FastAPI security routes perform Guardian evaluation and return a Guardian receipt. Miner mining/security/TOE routes execute fail-closed Guardian preflight before handler dispatch; successful responses attach the receipt and append only its hash to the audit log.

Local result with both adapters present: 13 privileged routes discovered, 0 violations. A signed HMAC mediation manifest is emitted when `MEDIATION_MANIFEST_KEY` is configured; otherwise the manifest is content-hashed and explicitly marked `UNSIGNED`. Unsigned route coverage can unblock the static audit but cannot satisfy independent evidence/promotion requirements.

## Observability and SLOs

- Prometheus scrape configuration for core, Miner, and Enterprise.
- OTLP Collector receiver with memory limiting, batching, trace debug export, and Prometheus metric export.
- Six SLOs bound to developer, edge, enterprise, sovereign, and hyperscaler profiles.
- Grafana-compatible dashboard model with ten panels.
- Fast/slow burn, freshness, and zero-budget parity alert generation.

## Machine-readable runbooks

The catalogue includes key rotation, forward schema migration, witness-loss recovery, and four compound-failure playbooks. The runner enforces prerequisites, executes named actions, verifies outcomes, runs rollback actions on failure, and signs successful evidence.

## Compliance evidence

- Multi-signer regulator evidence-pack assembly.
- Offline verification callbacks requiring signature, envelope, witness, and explained-gap checks; no MLA1517 runtime dependency.
- Assurance-pack crosswalk generation.
- Continuous-control jobs with alert and gap recording.
- Read-only filesystem evidence-room reference.
- Industry-pack installation through explicitly supplied registries.

## Evidence and remaining boundaries

The combined dependency-free suite passes 41 tests. Static privileged mediation now passes locally. Full runtime/ASGI tests, production signing key custody, real Prometheus/OTel deployment, runbook drills, independently administered witness verification, and regulator validation remain unestablished. GitHub check publication must still be observed on the target SHA before any promotion.
