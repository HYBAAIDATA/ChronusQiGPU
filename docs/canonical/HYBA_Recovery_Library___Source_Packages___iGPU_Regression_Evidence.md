# HYBA Recovery Library — Source Packages & iGPU Regression Evidence

**Received and inspected:** 29 October 2026. Agent entry point for ten recovered source/export archives. Originals are preserved separately; do not overwrite a newer implementation with an older recovery package. This library preserves source access and now records the implemented, tested offline recovery in §5. Full product/hardware/mining integration is not complete. Access to the parent page and attachments must be verified by each assigned agent.

## 1. Executable review evidence

The evidence bundle contains the SHA-256 archive manifest and entry inventory, syntax results, review notes, four-test reference-run log, three-test failing regression contract and replay instructions. Full digests—not filenames or version labels—identify the supplied binaries.

[HYBA-recovery-evidence-20261029.zip](HYBA%20Recovery%20Library%20%E2%80%94%20Source%20Packages%20&%20iGPU%20Reg/HYBA-recovery-evidence-20261029.zip)

**Fresh results:** all inspected Python files parse: 35 / 15 / 6 / 61 / 89 / 70 / 4,151 in archives 1 / 2 / 3 / 4 / 5 / 9 / 10 respectively; these counts include duplicates and legacy trees. The recovered v3.4 `test_one_igpu.py` passes four tests. The newly added offline regression contract fails all three checks: invalid mode rejection, modified-record rejection and truthful reference-backend attribution. At the initial archive inspection, pytest was unavailable and no modern suite was run. This is now historical: §5 records newly installed isolated environments and 242 passing selected modern tests. Physical iGPU, native builds, the connected mining voyage and live submission remain unvalidated.

### Concrete iGPU drift found

In v3.4 `src/chronos/igpu/facade.py`, `dispatch()` runs `SpatialLucasPipeline` while reporting the requested integrated/overlay backend label; an unknown mode becomes `host_gpu_overlay`. `OneIGPUResult.verify()` accesses `record.certificate` without verifying it; a modified record value is accepted. Existing happy-path tests miss all three defects. Preserve the failing tests as regression evidence, not as passing qualification.

The larger EUCLID tree contains different implementations: `chronus/igpu/facade.py` validates plans, routes via `ComputeFabric`, records executor/device/receipt evidence and uses pipeline verification. `chronus/one_igpu_mining.py` checks execution contracts/receipts. Its separately packaged ONE iGPU declares `3.11.3rc2`. These were initially inspected source differences. §5 now adds fresh selected offline tests of the modern path; it still does not establish physical hardware execution. The standalone v3.4 ZIP must not replace this richer lineage by default.

## 2. Recovery and reintegration map

| Material | Recovered source / required treatment |
| --- | --- |
| EUCLID enterprise tree | `toe/bridge.py`, `toe/foundation.py`, broader `toe/`, `millennium/hyba_poincare_yangmills.py`, `kellogg/`, `tensor/`, CHRONUS execution/mining adapters, OpenCL/native sources and tests are present. Earlier “not supplied” statements are historical; source access is now restored for these paths. Establish immutable revision, import/build closure and canonical integration before closing runtime findings. |
| iGPU lineage | Preserve reference architecture, one-logical-substrate façade, real backend adapters, resident Hendrix sealed plans, exact geometry and independent verification. Reconcile standalone/reference/current/legacy copies explicitly; no silent reduction to a generic graphics engine or scalar Lucas example. |
| EUCLID learning/posterity | Learning, experience, memory preservation, safe self-modification and tests are supplied. Reconcile capability by capability with the larger enterprise tree. Do not create another orchestration or strategy authority. |
| PULVINI | Enterprise and research packages contain implementation, tests and PULVINI-scoped `formal.py`. Verify namespace/API compatibility before using it to satisfy any old VQC `.formal` dependency. Active working-set reduction is not total retained-state compression; reversible fold, lossy TT and dynamics remain separate capabilities. |
| CHRONUS operations export | Manual plus eight workflows: workload admission, hardware certification, benchmark promotion, release/provenance, deployment profiles, incident/recovery, change approval and risk review. CHRONUS is the broader heterogeneous execution/Virtual iGPU plane, not only the MT dispatcher. |
| TURING operations export | Manual plus eight workflows. TURING is an independent VQC with semantic authority; it may consume OVID transformations, THESEUS custody and CHRONUS execution. Mining is a consuming domain, not its composition root. |
| Large integrated export | Ten nested ZIPs include backend/frontend golden masters, enterprise handover, PULVINI completion and VQC material. Two nested packages list `phi_nucleus/phi_ricci_flow.py`. This is a recovery lead, not demonstrated equivalence to the still-unresolved `ricci_yang_mills_flow.py` or permission to concatenate deployments. Nested inventories were inspected, not all implementations extracted/tested. |

The recovered Poincaré/Yang–Mills module explicitly limits itself to a finite subgroup model and keeps the continuum proof claim false. Preserve this boundary. TOE descriptions and causal/quantum terminology still need capability-specific validation; source availability does not demonstrate universal prediction or mining advantage.

## 3. Original archive attachments

### A1 — `chronos-completed.zip`

SHA-256 prefix `37387ea896ebbafe`; 50 entries. Older mathematical/graphics source candidate.

[chronos-completed.zip](HYBA%20Recovery%20Library%20%E2%80%94%20Source%20Packages%20&%20iGPU%20Reg/chronos-completed.zip)

### A2 — `EUCLID_POSTERITY_RESEARCH_ARCHIVE_20260718.zip`

SHA-256 prefix `b2e31ad8af27f81d`; 35 entries.

[EUCLID_POSTERITY_RESEARCH_ARCHIVE_20260718.zip](HYBA%20Recovery%20Library%20%E2%80%94%20Source%20Packages%20&%20iGPU%20Reg/EUCLID_POSTERITY_RESEARCH_ARCHIVE_20260718.zip)

### A3 — EUCLID_LEARNING_SYSTEM_20260718 (1).zip

SHA-256 prefix `006354801602c005`; 130 entries.

[EUCLID_LEARNING_SYSTEM_20260718_(1).zip](HYBA%20Recovery%20Library%20%E2%80%94%20Source%20Packages%20&%20iGPU%20Reg/EUCLID_LEARNING_SYSTEM_20260718_(1).zip)

### A4 — `pulvini_v3_enterprise_production_20260724.zip`

SHA-256 prefix `00b79a99c01e88a4`; 122 entries. Filename is not production certification.

[pulvini_v3_enterprise_production_20260724.zip](HYBA%20Recovery%20Library%20%E2%80%94%20Source%20Packages%20&%20iGPU%20Reg/pulvini_v3_enterprise_production_20260724.zip)

### A5 — `pulvini_v3_phases_11_13_14_20260724.zip`

SHA-256 prefix `ee0f91b1985f5576`; 160 entries.

[pulvini_v3_phases_11_13_14_20260724.zip](HYBA%20Recovery%20Library%20%E2%80%94%20Source%20Packages%20&%20iGPU%20Reg/pulvini_v3_phases_11_13_14_20260724.zip)

### A6 — Integrated deployment/discovery export

Original `bd5d8d19-e866-459d-a314-48fb7e58b9bd_ExportBlock-aa12b936-0773-4cfc-ada1-96ce85fdf062.zip`; SHA-256 prefix `198ee4c987e27da7`; 181 outer entries, including ten nested ZIPs.

[bd5d8d19-e866-459d-a314-48fb7e58b9bd_ExportBlock-aa12b936-0773-4cfc-ada1-96ce85fdf062.zip](HYBA%20Recovery%20Library%20%E2%80%94%20Source%20Packages%20&%20iGPU%20Reg/bd5d8d19-e866-459d-a314-48fb7e58b9bd_ExportBlock-aa12b936-0773-4cfc-ada1-96ce85fdf062.zip)

### A7 — CHRONUS manual and eight workflows

Original `b9626afb-39b6-4f05-a9c2-9726f631f35c_ExportBlock-f3701862-cf09-44f2-bb54-44c97e2e9923.zip`; SHA-256 prefix `39c4439d93903e56`; nine entries.

[b9626afb-39b6-4f05-a9c2-9726f631f35c_ExportBlock-f3701862-cf09-44f2-bb54-44c97e2e9923.zip](HYBA%20Recovery%20Library%20%E2%80%94%20Source%20Packages%20&%20iGPU%20Reg/b9626afb-39b6-4f05-a9c2-9726f631f35c_ExportBlock-f3701862-cf09-44f2-bb54-44c97e2e9923.zip)

### A8 — TURING manual and eight workflows

Original `f71fa960-d6b3-4f87-bb26-c67375269906_ExportBlock-9f73e92d-a819-49e9-be56-b88824f04456.zip`; SHA-256 prefix `1f1fc86e3cc59b35`; nine entries.

[f71fa960-d6b3-4f87-bb26-c67375269906_ExportBlock-9f73e92d-a819-49e9-be56-b88824f04456.zip](HYBA%20Recovery%20Library%20%E2%80%94%20Source%20Packages%20&%20iGPU%20Reg/f71fa960-d6b3-4f87-bb26-c67375269906_ExportBlock-9f73e92d-a819-49e9-be56-b88824f04456.zip)

### A9 — `chronos-one-igpu-v3.4.zip`

SHA-256 prefix `406a6b499ecee14a`; 133 entries. Contains the façade regressions documented above.

[chronos-one-igpu-v3.4.zip](HYBA%20Recovery%20Library%20%E2%80%94%20Source%20Packages%20&%20iGPU%20Reg/chronos-one-igpu-v3.4.zip)

### A10 — `EuclidPhiEnterprise-main.zip`

SHA-256 prefix `4a6e910cee9135a4`; 8,957 entries. `main` in the ZIP name is not verified Git provenance. Preserve legacy trees as provenance, not parallel canonical imports.

[EuclidPhiEnterprise-main.zip](HYBA%20Recovery%20Library%20%E2%80%94%20Source%20Packages%20&%20iGPU%20Reg/EuclidPhiEnterprise-main.zip)

## 3.1 Additional Owner-Supplied Audit Export

Received during recovery review on 29 October 2026. This text restates the audit through Gate 13; it is preserved as supplied context, not a new test run or an instruction to overwrite the recovery corrections.

[HYBA-audit-owner-update-20261029.txt](HYBA%20Recovery%20Library%20%E2%80%94%20Source%20Packages%20&%20iGPU%20Reg/HYBA-audit-owner-update-20261029.txt)

## 5. Implemented EUCLID Education and Compute Recovery

**Checkpoint:** 29 October 2026. [Draft PR #1](https://github.com/IntelligencePhi/PYTHIA/pull/1) restores 2,332 source/configuration/test/notice files on `recovery/euclid-education-integration-20261029`, based on mining master. [Pinned implementation](https://github.com/IntelligencePhi/PYTHIA/tree/340014a10ea1b191da53fbb05ff05dface7505e2), commit `340014a10ea1b191da53fbb05ff05dface7505e2`. The original eight mining files remain unchanged; no merge or deployment was performed.[[1]](https://github.com/IntelligencePhi/PYTHIA/pull/1)

EUCLID's composition root, learning service, shared experience learner, scoped memory, training/evaluation/checkpoint paths and integrated skill lifecycle are restored. Tensor/Kellogg ownership and its missing exact engine dependency, TURING pipeline and richer CHRONUS geometry/resident/logical-iGPU sources are included. The old v3.4 package is retained as historical evidence, not promoted over the newer implementation.[[2]](https://github.com/IntelligencePhi/PYTHIA/blob/340014a10ea1b191da53fbb05ff05dface7505e2/recovery/README.md)

**Fresh verification:** 242 selected tests passed; the initial pytest summary also records 12 passing subtests. A manifest-bound runner passed in both the initial environment and a newly created clean Python 3.13 virtual environment installed from the recorded requirements. Source integrity passed and required failures/skips/missing tests were absent. A real child-pytest/JUnit rootdir defect was fixed and covered by a nested-project regression. Added property/adversarial checks cover shared training seeds, invalid modes, truthful CPU-reference attribution and modified-result rejection.

The evidence ZIP below contains JUnit, run/install logs, publication receipt, source hash manifest, replay requirements, runner and new regression tests. Local runs bind the source manifest; local Git metadata was absent, so the evidence does not pretend it executed a remote Git commit. Remote CI success has not been established.

[HYBA-euclid-reintegration-evidence-20261029.zip](HYBA%20Recovery%20Library%20%E2%80%94%20Source%20Packages%20&%20iGPU%20Reg/HYBA-euclid-reintegration-evidence-20261029.zip)

**Replay:** follow [recovery/README.md](https://github.com/IntelligencePhi/PYTHIA/blob/340014a10ea1b191da53fbb05ff05dface7505e2/recovery/README.md): create a Python 3.13 venv, install `requirements-recovery.txt`, run `python scripts/verify_recovery.py`. No operational mining or credentials are required.

**Still open:** independent review/merge; every curriculum/domain and all older/nested recovery capabilities; broader optional dependencies and complete production packaging/SBOM; physical iGPU/native/OpenCL; full TS/Python mining voyage; operational custody and deployment. This is a qualified offline recovery profile, not whole-product GO. See parent audit §0.8 for the full checkpoint and §5.6/Gate 14 for remaining obligations.

## 6. Recovery Wave 2 — Canonical Direction and Six-Agent Handoff

Five more archives were received and statically inspected: `pythia.zip`, `EuclidPhiEnterprise-main (1).zip`, `MIDAS_BACKEND_HYBA_EUCLID_ELEVATED.zip`, `EUCLID_RELEASE_CONTROLS_20260718.zip` and `EUCLID_SHARED_REPOSITORY_SNAPSHOT_20260718_2158.zip`. Full digests, ZIP inventory counts, recovered governing declarations and research leads are preserved in [HYBA Canonical Research & Architecture Record — Recovery Wave 2](https://app.notion.com/p/HYBA-Canonical-Research-Architecture-Record-Recovery-Wave-2-a4564db2dc4340429bb036fa6bced579?pvs=21).

**Access limitation:** attachment export failed, including a single-file retry. These five new binaries are **not attached by this update** and other-session access is unverified. They remain owner-supplied chat attachments; A2 must arrange and verify an approved persistent copy before relying on them. No new-wave code/tests were executed or pushed during briefing preparation.

The recovered owner canon confirms independent substrate/hardware-agnostic CHRONUS with no physical GPU prerequisite, family roles and active roots; D9 clarifies OVID authoritative custody, THESEUS rebuildable projections and EUCLID training/genesis authority. Earlier hardware requirements and custody interpretations need profile-aware correction. The exact draft *The Golden Ratio as Nature's Great Scaler* is in MIDAS `docs/phi_scaling/03_paper.md`; revised theory/audit and discovery/transform tool candidates are identified in the companion record.

[HYBA Six-Agent Remediation — Common Prompt, Assignments & QC Close-Out](https://app.notion.com/p/HYBA-Six-Agent-Remediation-Common-Prompt-Assignments-QC-Close-Out-54cf93194b3f4385acbfc03f4ec79e04?pvs=21) provides the shared prompt, six file-owned work packages, branch/Notion handoff rules, CI-first dependencies, agent return board and coordinator-owned QC checklist. Assignments are ready to issue; no agents were automatically launched and no release approval was granted.

## 4. Agent handling requirements

Verify attachment retrieval and full digest; inspect dependencies and licenses; scan for secrets before any wider publication. Preserve originals read-only. Import only reviewed source into the intended repository/namespace on task branches. Link every restoration to an architecture contract, invariant, test and fresh evidence receipt. No supplied archive filename, archived report or code comment grants permission to change product identity, authority or production status. Do not execute archived scripts, install hooks, open pools, or deploy as an automatic recovery step.

The parent audit §5.6 and Gate 14 define the mandatory reintegration and anti-drift test requirements. Scoped recovery implementation is now published in draft PR #1, as recorded below. Review/merge, broader capability reconciliation and full deployment integration remain pending.

## 7. A2 transfer unblock — direct Notion attachment upload

**Owner-reported status — 2026-10-29:** all five original Wave 2 ZIPs are located and their SHA-256 hashes have been verified against the recorded manifest. The file-export service still fails, so there is no shared download location and A2 remains blocked on transfer. This report records the owner's verification; it does not claim A2 has independently recomputed the hashes.

**Action for the archive custodian / coordinating agent:** upload the five original ZIP files directly as file attachments to this Recovery Library page, preserving original filenames and read-only originals:

- `pythia.zip` — `4f932df90ed4dd1e9fefd79a66d66364cd783022252c1dabd3495a756a1c0b0f`
- `EuclidPhiEnterprise-main (1).zip` — `3440b1047a140e3f736d67d22153be71777ef429e8875957a0d7926e3f8c6857`
- `MIDAS_BACKEND_HYBA_EUCLID_ELEVATED.zip` — `6025cb1dc7901ee283a450f20f1f5c5593bfeaedc3dd4def5f420cae98b304ab`
- `EUCLID_RELEASE_CONTROLS_20260718.zip` — `c2fd36371907019d7b621a725ca899c374b35fc9912432fcdc507037ecf55001`
- `EUCLID_SHARED_REPOSITORY_SNAPSHOT_20260718_2158.zip` — `b13381ec1888cd50fee43f4a0f444443d1f9ccc6ea09555cb960ab2146f50ffd`

Once attached, notify A2 and provide the attachment links. A2 must retrieve each ZIP, independently recompute the full SHA-256, and report the results before implementation. Until that verification is complete, archive-dependent implementation and tests remain pending; hosted CI remains paused.