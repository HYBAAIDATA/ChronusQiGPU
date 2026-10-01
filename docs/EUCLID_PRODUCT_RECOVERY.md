# EUCLID Product Recovery and Mining Convergence

Status: **ACTIVE CONVERGENCE — NOT A PRODUCTION-READINESS CLAIM**

This document is the provenance and ownership record for the EUCLID / enterprise-intelligence source recovered for PYTHIPhiMiner. Its purpose is to prevent a partial import from being mistaken for the full product and to make the mining-support boundary reviewable.

## Authoritative recovered source

Recovered package: `hyba_final.zip`

SHA-256:

`99ce08bd16d7c399ed5787728e6c74f8347d659ef328d306fa024053a497de36`

The recovered package was executed independently before integration. These results describe the recovered archive only; they are **not** evidence that the mining branch has integrated the same capabilities yet.

| Recovered gate | Result |
|---|---:|
| `tests.test_euclid_creative_substrate` | 15/15 |
| `tests.test_euclid_organism_cns` | 8/8 |
| `tests.test_euclid_startup_orchestrator` | 9/9 |
| EUCLID development gates | 32/32 |
| `euclid.production_harness` | 15/15, `EUCLID_PRODUCTION_HARNESS_V2` |

GitHub Actions on PYTHIPhiMiner is currently failing before runner allocation (`steps=[]`, `runner_id=0`). Therefore repository-side changes are **CI-unverified** until executable runners become available.

## Recovered canonical package inventory

The following package hashes are deterministic hashes over sorted relative path + file bytes from the recovered archive.

| Package | Files | Python files | Bytes | Recovered tree SHA-256 | Mining-branch status |
|---|---:|---:|---:|---|---|
| `euclid/` | 80 | 55 | 709,547 | `83ea6892e836cf49e05fb4e1f7ee8b2ceef5c899aa651115f77eaa69b82401c8` | **RECOVERED / NOT YET COPIED** |
| `hyba_substrate/` | 8 | 8 | 95,157 | `71501e675f2bbb6a2076344d1f09e70abce003f28343eab4764b9461778bee72` | **PRESENT — CONVERGENCE EDITION / BRANCH EXECUTION UNVERIFIED** |
| `resonance_intelligence/` | 34 | 34 | 278,914 | `d99ebc6bc1d4268cd44aea508131228b4de5466a711520390cdc0d203f3ac4a4` | **RECOVERED / IMPORT IN PROGRESS** |
| `quantum_core/` | 7 | 7 | 70,557 | `00955267b2b3c5342c464869a8f4ce5a9f717a0a8a76d29740ac1eaf649d2fd6` | **RECOVERED / NOT YET COPIED** |

`hyba_substrate/` is now physically present as eight source modules. The convergence edition is not byte-for-byte identical to the recovered archive: implementation files were normalized during import. A semantic surface audit confirmed the learning-system classes and public methods needed for seed knowledge, experience lineage, claim evidence, curriculum, consolidation, persistence and chain validation remain present. Any future divergence must be judged by capability/evidence parity rather than by filename presence alone.

No implementation credit is given to the mining branch for a package merely because it is listed here.

## Existing canonical owners in PYTHIPhiMiner

The recovered archive must not overwrite newer product owners that already exist in the mining repository.

- **Mining / Stratum / SHA256d authority:** current `mla1517_platform_v3.4/python/mla1517/mining/` and `mining/` surfaces.
- **Aethel:** current first-class `aethel/` package. Recovered enterprise copies must not replace it wholesale.
- **Turing:** current packaged `turing_universal_quantum_computer/` compute/mathematical substrate. Chronus is not Turing and must not absorb it.
- **Chronus:** iGPU product/offering boundary. Historical Chronos graphics research is provenance material, not the current product identity.
- **Bitcoin consensus truth:** current SHA256d proof adapter, current target/job generation, local candidate validation and pool acknowledgement. EUCLID has no authority to modify these.

## Production mining integration seam

The branch contains:

`mla1517_platform_v3.4/python/mla1517/mining/euclid_support.py`

and the canonical `mining_runtime.py` instantiates `EuclidProductionMiningCoordinator`.

The seam has one deliberately bounded actuator: **candidate dispatch breadth**. It may HOLD, REDUCE or RESTORE breadth, where RESTORE is hard-clamped to the coordinator's existing baseline. It cannot alter:

- SHA256d;
- block/header construction;
- Stratum target or difficulty;
- nonce correctness;
- share proof validation;
- credentials;
- submission parameters; or
- pool acknowledgement truth.

`hyba_substrate.euclid_experience_superlearner` is now physically present, so the package-absence condition that previously forced `UNAVAILABLE` has been removed at source level. **This is not yet a runtime-success claim:** the branch still requires import/startup execution against the converged tree. If runtime initialization fails, the seam must continue to publish `UNAVAILABLE` rather than fabricate active intelligence.

The seam learns only from observed mining outcomes, de-duplicates outcome generations so repeated telemetry polls do not multiply one result, and cadence-limits policy evaluation. Missing submission evidence produces no invented reward.

## Recovered capability classification

### Appropriate for live production support after import

- experience-first learning and durable learning lineage;
- world/system modelling when fed bounded measured operational state;
- organism/coherence evaluation;
- resonance feedback, causal attribution, uncertainty and resource awareness;
- governed fallback and audit surfaces;
- evidence-gated learning and claim promotion.

These mechanisms may influence bounded operating policy only after their inputs and effects are visible in mining evidence.

### Laboratory-only by source contract

The recovered Kairos mining lab explicitly states that it has no miner, pool, wallet, credentials, network, share submission, revenue or profitability capability. Its evidence gate forbids live-operation fields including `pool`, `stratum`, `hashrate` and `accepted_share`.

Therefore `euclid.kairos_mining_lab_service` and `euclid.kairos_mining_reasoning` remain governed laboratory/test-world capabilities. They must **not** be represented as the live pool-control path. Their role in the mining product is falsification, simulation, reasoning tests and policy rehearsal.

## Full-product acceptance rule

EUCLID is not considered integrated until all of the following are true:

1. The canonical recovered packages are physically present in source form in the mining branch or deliberately replaced by newer canonical implementations with documented equivalence.
2. Startup/import gates execute against the mining branch rather than the extracted archive.
3. Mining runtime evidence shows EUCLID availability and the exact bounded decision/effect pair.
4. Learning receives measured outcomes only; absent evidence produces no fabricated reward.
5. The lab-only boundary remains enforced.
6. Existing Aethel, Turing, Chronus, Salamander, mining protocol and evidence owners are not duplicated by stale archive copies.
7. Tests prove that EUCLID cannot change Bitcoin consensus/proof truth.
8. Reviewer-facing capability traceability maps every active spec/whitepaper promise to implementation, runtime reachability, evidence and claim boundary.

Anything short of this remains **PARTIAL / RECOVERED / DISCONNECTED** and must be labelled that way.

## Enterprise migration destination

The intended later destination is `QuantumPhiEnterprise/UnifiedEnterprise`. The current GitHub connections cannot access that repository: the working `bollingertm` connection receives 404 and the HYBA connection is currently suspended. No substitute Enterprise repository is being used.
