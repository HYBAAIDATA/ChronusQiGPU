# ChronusQiGPU — production and release blocker audit

**Review date:** 2026-11-15 (UTC)  
**Repository:** [HYBAAIDATA/ChronusQiGPU](https://github.com/HYBAAIDATA/ChronusQiGPU)  
**Audited `main` SHA:** `dc920a82c38ee408fb9698d3206631139f9d0d97`  
**Decision:** **NOT QUALIFIED — release publication must remain held.**  
**Scope:** repository code, GitHub open PRs, checks, review threads, workflows and release-facing documents. This is a point-in-time assessment, not evidence of a deployed runtime.

## Release blocker register

| Blocker | Observed evidence | Disposition / closure gate |
| --- | --- | --- |
| Unprotected main branch | Audited GitHub branch API reported `main.protected=false` and no enforced required checks at the reviewed SHA | [Issue #89](https://github.com/HYBAAIDATA/ChronusQiGPU/issues/89): admin must enforce required CI/review and restricted release/tag controls; verify effective ruleset before release. |
| Main-branch CI red | [CI run 43669370042](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/43669370042), [packages 43669369942](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/43669369942), [qualification 43669370018](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/43669370018), [storage 43669370069](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/43669370069) failed on the audited baseline | Repair series [#73](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/73), [#74](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/74), [#75](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/75) consolidated in [#86](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/86). Integrate only after full current-head CI and substantive review clearance. |
| Blank HYBA Mine workflow | [Failed push run 43694550417](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/43694550417); workflow present on audited `main` | [#72](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/72) removes the empty workflow. The optional mining deployment remains owner-held, not silently activated. |
| Braiins endpoint parser | [#72](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/72): hostname and port parsing fixes, offline Docker checks; mining-focused checks reported passing | Re-run the complete PR matrix after baseline repair and merge if green. No live Braiins pool acknowledgement or accepted share asserted. |
| SQLite concurrent first-use | [Issue #82](https://github.com/HYBAAIDATA/ChronusQiGPU/issues/82), [PR #83](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/83); cross-process lock and subprocess test | Review stale-path, alias-path, Windows contention and interrupted-bootstrap cases; require full matrix green and Qodo comments disposition. No distributed SQLite claim. |
| Unqualified release can publish | [Issue #79](https://github.com/HYBAAIDATA/ChronusQiGPU/issues/79), baseline [release.yml](https://github.com/HYBAAIDATA/ChronusQiGPU/blob/dc920a82c38ee408fb9698d3206631139f9d0d97/.github/workflows/release.yml) permits publication without an independently verified PASS verdict | [#85](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/85) proposes tag-only, exact-commit attested qualification. Verify negative cases (missing/tampered/unattested evidence), CLI compatibility and reviewer findings before merge. |
| Frontend dependency updates | [#76](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/76) includes Next.js and supporting dependencies; frontend build passed on its head but unrelated baseline jobs failed | Recheck after baseline repair; do not describe as merged or security-fixed until updated lockfile passes complete checks. |
| Duplicate repair draft | [#71](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/71) overlaps CI fixes, blank-workflow removal and qualification documents | Reconcile with #86/#72 and this qualification-truth change; close as superseded only after verifying no unique remediation/evidence is lost. |
| Legacy qualification promotion | `scripts/ci/manifest.py` included a source-embedded HMAC key, hard-coded metrics, and `PRODUCTION_QUALIFIED` on local check success | This branch removes the embedded-key signature and false metrics, always outputs `NOT_QUALIFIED` and retains the local pass/fail signal. Add regression tests; verify current-head CI. |
| Contradictory release documents | Old root `STATUS.md` claims 100% qualified; root `PRODUCTION_QUALIFIED.json` reports a historical signed PASS not bound to current acceptance | Root documents updated to a dated `NOT_QUALIFIED` assessment. Preserve old values in Git history only. |
| Local audit script false-positive | `scripts/ci/verify_chronus.py` always prints “ALL SIX ARTIFACTS VERIFIED SUCCESSFULLY” regardless of subprocess exit codes | Corrected to label its output as non-qualifying inspection; no release authority is conferred. |

## Strict evidence and claim boundaries

A successful check or PR merge proves only the measured repository condition and commit. The **product release** remains HELD unless the following artifacts are demonstrably available and cryptographically tied to the exact release commit:

1. Successful `main` qualification workflow; cryptographically verified verdict `PASS`, no blockers, mandatory gates all PASS and supported claims.
2. Conformant cryptography, independently reviewed security controls, authenticated identity and actual remote key custody where claimed.
3. Real device census and certification, reference-vs-device differential and reproducible throughput/power/performance evidence for any physical accelerator claim.
4. Sustained soak and fault recovery, durable custody/restart, deployment rollback and operational readiness evidence.
5. Literal pool acceptance record for any live-share claim; no synthetic replay substitutes for this.
6. Independently auditable SBOM/provenance, traceable owner approval and versioned release artifacts.

**Currently unavailable:** exact-commit production PASS verdict; independent crypto and security assessment; HSM custody; physical device certificate; soak/recovery; live pool acknowledgement; owner deployment approval. Record each as unavailable rather than asserting a failed test that was never run.

## Authority and change policy

The audit does **not** change subsystem authority: EUCLID intelligence orchestration; PYTHIA predictive/mining authority; TURING independent VQC; Chronus execution/iGPU; THESEUS durable custody; OVID transformation contracts; Salamander bounded healing; AL HARAS security. No autonomous release, live mining deployment, hardware qualification, publication or customer certification is authorized by these documentation repairs.

## CI and PR closeout sequence

1. Close substantive CodeRabbit/Qodo findings on the latest heads; specifically verify the SQLite alias/lock and release-attestation failure cases.
2. Consolidate and integrate CI baseline [#86](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/86), then SQLite [#83](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/83) as appropriate to the stacked branch graph.
3. Rebase/re-run independent [#72](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/72), [#76](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/76) and [#85](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/85) on the integrated baseline; do not bypass failing gates.
4. Incorporate the legacy claim-truth correction, then refresh branch-head check statuses in this register and reconcile/close redundant #71/#73–#75 PRs.
5. Keep #79/#82 open until the corresponding verified software PRs merge; keep [#16](https://github.com/HYBAAIDATA/ChronusQiGPU/issues/16) open for customer trust evidence.

**This report captures the initial audit.** A passing CI run, merge, or live observation after this timestamp must be recorded with its own SHA and run URL, not inferred from the PR description or this static file.
