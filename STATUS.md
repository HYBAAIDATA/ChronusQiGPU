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

## Security/archive recovery branch follow-up (16 November 2026)

The archive reconciliation PR #130 includes additional source changes:
- `src/chronus/security/durable_receipts.py`: Ed25519 signed receipt replay
  in canonical THESEUS custody; facade Gate G2 now validates a local restart.
- `src/chronus/service/mining_operator.py`: explicit AL HARAS operator
  admission for all 11 mining administration routes, with durable admission
  audit before any handler and no implicit tenant-token authority.
- Both Kubernetes readiness probes now target `/health/ready`; the
  authenticated global mining telemetry endpoint is not a health probe.
- New adversarial regression tests and corrected old API test credentials.
- Original PULVINI protected sources and test/guard code have been verified
  byte-identical to their archived handoff; no duplicate was imported.
- Historical Kellogg sources from other private repositories are
  inaccessible here and remain **UNAVAILABLE FOR RECOVERY**, not invented.

**NOT QUALIFIED**: New source and tests are committed only on review PR #130,
not production-admitted. CI must execute, pass and provide exact-head
evidence before merge; human owner must enforce rulesets and release gates.
Legacy `access_control.py` is not an active security authority.
