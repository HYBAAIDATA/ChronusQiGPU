# Chronus claim audit — definitive close-out posture

**Review date:** 15 November 2026  
**Candidate:** PR #93 / `closeout/triad-production-posture-20261115`

This document supersedes the 8 November static review. It is the human-readable companion to:
- `docs/QUALIFICATION_AND_CLAIMS.md`
- `capabilities/triad_production_manifest.json`
- `evidence/migration/chronus_historical_evidence_register.json`

## Governing rule

A current product statement needs the exact source revision, the applicable test or measurement, the environment, the retained evidence artifact and the relevant admission gate. Historical results remain provenance until rerun or reconciled to the current candidate.

## Current dispositions

| Claim area | Current disposition | Evidence boundary |
| --- | --- | --- |
| CHRONUS execution/fleet | Implemented | Current CI required; physical scaling/performance remains environment-specific |
| Tensor software runtime | Implemented and elevated in PR #93 | Current branch regressions required |
| OpenCL tensor backend | Implemented, fail closed | Physical GPU evidence required |
| CUDA tensor backend | Implemented, fail closed | Physical NVIDIA device evidence required |
| Metal tensor backend | Implemented, fail closed | Physical Apple device evidence required |
| OVID transform/materialise | Implemented | Current round-trip/digest tests required |
| THESEUS durable local custody | Implemented in PR #93 | Restart, corruption, concurrency and journal tests required |
| Triad restart/replay | Implemented in PR #93 | Exact-current CI required |
| External customer-held key custody | Not established by provider interfaces | Actual provider operation + attested `FN-CUSTODY` PASS required |
| Multi-region durability / HA | Not established by local SQLite/WAL durability | Deployment-specific failover, RTO/RPO and replication evidence required |
| Current comparative performance | Evidence-specific | Historical device and benchmark records are retained but not promoted automatically |
| Regulatory / external certification | Not awarded by this repository | External authority/assessor evidence required |
| Customer deployment / SLA | Not inferred from source or fixtures | Customer/deployment evidence required |
| Production admission | Evidence gated | Exact candidate CI + verified artifact attestation + every mandatory product gate PASS |

## Qualification controls

The current mandatory gates are:
- `CO-SIGN`
- `RS-RECEIPT`
- `RS-REPLAY`
- `FN-CLAIMS`
- `FN-CUSTODY`

The close-out removes prior self-certifying paths:
- the package facade no longer forces a production result;
- the local manifest no longer embeds a key or awards production status;
- the legacy sovereign dossier is local software evidence only;
- a provider name cannot satisfy custody;
- historical test counts cannot satisfy an exact-current gate.

## Historical evidence

Historical tensor, fleet, storage and device records are preserved in `evidence/migration/chronus_historical_evidence_register.json` and summarized in `docs/production/TEST_AND_BENCHMARK_PROVENANCE.md`.

They remain visible for provenance and regression design without being represented as current PR #93 results.

## Current CI condition

PR #93 triggered the repository's GitHub Actions and CodeQL checks. At the time of this update, the sampled jobs fail before usable logs are produced and the log endpoint returns Azure `BlobNotFound`. This is recorded as an infrastructure condition, not as a software pass or failure. The merge/release decision must use a successful rerun or another retained exact-current execution record before production admission.
