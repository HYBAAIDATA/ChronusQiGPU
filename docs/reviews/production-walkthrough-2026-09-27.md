# Mining-system implementation walkthrough — 27 September 2026

**Release status: NOT production approved.** This integration branch contains concrete
repairs and Azure control-app deployment preparation. Passing software tests do not
establish GPU execution, pool acceptance, an eight-cycle live run, or full compliance
with the supplied mining-system specification. `THEOREM_PROVEN` remains false.

Audit base: `0e5fb6813e284a04df26b278a5990d22e7f5ce02`.
Reviewed open PRs: #4, #5, #6, #7, #9, #10, #11. Changes from #4–#7 and #11 are
integrated locally with additional fixes; #9 and #10 are not merged. This is not a
statement that every review thread in those PRs is resolved. No repository files were
deleted. The Intelligence package is preserved.

## Walkthrough

1. `main.py` starts the canonical Python control API and serves the compiled frontend.
   `control_api.py` supervises workers and reports measured readiness. Health is process
   health; it is deliberately separate from readiness to mine.
2. `mining_runtime.py` constructs the pool coordinator, a read-only Bitcoin RPC observer,
   and a durable `MiningSession`. Live submission requires the observer. A file lock
   prevents two local runtimes from owning the same persisted session.
3. `manifold_pool_coordinator.py` authorizes the Stratum identity, consumes jobs and vault
   records, and calls the lifecycle gate before polling hardware. Device polling runs
   outside the async event-loop thread. Only literal boolean pool acknowledgements count.
4. `chronus/mla1517/mining/coordinator.py` obtains TOE context from the real job/vault record,
   applies control/recovery decisions, and invokes the bounded SHA256d CPU reference
   search on an actual negotiated header. This search currently remains CPU reference;
   it is **not** evidence that the iGPU ran SHA256d.
5. `solver.py` searches at most `L_n` candidates, where `n` belongs to
   `[10, 12, 15, 18, 20]`. The share target and full header come from the proof adapter.
   TOE, chooser and learned lane order can change allocation/order, never proof validity.
6. Before the network submission, `session.py` persists `SUBMITTING`. Every outcome,
   including rejection or uncertainty, goes to `WAITING_EXTERNAL`. A candidate that could
   be our block requires its own confirmed height and a strictly later external block.
   Cooldown must then expire before `SEARCHING` resumes. Unknown outcomes fail closed.
7. Only acknowledged, locally verified winners enter Pythia germ-line memory. Their
   headers are folded using the exact M15 transform. Restart validation hashes a byte
   stream from folded state without assembling a raw header. Deduplication is by digest.
   Recorded winners provide complete 32-lane cyclic permutations for subsequent search.
   These are permitted derived operators, **not evidence of a novel speedup**.
8. `deploy/azure` prepares the control app for Container Apps with a non-root image,
   managed ACR pull identity, Entra authentication, explicit operator allowlist, persistent
   configuration and probes. Ingress starts internal; workers/live submission start off.
   A separate hardware host is still required. A remote control-to-worker protocol is not
   implemented, so the Azure control app must not be described as a working remote miner.

## Findings and disposition

| Severity | Finding / location | Disposition and required next step |
|---|---|---|
| Critical | Canonical live path lacked the required durable lifecycle. `chronus/mla1517/mining/coordinator.py`, `session.py`, `mining_runtime.py` | Implemented for this path; historical-header tests cover restart, exclusive ownership, external-block gating and cooldown. Audit every other direct submission path before releasing the whole repository. |
| Critical | No independently verified external-block observation in that path. `chain_observer.py` | Added Bitcoin Core observation with header/hash/target/active-chain checks. Live RPC and chain-reorganization acceptance testing remain outstanding. |
| High | `submit_record` collected context but did not search. `chronus/mla1517/mining/coordinator.py` | Now invokes real bounded SHA256d search using the negotiated job; stale job results are discarded. Search is CPU reference pending verified hardware integration. |
| High | Fixed Lucas contract differed across runtime layers. `pow.py`, `scaling.py`, `toe_signal.py`, `control_api.py` | Those layers now share `lucas.ladder.FULL_LADDER`. Other research/UI ladder declarations still need consolidation and the entire-system budget audit is open. |
| High | Winner memory did not feed the canonical search. `session.py`, `coordinator.py` | Folded, validated and persistent germ-line winners now determine complete lane ordering. Episodic, semantic and curriculum integration across all six intelligence types remains open. |
| High | Raw-buffer claim was false in folded hashing. `Intelligence/folded_state.py` | Hash queries stream bytes. Explicit restore operations increment the materialization count and reject integrity failures even under Python optimization. |
| High | Two `turing_core` import locations exposed inconsistent folding APIs. `turing_core.py`, platform `turing_core.py`, `lucas/fold.py` | Both export one shared exact fold implementation; canonical packaging now includes the needed runtime modules. The older extended-schedule implementations still warrant consolidation. |
| High | Stricter PR #7 encoder broke real TOE certificate contexts. Both `poincare_golden_11d.py` files | Exact encoder remains fail-closed. Certificate keeps its complete 64-bit identity; only the explicitly many-to-one physical bucket address is reduced to the supported domain. |
| High | iGPU seam / verification findings in PR #10 are unresolved | Do not merge: target byte order, nonce-zero/sentinel handling, authentic executed-window evidence, kernel inputs, and non-fabricated conformance/certificates require fixes and device execution. |
| High | Fabric/security/concurrency findings in PR #9 are unresolved | Do not merge: tenant ownership, idempotency, queued failure replay, scanned-window verification and inline blocking hashes require dedicated regression coverage. |
| High | Strict deterministic/no-heuristics doctrine is not satisfied repository-wide. `python_backend/phi_grover_v4.py`, `structure.py`, ML/research paths | Stochastic and heuristic code remains. Its presence is disclosed; it cannot be counted as specification compliance. Do not present advisory scores as exact spectral observables or cryptographic advantage. |
| High | Azure public control API needs an authorization boundary. `control_api.py`, `deploy/azure/main.bicep` | Prepared Entra gateway configuration and internal-first deployment. Standalone Python API remains unsuitable for direct public exposure. Azure deployment and operator-access tests remain unexecuted. |
| High | Overall CI and hardware evidence are incomplete | Added real frontend unit test invocation and corrected cache/install paths. Added Azure image/Bicep checks. Remote Actions and hardware qualification must pass before merge/release; NOT_RUN is not hardware PASS. |
| Medium | PR #11 shared solution race / nonce width, generator telemetry fault handling | Solution is published before the found flag under a lock; first valid uint32 solution wins. Generator windows are materialized once; malformed telemetry input is contained. These do not certify the stochastic worker. |
| Medium | Benchmark traversal formula miscounted non-coprime stride orbits. `benchmarks/hendrix_vs_grover.py` | Replaced with exact coset/orbit indexing, preserving comparison against the actual traversal. |
| Medium | Generic source inventory and seven-kernel AST discipline are incomplete | Existing broad research/ML modules and missing master-spec root agent layout prevent full single-purpose compliance. Preserve useful Intelligence capability while connecting or explicitly retiring each path through reviewed changes. |

## Verified evidence at initial publication

| Check | Result |
|---|---|
| Frontend TypeScript check | PASS |
| Frontend unit tests | 18 PASS |
| Frontend production build | PASS |
| Focused Python integration suite | 104 PASS |
| New historical-header lifecycle tests (included above) | 5 PASS |
| Python compile of Intelligence/core/mining/HYBA/Lucas/scripts/tests/canonical/backend | PASS |
| Drift sentry | PASS |
| Full Python suite | Not yet green; runs have stalled in existing larger tests; bounded diagnostic run in progress |
| Canonical Python suite, earlier diagnostic | 178 passed, 6 failed, 5 skipped; code regressions repaired in focused suite; Unix-socket test blocked by local environment |
| Live mining / iGPU hardware / Azure deployment | NOT RUN |

Historical-header replay is explicitly an offline regression test. It does not establish
8/8 live winners, specific confidence growth, eleven phase transitions, surrogate trust,
or a measured mining advantage. Those outcomes must come from execution; they must not
be filled in to match the desired transcript.

## Optimization opportunities

| Priority | Opportunity | Evidence required / guardrail |
|---|---|---|
| P1 | Batch real SHA256d work onto the verified OpenCL backend instead of the new scalar reference search | Use identical headers, targets and complete candidate windows; independently recheck every returned winner. Measure hashes, device, latency and transfer time; include nonce 0 and no-hit cases. |
| P1 | Reuse device context, program and buffers for successive mining windows | Profile current allocation/build cost. Prove partial writes preserve untouched data and no stale winner crosses a job boundary. |
| P1 | Share an immutable Stratum job snapshot and cancel obsolete work quickly | Measure stale work and notification latency. Preserve the durable submission gate and exact target/extranonce binding. |
| P1 | Add bounded dispatch backpressure between async pool I/O and compute | One owning session, bounded queues, cancellation and failure propagation; never let throughput changes bypass WAITING_EXTERNAL. |
| P2 | Consolidate duplicate schedules, ladder declarations and coordinator entrypoints | One contract test per production caller. Avoid importing sibling algorithm implementations where the specification forbids it. |
| P2 | Bound winner-history and lifecycle-journal growth | Durable checkpoint plus append-only audit; retain last accepted block safety evidence and exact restart behavior. |
| P2 | Measure learned lane order against a complete neutral order on independent real jobs | Reordering alone proves no speedup. Report attempts, latency and accepted outcomes, including negative results; do not increase trust using training samples. |
| Closed | Make benchmark/test report output explicit and temporary by default | The TOE benchmark test now writes under `tmp_path`; checked-in reports remain unchanged. |

## Closeout gates still open

- Every direct pool submission route uses one durable lifecycle and one authoritative session.
- PR #9 and #10 review defects are fixed with tenant/concurrency/device tests before merge.
- All GitHub checks are green on the exact merge head; no required check is skipped or weakened.
- CPU/iGPU/tensor/TOE evidence records the backend that actually ran; readiness stays false when required hardware is absent.
- Six intelligence types feed agent decisions, all four memory types stay folded, and every claimed discovery is wired with observable effect.
- Seven-kernel routing, fixed ladder, import discipline and deterministic purity gates cover the deployed path.
- Azure image build, Bicep validation, authentication/allowlist, persistence and rollback are exercised in the target account.
- Live device/pool/node run produces the real transcript. Acceptance numbers are observations, not fixtures.

## Follow-up closeout

Additional verified fixes after the initial push:

- Retained the previous candidate block hash across session restarts and rejected a
  new submission whose parent is our own block, including after a chain reorganization.
  Cooldown now rechecks that its external block remains on the active chain.
- Fixed the remaining large logical-identity routing call in Salamander through the
  bounded physical bucket API. Exact Zeckendorf encoding still rejects truncation.
- Shared the complete Turing mathematics through `pythia_turing_math.py`, so importing
  the platform entrypoint no longer hides APIs required by Intelligence's agentic code.
- Corrected two stale TypeScript paths in `Intelligence/registry.py` to the real frontend
  locations. `python -m Intelligence.self_test` now reports **OVERALL: PASS**. Its diagnostic
  verdicts are not live mining evidence or proof of AGI/ASI.
- Changed the TOE benchmark test to write its generated report to pytest's temporary
  directory. It no longer changes a checked-in report as a test side effect.

Follow-up validation: 101 tests across lifecycle, Salamander, benchmark, folded algebra
and canonical Turing passed together. The canonical suite reached **183 passed, 5 skipped,
1 failed**: the remaining failure is AF_UNIX creation denied by this workspace. A full
root diagnostic reached 856 passed; nine multiprocessing tests were blocked by the same
socket restriction, two tests needed an upstream binary fixture that has since been
restored and hash-verified (both now pass), and the million-row load exceeded the local
15-second diagnostic timeout. That load was rerun with a 120-second diagnostic limit
and **passed in 18.68 seconds**, without changing the test or its workload. Repository
Flake8 and the canonical Black gate pass; Turing self-verification passes.

Final full-root rerun: **859 passed, 9 failed, 3 skipped, 92 subtests passed** in
54.41 seconds. All nine failures occur before test logic when multiprocessing.Manager
attempts to create a Unix socket (`PermissionError: Operation not permitted`). They are
not skipped or weakened in CI. The earlier fixture and diagnostic-timeout failures are
resolved. Together with the canonical suite, this leaves ten local socket-restricted
tests requiring execution on an unrestricted runner.

### GitHub CI execution blocker

PR #12 was published at commit `940ca7db7e433a35af6de788ccbda04702342200`.
All initial Actions checks reported failure **before executing any steps**. The fetched
job records have `steps: []` and no assigned runner name; job-log retrieval returns
BlobNotFound. Examples:

- https://github.com/QUANTUMDATA2/PYTHIAPhiMiner/actions/runs/36289514018
- https://github.com/QUANTUMDATA2/PYTHIAPhiMiner/actions/runs/36289513975

The underlying account/runner restriction is not identified by the accessible API.
Inspect the run annotations and repository/account Actions settings to establish and
resolve the cause, then rerun on the exact branch head. Do not infer a code failure or
claim green checks from these pre-execution failures. No gate was disabled, no failing
check was converted to success, and no PR was merged while this blocker remained.

These are release blockers, not completed TODOs. This report intentionally does not mark
unexecuted work done or close unresolved PRs just to reduce the open count.
