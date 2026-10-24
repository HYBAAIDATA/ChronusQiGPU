# Hyperscaler Pilot Proposal — IGPU Cold-Tier Orchestrator

Objective
- Validate IGPU's cold-tier compression, query latency, and provenance in a controlled hyperscaler region on 10–50 PB of cold data.

Duration
- 3–6 months (Pilot / Evaluation)

Pilot Scope
1. Infrastructure
   - Kubernetes namespace or equivalent tenancy
   - Persistent storage (object-backed or block-backed PVCs)
   - Monitoring / telemetry: CloudWatch/Stackdriver/Monitor

2. Components
   - `igpu-core` (toe + aethel bindings)
   - `igpu-data-ingestion` (connectors, zlib + zeckendorf fold)
   - `igpu-causal-intelligence` (toe.bridge, causal lenses)
   - Bench harness and evidence pipeline

3. Goals & Metrics
   - Compression ratio target: 40%–60% (measured across typical cold datasets)
   - Query latency P95: <200ms for representative analytic queries
   - Provenance verification: <1s to validate digest chain per ingest
   - Operational safety: fail-closed on missing evidence

4. Success Criteria
   - Demonstrable storage cost reduction vs baseline (as measured by `benchmarks/hyperscaler_cold_tier.py`)
   - Demonstrable ability to run 3 representative BI workloads end-to-end on cold-tier data
   - Attested provenance for sample regulatory audit (proof packet + receipts)

5. Deliverables
   - Pilot report: compression, latency, cost model
   - Playbook for production rollout (deployment, rollback, incident response)
   - Open contract/statement of work for continued production

6. Responsibilities
   - Hyperscaler: provide tenancy, storage, access to anonymized sample datasets
   - PhiEnterprise: deliver container images, K8s manifests, monitoring dashboards, playbooks

7. Pricing model (example)
   - Pilot fee: engineering + integration (T&M) — suggested $120k–$250k depending on integration scope
   - Production pricing: share of realized storage savings or subscription + per-GB management fee

Notes
- Pilot does not include optional mining/upstream revenue operations. Mining is an optional upsell and requires separate governance and pool integration approval.
