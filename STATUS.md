# Chronus release status

**Status: NOT QUALIFIED**

- Repository: `HYBAAIDATA/ChronusQiGPU`
- Main baseline reviewed: `dc920a82c38ee408fb9698d3206631139f9d0d97`
- Closing branch: `codex/production-readiness-20261115`
- Closing PR: [#71](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/71)
- Requirements map: [docs/notion-production-readiness.md](docs/notion-production-readiness.md)
- Claim audit: [docs/claim-audit.md](docs/claim-audit.md)

The previous dossier claimed “100% PRODUCTION QUALIFIED” from an unrelated historical commit. It is withdrawn. Current source and tests provide useful implementation evidence, but they do not establish a production release.

## Observed blockers

- The main baseline had reproducible CI failures in collection, packaging, static security, purity, evidence installation and storage-path setup. PR #71 addresses the source-level causes and reruns the checks on its own SHA.
- No physical GPU/device certificate, reference-vs-device differential, sustained thermal/soak run, failure/recovery record, or literal live-pool acknowledgement is present.
- No immutable SBOM/provenance/rollback packet or explicit owner approval is present.
- Several Notion lineage names (the four Geodesic primitives and the named Kellogg contract) have no active-tree symbol match; they remain port/missing work, not implied by archived files.
- Historical qualification manifests and benchmark claims remain provenance only.

The mining deployment hold in `deploy/hyba-mine/control.env` is preserved. No deployment workflow was resurrected by this review.
