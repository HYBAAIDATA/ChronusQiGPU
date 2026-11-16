# ChronusQiGPU — source, archive and runtime-evidence reconciliation

**Reviewed 2026-11-16 UTC.** Private repository `HYBAAIDATA/ChronusQiGPU`.
**Pinned starting `main` commit:** `35676f79a743914d95f1bcee0367edaf7ba19fd0` (the branch may advance after this snapshot).
**Decision:** **NOT QUALIFIED**. This is a source-to-requirement and targeted defect review, not an executed whole-repository test run, deployed runtime inspection or release certificate.

## Source authority and provenance

1. The supplied 29 October 2026 *HYBA Mining Runtime (MT)* review audited a **PYTHIA TypeScript/parallel Python mining snapshot**, including `hybaMiningRuntime.ts`, `routes/mining.ts` and `miningRunEngine.ts`. Those precise TS paths are absent from this maintained repository. The old RFX instructions must be treated as historical risk leads, **not** blindly implemented as new parallel controllers.
2. The authoritative 5 October Notion register (as subsequently reconciled with enterprise triad decisions) controls ownership: CHRONUS execution, OVID transformation, THESEUS durable custody, TURING independent VQC, EUCLID orchestration, PYTHIA mining intelligence, Salamander healing, AL HARAS security. The mining-only D9 inversion of OVID/THESEUS in the historical review is superseded.
3. The 15 November Notion page *ChronusQiGPU — Mining Production Readiness & Chronos/Tensor Reconciliation* is a requirements and historical observation source. Its symbol-absence finding has now been superseded by a fresh source inspection. Notion historical test counts are provenance only.
4. No external pool, GPU, QPU or service deployment was executed by this audit.

## Recovered archive inventory — originals, not duplicated into production

| Source artifact | Verified raw archive SHA-256 | Disposition |
| --- | --- | --- |
| ChatGPT Library `GEODESIC_TENSOR_ENGINE_EXTENDED_20260724.zip` (3 entries) | `43d4d3a39fd13fb525bf3acf0b822af1ef55c6b801616aeb9bf326a76dcfa44b` | Source inspected: `geodesic_tensor_engine.py` and two historical test modules. Preserve as historical baseline; current maintained classes already exist. |
| ChatGPT Library `HYBA_PULVINI_V3_OWNER_RESEARCH_HANDOFF_20261115.zip` (18 outer entries) | `561d0b9cec7aa4ae80117f9267f44abc53328ecfe46445c51123261e846032cc` | Contains embedded original 20260724 archive and `integration_seam` with PULVINI files, lock and tests. Compare the existing guarded active files before importing any patch. |
| ChatGPT Library `chronus_remediation_bundle_2026-11-15.zip` (4 entries) | `e14ad66c22d3ddf2ebb3da4d38426374de0454c1567d5c8655e7ec5e4a0e784a` | Historical patch, audit and two test files; do not replay patch without confirming the current source baseline. |

Zip members were listed and archived source class definitions inspected. Archive SHA-256 means the source archive was read intact; it **does not** establish current implementation equivalence, execution or historical benchmark reproduction.

## PULVINI owner handoff: exact Git-blob equivalence

The recovered `HYBA_PULVINI_V3_OWNER_RESEARCH_HANDOFF_20261115.zip` was
unpacked offline and its `integration_seam/` files compared with the active
private repository using Git blob SHA-1 (the same hashing rule GitHub exposes
on its `fetch_file` API). This comparison is stronger than a class-name match:

| Recovered file | Git blob SHA-1 | Active tree |
| --- | --- | --- |
| `src/chronus/pulvini/formal.py` | `863c0397e9c9e8ee9935183f4b736153b8160f8b` | **IDENTICAL** |
| `src/chronus/pulvini/interop.py` | `6b6a9d848799235de1427c2d31e04cf33a6139c7` | **IDENTICAL** |
| `src/chronus/pulvini/__init__.py` | `7710d94658f7bae88f202866214fc23f4343c062` | **IDENTICAL** |
| `tests/test_pulvini_research_locked.py` | `5a907423a0da88927ffca0278868e55a81ad9939` | **IDENTICAL** |
| `tools/verify_pulvini_lock.py` | `417d3fb7ba5068bbf8c7cfc885f719b0354ae539` | **IDENTICAL** |
| `.github/workflows/pulvini-research-guard.yml` | `66c6189e165a4e18b17243053b360d0d240ee7b0` | **IDENTICAL** |

The archived `docs/research/PULVINI_V3_FOLD_AUTHORITY.md` differs from the
current maintained document, which contains later amendments. **Do not overwrite
the later source-of-truth document with the older handoff.** Repository ruleset
enforcement and green CI are separate from byte equivalence; issues #98 and #92
remain open.

The recovered October `HYBA_Library_Millennium_Recovery_2026-10-28.zip`,
`HYBA_1000_QUBIT_VQC_20260724.zip`, `hyba_final.zip` and
`HYBA_Consolidation_Elevation_2026-10-28.zip` were also inventoried offline.
Their filenames alone do not establish compatibility or transfer authority.
The available archive inventories contain no `kellogg/` source package.
Notion records identify formerly merged Kellogg implementations at
`QuantumPhiEnterprise/PYTHIPhiMiner` PRs #55 and #59, but the historical
private repository is currently not accessible through the GitHub connection.
**Kellogg source recovery/compatibility remains UNAVAILABLE**, not restored.

## Newly wired security and governance paths

- `src/chronus/security/durable_receipts.py` provides versioned, signed
  receipt custody/restart replay against canonical `DurableTheseusService`,
  without transferring custody authority to AL HARAS or preserving private keys
  in the store. `src/chronus/core/facade.py` Gate G2 now exercises restart,
  signature, wrong-key and tamper negatives.
- `src/chronus/service/mining_operator.py` is the AL HARAS authorisation
  dependency on **all eleven** shared mining-administration routes (nine
  mutating and two read-only). It derives a verified JWT identity from the
  maintained authentication middleware; requires exact system-admin, subject
  allowlist and owning tenant; rejects legacy tenant-only tokens; records
  durable operator **admission**, not success.
- Both Kubernetes manifests now use `/health/ready`, not an authenticated
  global mining endpoint masquerading as readiness.
- Tests cover genuine JWT admission and denial, tenant isolation, missing
  custody, receipt restart, spoofing, mutation and tamper. See
  [operational contract](../security/mining-operator-admission-and-receipt-custody.md).
- The legacy `src/chronus/access_control.py` remains **UNBOUND / NOT
  AUTHORITATIVE** under issue #91. The new routes do not import it. No fabricated
  default exposure is promoted and no new competing security authority is
  introduced.

## Active code reconciliation

| Capability / authority | Current repository source | Regression surface | Disposition |
| --- | --- | --- | --- |
| PhiTensorCore | `src/chronus/tensor/geodesic.py` | `tests/test_geodesic_tensor_migration.py` | **SOURCE-PRESENT / TEST-PRESENT**, not runtime-qualified |
| GeodesicScheduler | Same; consumed by `src/chronus/execution/mining_scheduler.py` | Same | **SOURCE-PRESENT / TEST-PRESENT** |
| PhiMemoryHierarchy | Same; resident `ExactFoldState` type and selective loads | Same | **SOURCE-PRESENT / TEST-PRESENT**; logical tier labels are not physical memory measurements |
| TopologicalIntegrityGate | Same; operation-output checks | Same, plus `tests/test_tensor_hamiltonian_contract.py` | **SOURCE-PRESENT / TEST-PRESENT**; not a mathematical proof of full topological equivalence |
| PULVINI exact fold/reconstruct seam | `src/chronus/pulvini/formal.py`, `interop.py`; research guard workflow | `tests/test_pulvini_research_locked.py` | **SOURCE-PRESENT / TEST-PRESENT**; enforced independent owner ruleset and exact-commit green CI remain unresolved |
| Canonical triad | `src/chronus/triad.py`, OVID transform, THESEUS durable SQLite service | Maintained tests under `tests/` | **SOURCE-PRESENT**; actual deployment/fresh-process recovery evidence remains separately required |
| TURING VQC | `packages/turing/` | Package tests | **SOURCE-PRESENT**; no physical QPU advantage is established |
| Live Stratum mining | `src/chronus/execution/mining_entrypoint.py`, `src/chronus/stratum/` | Mining readiness and Stratum tests | **SOURCE-PRESENT**, accepted share **UNAVAILABLE** |
| Historical Kellogg exact tensor contract | No current named complete contract has been established by this audit | **UNVERIFIED** | Preserve as archive integration candidate; do not create an alternative tensor authority |
| Historical TOE/world-model or PYTHIA TS routes | Not current-owned paths in this repo | **NOT A LITERAL PORT TARGET** | Coordinate through governed adapters with their own authorities; no new mining lifecycle |

Four items previously marked missing in `docs/notion-production-readiness.md` are present in the current maintained tree; this branch corrects that map. No copy of the older 83-kilobyte monolithic engine is needed.

## Confirmed current defect addressed on this branch

`src/chronus/service/routers/mining_admin.py` reported a `SUCCESS` message that four named external pools had accepted **100%** of shares after `execute_master_end_to_end()`. The runner in `src/chronus/execution/master_e2e_engine.py` explicitly starts **127.0.0.1 LocalStratumTestServer fixtures**, not live pools. It also logged a 3µs assertion without latency measurements and did not require a successful submit response before announcing completion.

This branch changes the API to a fixed local-loopback rehearsal classification, rejects caller pool overrides, returns no fabricated acceptance or qualification, makes rejected fixture acknowledgements fail the runner, removes the latency assertion and adds denial/negative regression tests. **Production impact:** truth boundary improved; **live shares and measured timing remain UNAVAILABLE**.

## Remaining independently blocking work — not waived

| Priority | Blocker | Required evidence or responsible action |
| --- | --- | --- |
| P0 | Release infrastructure, checks and protection | Issues [#92](https://github.com/HYBAAIDATA/ChronusQiGPU/issues/92), [#89](https://github.com/HYBAAIDATA/ChronusQiGPU/issues/89), [#98](https://github.com/HYBAAIDATA/ChronusQiGPU/issues/98): run steps actually execute, required checks green at exact SHA; independently controlled owner must enforce rulesets and reviews |
| P0 | Legacy `src/chronus/access_control.py` is not an AL HARAS authority | Issue [#91](https://github.com/HYBAAIDATA/ChronusQiGPU/issues/91) records broken Role enum, unavailable identity/audit bindings, and fabricated default exposure. Do not activate this module or infer authority from role assertions; implement trusted-boundary checks and adversarial tests in a separate security PR |
| P0 | Production release packet unavailable | Exact SHA/test artefacts, signed provenance, owner approval, credential/tenant isolation, cold-restart THESEUS custody and rollback remain unverified. Reject GO until mandatory product gates pass |
| P1 | Cross-process SQLite first use | Issue [#82](https://github.com/HYBAAIDATA/ChronusQiGPU/issues/82): cold-start/crash/alias-path and corruption qualification with real multi-process tests |
| P1 | In-memory signed receipt compatibility module | `src/chronus/security/receipts.py` documents in-memory custody only. Integrate or explicitly gate before presenting its receipts as restart-durable THESEUS records |
| P1 | Physical acceleration / live mining and 10 EH/s | No exact-commit device census+known-answer+differential+soak evidence or literal pool acknowledgement. Engineering ceilings are not measured rates |
| P1 | Full real-input benchmark | [PR #127](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/127) covers a bounded manifest-based benchmark; operator real input and production-host results are unavailable until provided and run |
| P1 | Current-head CI | Failed / queued Actions have been observed; investigate whether jobs ran any steps before classifying as a source regression. Do not bypass checks |
| P2 | Historic capability equivalence | Compare July API operations and proofs against maintained Geodesic/Tensor, PULVINI and TURING one-by-one; current symbol presence is not a complete byte-for-byte reimplementation certificate |

## Historical archive replay evidence (local, non-qualifying)

The original July Geodesic test modules were executed in a temporary isolated import layout with the November PULVINI handoff's `formal.py`. **115/115 historical tests passed** under Python 3.13.5, NumPy 2.3.5, pytest 9.0.2 at 2026-11-16T06:41Z. This is a mixed-archive compatibility check, **not** a test of current Chronus source, PR head, physical device or mining deployment. Original archive hashes, reconstructed dependency hash, invocation, exit code and local stdout/JUnit digests are recorded at [evidence/migration/2026-11-16-geodesic-archive-replay.md](../../evidence/migration/2026-11-16-geodesic-archive-replay.md).

## Release disposition

**NOT QUALIFIED / RELEASE HELD.** Targeted PR-level source fixes are not merged/current-main proof. No live service was deployed, no pool credentials used, no hidden benchmark generated and no issue or production hold is declared closed without linked evidence. Preserve the historical archives, hashes and failing results for reconstruction.

## Governing references

- [Canonical Architecture Authority Register](https://app.notion.com/p/3f0bcc6fa49981c68659c178cbb72a19)
- [ChronusQiGPU production readiness, 15 Nov](https://app.notion.com/p/419bcc6fa49981cf9e6cecfa7a838b70)
- [Geodesic Tensor Engine/PULVINI V3 engineering record, 24 Jul](https://app.notion.com/p/ffd11e5552144c30ad38a5aaab0b5fcb)
- [PULVINI owner research authority](../research/PULVINI_V3_FOLD_AUTHORITY.md)
- [Current release status](../../STATUS.md)
