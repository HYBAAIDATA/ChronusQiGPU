# Chronus release status

**Status: NOT QUALIFIED**

- Repository: `HYBAAIDATA/ChronusQiGPU`
- Main baseline reviewed: `3f30f61d490ee78ca6c8b0bdf1b3df84b1b6a0c1`
- Closing branch: `codex/production-readiness-20261116`
- Closing PR: [#136](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/136)
- Requirements map: [docs/notion-production-readiness.md](docs/notion-production-readiness.md)
- Claim audit: [docs/claim-audit.md](docs/claim-audit.md)

The previous dossier claimed “100% PRODUCTION QUALIFIED” from an unrelated historical commit. It is withdrawn. Current source and tests provide useful implementation evidence, but they do not establish a production release.

## Observed blockers

- 2026-11-19 wiring closeout: PR #173 (entry-point/env/migration wiring) merged as `c11af3e6`; orphan-module dispositions, version single source (`37.0.0.dev0` from `pyproject.toml`), root cleanup and the CI test-execution gate are recorded in [docs/audits/2026-11-18-wiring-audit.md](docs/audits/2026-11-18-wiring-audit.md#closeout-2026-11-19). `hendrix.mhtml` was removed from the tree but remains in git history.

- The current main baseline had reproducible source-level failures in package collection, hygiene, qualification import paths and test fixtures. PR #136 carries the fixes on top of main, including the missing Geodesic evidence packet, clean-checkout TURING import path, secure tenant-capacity test credentials, rollback fixture setup, claim-token allowlisting and the HYBA Mine/TURING installation seam.
- The frontend lockfile also carried 20 pnpm advisories through the Tailwind/PostCSS transitive graph (including one critical). PR #136 refreshes the locked graph; local `pnpm audit` now reports zero advisories, the Next production build passes, and all four Ciaas acceptance tests pass.
- Local exact-current verification on the review checkout passed `2340 passed, 38 skipped, 1 xfailed` (Python 3.12.14), with the focused package, acceleration, storage, build, Bandit, purity and mutation checks passing. This is local evidence, not GitHub-hosted CI evidence.
- The PR's GitHub Actions runs fail before retaining usable job steps/logs; sampled log downloads return Azure `BlobNotFound`. That is recorded as infrastructure unavailable, not as a passing release gate.
- No physical GPU/device certificate, reference-vs-device differential, sustained thermal/soak run, failure/recovery record, or literal live-pool acknowledgement is present.
- No immutable SBOM/provenance/rollback packet or explicit owner approval is present.
- The four July Geodesic Tensor primitives have now been located in active `src/chronus/tensor/geodesic.py`, exported and tested by `tests/test_geodesic_tensor_migration.py` (source/test presence only; no current release qualification). The historical named Kellogg contract is not yet matched to a complete maintained implementation/certification and remains under reconciliation.
- Historical qualification manifests and benchmark claims remain provenance only.

The mining deployment hold in `deploy/hyba-mine/control.env` is preserved. No deployment workflow was resurrected by this review.

The ChatGPT Library and Notion source reconciliation is recorded in
[`docs/notion-production-readiness.md`](docs/notion-production-readiness.md),
[`docs/production/NOTION_LIBRARY_RECONCILIATION.md`](docs/production/NOTION_LIBRARY_RECONCILIATION.md)
and the dated audit. The maintained tree already contains the four named
Geodesic/Tensor surfaces; historical monolithic source was not copied into the
runtime.

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

## Notion/Library source restoration — November 16, 2026

Source recovery branch `audit/20261116-notion-library-artifacts` reconciles
real attached Notion blocks and ChatGPT Library ZIPs, not names alone.
Seven supplied ZIPs passed archive integrity/path checks. The source register
records their fingerprints plus additional Library sources.

- **CODE-PRESENT, REVIEW PENDING:** exact rational TT (no implicit numerical
  truncation, checked core digest, registered in `chronus.tensor`).
- **CODE-PRESENT, REVIEW PENDING:** archived ONE iGPU finite-data and allocation
  guards wired into the existing `PhiTensorCore` reference execution path.
- **TEST SOURCE ADDED, CURRENT CI UNAVAILABLE:** tensor round-trip/negative
  cases and geodesic input/output safety cases.
- **ARCHIVE-SCOPED RESULTS:** historical ONE iGPU/Lucas 10 passed, historical
  VQC + PULVINI formal 22 passed, local new exact TT source 6 passed.
  None qualifies this current branch or deployed runtime.
- **NOT PORTED:** Chronos QSDL parser/compiler graph. Historical Kellogg
  merged PR descriptions are not accessible source files via this connection.
- **NO CLAIM:** live pool accepted share, physical accelerator, quantum
  advantage, compression capacity or production qualification.

Source map:
`docs/audits/2026-11-16-notion-library-source-recovery.md`.
