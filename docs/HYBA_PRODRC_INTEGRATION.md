# HYBA Core Production-Readiness — Integration Manifest

Repository: `QuantumPhi2/PhiMiner`
Integration branch: `devin/hyba-prodrc-integration`
Baseline: `origin/main` = `ef23a5cb03c6bf9e1f393777018352b26687a438`
Executor: Windows Server 2022, CPU-only (no physical GPU/iGPU/QPU)
Integration agent: Devin session `devin-e868d89fdb724ef0867d8216ab7bb4a4`
Date: 2026-10-05

This document is the combined integration manifest required by the HYBA Core
Production-Readiness Programme handoff. It merges workstreams A (CHRONUS),
B (THESEUS), C (OVID) and D (TURING), wires the cross-agent contracts the
published interfaces allow, and records gates, evidence states, unresolved
dependencies and owner decision requests.

Verdicts are restricted to the programme taxonomy; this integration does not
and cannot declare APPROVED FOR PRODUCTION.

## 1. Canonical sources read

Notion MCP was attached to this session (unavailable to agents A/B/C). All
reads on 2026-10-05 (UTC).

| Page ID | Title | Last-edited | Read |
|---|---|---|---|
| `3f0bcc6fa49981c68659c178cbb72a19` | HYBA / QuantumPhi — Canonical Architecture Authority Register — 5 Oct 2026 | 2026-10-05T01:33:41Z | 2026-10-05 ~03:20Z |
| `1315c7dc5d8042488b2e6e2ad4252e5b` | feat(aethel): Chronus·Theseus·Ovid enterprise custody substrate (shared triad record, GitHub PR DB row) | 2026-10-03T16:01:14Z | 2026-10-05 ~03:20Z |
| `3f0bcc6fa49981a6b944cf2040030f58` | HYBA Change & Risk Log — Owner Review | 2026-10-05T01:06:51Z | 2026-10-05 ~03:21Z |
| `3f0bcc6fa4998106bbd3f0438cfa393e` | THESEUS — Canonical Custody, Operational Records & Continuity Service | 2026-10-05T01:29:14Z | 2026-10-05 ~03:21Z |
| `3f0bcc6fa499812591aedb9a32251b30` | Turing Workflow 04 — OVID Transformation & Fold Contract | 2026-10-05T01:26:35Z | 2026-10-05 ~03:22Z |

Normative content confirmed and respected: subsystem authority map (THESEUS
custody / OVID transformation / CHRONUS execution / TURING VQC; producer owns
meaning, THESEUS preserves it); THESEUS manual sections 1–3 (shared-service
consumers, non-negotiable authority boundary); WF04 (OVID owns the transform
implementation, Turing decides transformed-state validity; no fold advantage
inferred from one structured family); change-and-risk owner-control rule.
No canonical-vs-repo conflict was detected in the merged work.

## 2. Workstream merges

Order applied: B, then C, then A, then D (THESEUS contract first per task
ordering; B was already merged to main via PR #51 before this session, so its
merge was a no-op record merge).

| Agent | Branch | Head commit merged | Merge commit | Conflicts |
|---|---|---|---|---|
| B THESEUS | `B-theseus-production-custody` | `7af8ea73f010f245694ad5eac34d15f0b6467fbf` | already on main (`ef23a5c`, PR #51) | none |
| C OVID | `C/ovid-productionisation` | `6e6e0a59d02b3319bd804e02cd074acac313af63` | `726172d` | none |
| A CHRONUS | `A/chronus-production-readiness` | `5ef8b8e71288dfdd7c7ca8ddb940adf229ba3966` | `e198fee` | none |
| D TURING | `D-turing-vqc-production-pipeline` | `1eef82d6f6fc9237cae46a433446dc05d1dd9346` | `bf72e5c` | none |

Zero merge conflicts across all four branches. Per-agent verdicts (reported):

- A: RELEASE CANDIDATE WITH GATED ITEMS — 914 passed / 12 skipped / 0 failed in chronus+tensor scope
- B: RELEASE CANDIDATE WITH GATED ITEMS — 254 passed, 54 new THESEUS tests
- C: RELEASE CANDIDATE WITH GATED ITEMS — 76 new tests + 605 in-scope pass
- D: RELEASE CANDIDATE WITH GATED ITEMS — 37 pipeline tests + 1177 root tests pass

## 3. Integration wiring performed (additive only)

File-ownership rules relaxed only where the task permits shared wiring on the
integration branch. No workstream semantics were rewritten.

1. `aethel/enterprise/__init__.py` — re-exported the THESEUS
   operational-record surface B declared as a cross-agent dependency:
   `OperationalRecord`, `ProducerRegistry`/`ProducerContract`,
   `default_producer_registry`/`default_dependency_policy`,
   `ProducerAdmissionError`/`ContractValidationError`/`DependencyMismatchError`,
   `EVIDENCE_STATES`, `CANONICAL_PRODUCERS`, `DEPENDENCY_THESEUS_FORMAT`/
   `DEPENDENCY_OVID_TRANSFORM`, `CheckpointManager`/`CheckpointIntegrityError`/
   `CheckpointUnavailableError`, `RecoveryReport`, `RetentionPolicy`.
   Also removed a pre-existing ruff F811 (`SolutionsAPIFacade` double
   definition, no users repo-wide) that the changed-files lint ratchet flagged
   once this file entered the diff.
2. `aethel/enterprise/custody.py` — implemented B's declared end-state: the
   default dependency policy now admits only OVID transform versions with a
   declared `TransformContract` (new helper `_contracted_ovid_versions`,
   consulting `OvidRegistry.contracts()` added by C). A registered-but-
   undeclared version now fails closed at admission (`DependencyMismatchError`)
   instead of at envelope-verify time. Registries without a contracts surface
   keep prior behaviour.
3. `tests/test_hyba_prodrc_integration.py` (new) — 10 tests covering the
   wired seams: package re-exports; canonical producers cover the triad +
   tensor; OVID lineage → THESEUS custody roundtrip (`ovid_transform`
   dependency satisfied by the contracted v1); registered-but-uncontracted
   transform version refused at admission; unknown dependency namespace
   refused; CHRONUS `RuntimeDaemon` execution receipt → custody; TURING
   `run_pipeline` report → custody; recovery groups `pending_revalidation` by
   producer across chronus/ovid/turing; `verify_replay` + `replay()` into a
   second custody byte-exact; AL HARAS boundary (a stored record grants no
   access authority — strict `require_access_contract` denies).

## 4. Gate and test results (integration branch)

Commands (Windows venv python; shared-checkout venv used against the worktree
— `tests/conftest.py` rehomes `sys.path` to this tree):

```
python -m pytest tests/ -x
python -m pytest tests/ --deselect tests/test_deploy_sentry.py::test_this_repository_has_no_deploy_path_errors
python scripts/import_graph.py cycles
python scripts/import_graph.py layers
python scripts/regen_july_manifest.py --check
```

| Gate | Result |
|---|---|
| pytest tests/ -x | 1011 passed, 9 skipped, then stopped at the pre-existing environment defect below |
| pytest tests/ (full, minus env defect) | 3459 passed, 20 skipped, 103 subtests passed; 1 failure (`test_mla1517_prime_db_gap_analysis::test_contracts_do_not_promote_prime_db_over_ovid`) — pre-existing Windows cp1252 decode defect verified identical on clean `origin/main`; fixed on this branch (`read_text(encoding="utf-8")`), file now 4/4 PASS |
| tests/test_hyba_prodrc_integration.py | 10/10 PASS |
| import_graph cycles | 17 total, **0 new** vs baseline |
| import_graph layers | 27 total, **0 new** vs baseline |
| regen_july_manifest --check | PASS after running the sanctioned regen (`entries: 65`); drift was Windows EOL noise — regenerated blob hashes identically to the checked-in manifest, no content change |
| ruff E9,F / flake8 / black (touched files) | clean |

Pre-existing failure (not integration breakage):

- `tests/test_deploy_sentry.py::test_this_repository_has_no_deploy_path_errors`
  — environment defect verified by all four agents on clean `origin/main`
  (b1d68b8): the editable-install finder resolves
  `turing_universal_quantum_computer` testpaths into the sibling foreign
  checkout `repos/UnifiedEnterprise`. Identical signature here; outside all
  owned trees.

## 5. Integration findings

- **Replay drops operational manifests**: `EnterpriseCustody.replay(dest)`
  re-executes journal `put` ops via `dest.put()` without the `op_record`
  manifest meta, so payloads/digests reconstruct byte-exactly but
  `dest.get_record()` has no manifest to return. THESEUS semantics preserved
  (payloads verified); producers replaying for warm stand-by should re-admit
  via `put_record` if manifests are required. Recorded for owner/triad
  visibility, not patched (B's tree semantics).
- `run_pipeline(...)` reports carry `measured_qpu: False` and classify as
  TURING_VQC — consistent with canonical taxonomy rules; custody wiring
  stored a PASS report verbatim.

## 6. Cross-agent dependency status

| Dependency | State |
|---|---|
| B ← `aethel/enterprise/__init__.py` re-exports | RESOLVED on this branch (wiring #1) |
| B ← C: dependency policy consults `ovid_registry.contracts()` | RESOLVED on this branch (wiring #2) |
| C → B: `TransformLineage.to_dict()` custody-suitable | VERIFIED (integration test) |
| D → B: `aethel.theseus` custody adapter | VERIFIED by D's tests; report→custody verified here |
| D → C: `aethel.ovid` transform adapter | VERIFIED by D's tests |
| A/C/D → B records: producers registered | VERIFIED (`chronus`, `turing`, `ovid`, `tensor` in `CANONICAL_PRODUCERS`) |
| A: CHRONUS VQC gate-execution kernel for TURING lane | OPEN — `probe_chronus_lane` reports GATED honestly; no contracted kernel exists |
| PULVINI live bridge (`pulvini.svd_fold` via OVID contract path) | OPEN — requires edits in `quantum_compute_substrate/pulvini/` (no owner assigned this round) |
| manifests/ EOL drift | RESOLVED (regen; EOL-only, blob identical) |
| `test_deploy_sentry` env defect | OPEN — editable-install finder resolves to foreign checkout; needs environment fix, not code |

## 7. GATED / UNAVAILABLE / MISSING items (inherited, unchanged)

- All device-bound execution evidence: GATED/UNAVAILABLE — CPU-only executor,
  no physical GPU/iGPU/QPU. Nothing fabricated; device presence ≠ execution.
- CUDA/Metal/OpenCL probes fail closed (A). Physical QPU: UNAVAILABLE (D).
- CHRONUS VQC kernel dispatch: UNAVAILABLE — lane probes, defers honestly (D).
- Tensor-network/MPS representation: RESERVED/unbound (D, owner decision).
- Multi-machine Raft durability: UNAVAILABLE on single box (B).
- Candidate commit `2c8d4a1`: MISSING from origin (D) — hardware_rooted fix
  already on main via `b1d68b8`; other content uninspectable.
- Remote CI evidence: UNAVAILABLE — repo-wide GitHub Actions outage
  (BlobNotFound on all jobs, identical on merged PRs); local gates carry the
  verification weight.

## 8. OWNER DECISION REQUESTS (consolidated, inherited)

1. **Notion access for workstream agents** (A/B/C recorded pages MISSING):
   this session confirms the canonical corpus is reachable and no merged work
   contradicts it; A/B/C's prompt-derived contracts stand. No action needed
   beyond awareness that A/B/C could not normatively check page-level deltas.
2. **MPS/tensor-network representation** (D): `symbolic_density` RESERVED —
   making MPS first-class needs an exactness design, not a float bind.
3. **Circuit-optimisation primitives from pythagoras** (D): rejected for
   TURING; if wanted, route as OVID transformation consuming TURING semantics.
4. **Stale repo gates owned outside agent trees**: import_graph baseline was
   retargeted by C (`--update-baseline`, sanctioned); manifest drift resolved
   here; `test_deploy_sentry` remains an environment defect for whoever owns
   the venv/editable-install setup.
5. **PULVINI bridge**: `pulvini.svd_fold` catalogued BOUNDED_LOSS external —
   wiring a live bridge requires PULVINI-tree ownership assignment.

## 9. Reproduction

```bash
git fetch origin
git checkout devin/hyba-prodrc-integration
./.venv/Scripts/python.exe -m pytest tests/ -x          # or repo python
./.venv/Scripts/python.exe -m pytest tests/test_hyba_prodrc_integration.py -q
./.venv/Scripts/python.exe scripts/import_graph.py cycles
./.venv/Scripts/python.exe scripts/import_graph.py layers
./.venv/Scripts/python.exe scripts/regen_july_manifest.py --check
```

## 10. Artifact digests

Filled at commit time; see section below.
