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
- The four July Geodesic Tensor primitives have now been located in active `src/chronus/tensor/geodesic.py`, exported and tested by `tests/test_geodesic_tensor_migration.py` (source/test presence only; no current release qualification). The historical named Kellogg contract is not yet matched to a complete maintained implementation/certification and remains under reconciliation.
- Historical qualification manifests and benchmark claims remain provenance only.

The mining deployment hold in `deploy/hyba-mine/control.env` is preserved. No deployment workflow was resurrected by this review.

## 16 November 2026 closeout supplement

- The source-to-archive reconciliation is tracked in [docs/audits/2026-11-16-source-archive-reconciliation.md](docs/audits/2026-11-16-source-archive-reconciliation.md).
- The Patroclus `/v1/mining/admin/patroclus/simulate` endpoint was found to misrepresent localhost fixture success as acceptance by four live mining pools. This review branch corrects its response classification and validates local fixture submission; this is **not** proof of external pool acceptance.
- Mainline production qualification, CI, protected release policy and live/runtime evidence stay **NOT QUALIFIED / UNAVAILABLE** until exact-commit evidence exists.
