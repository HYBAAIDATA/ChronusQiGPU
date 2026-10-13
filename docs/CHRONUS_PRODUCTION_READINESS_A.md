# CHRONUS production-readiness — Agent A evidence record

Baseline: `b1d68b8661d944270c6394fac3a6b99a4299ec4d` (`fix(chronus): fail closed on
unverified hardware-rooted claims`). Executor hardware: CPU-only Windows box —
**no physical GPU/iGPU**, so all device-bound execution evidence is GATED or
UNAVAILABLE and every such path was verified to fail closed.

## Canonical read record

Notion MCP was unreachable in this session (no `notion` server in the MCP
catalog; integrations API shows Notion installed but this session has no MCP
grants; messaging the orchestrating parent session returned 403). Every
canonical page is therefore recorded MISSING and the work proceeded from the
contracts in the programme prompt:

| Page | ID | Status |
| --- | --- | --- |
| Canonical register | 3f0bcc6fa49981c68659c178cbb72a19 | MISSING |
| Shared triad record | 1315c7dc5d8042488b2e6e2ad4252e5b | MISSING |
| Change & risk log | 3f0bcc6fa49981a6b944cf2040030f58 | MISSING |
| CHRONUS manual | 3f0bcc6fa49981ef9b12f67cab2d5f21 | MISSING |
| Chronus WF01–WF08 (children of manual) | incl. ...a132b7b1c12ce9b153a1, ...a196a304ec190ff50525 | MISSING |
| THESEUS manual | 3f0bcc6fa4998106bbd3f0438cfa393e | MISSING |

## Requirement → implementation → evidence

| Requirement | Implementation | Evidence | State |
| --- | --- | --- | --- |
| hardware_rooted requires corroborated attestation | `chronus/virtual_igpu/runtime.py::_hardware_root_corroborated` re-probes the adapter and requires `att.hardware_rooted`, `trust_class == hardware_rooted`, `digest_json(record) == fingerprint`, `extend_chain((), record)[-1] == chain_digest`, `verify([record], chain)`; uncorroborated claims downgrade to `runtime_signed` | `tests/test_chronus_hardware_rooted_adversarial.py` (9 tests): self-asserted claim, fabricated digest, missing chain, altered fingerprint, chain mismatch, probe failure, software-id — all downgrade; legitimate full attestation survives; ledger records the downgrade | PASS |
| Byte quota admission | `Quota.submitted_bytes` enforced in `submit()` over canonical JSON of `w.input` | `test_chronus_runtime_lifecycle.py` single + cumulative byte-quota tests | PASS |
| deadline_ms enforcement | Non-positive rejected; execution wrapped in `_execute_with_deadline` (daemon thread + `join`); timeout yields `status="timeout"` result + receipt | lifecycle tests: nonpositive-deadline rejection, timeout result/receipt, fast-enough pass | PASS |
| Cancellation | `cancel()` records id; post-completion results for cancelled ids report `status="cancelled"`, `error="cancelled before completion was reported"` | lifecycle tests: cancel → cancelled status + receipt verification; unknown id → False | PASS |
| Device loss / adapter death | re-probe excludes dead adapters; required-adapter unavailable → `AdapterUnavailable`; preferred falls back to CPU | lifecycle tests: dead-adapter exclusion + preferred-adapter fallback | PASS |
| Recovery hooks | `recover()` added: READY → refresh re-probe; FAILED/RECOVERING/DETACHED → RECOVERING → re-probe → READY or FAILED; budget `_max_recoveries=3` then failed closed; no adapter → fails closed | lifecycle tests: FAILED→READY, budget exhaustion, no-adapter fails closed, submit-from-FAILED rejected | PASS |
| Scalar/sub-foldable operand custody | `store_tensor` (tensor/api.py) and `_fold_as_deep_as` (tensor/benchmarks.py) now try `depth=0` as honest floor; 1-element scalars fold degenerately and `scale`'s declared domain is reachable | scale store+execute e2e (`path: lifted`, correct); `bench_scale.json` | PASS (defect fixed) |
| CUDA execution | `chronus/native_hash.py::sha256d_batch_cuda` — real CuPy RawModule path over `kernels/bitcoin_sha256d.cu` (genuine SHA-256d: K-constants, message schedule, two-block compression) | `probe_cuda` fails closed with reason on this box (no CuPy/device) | GATED — no device |
| Metal execution | `sha256d_batch_metal` always raises `NativeHashUnavailable` (kernel not production-verified); `probe_metal` fails closed | code inspection + probe | GATED — UNAVAILABLE by design |
| embedded / cloud_instance delivery | `chronus/delivery.py::probe_embedded`/`probe_cloud_instance` descriptive-only, fail closed, no cross-backend fallback | code inspection | GATED — no remote endpoint |
| Tensor compute ops | FOLDED_OPERATOR_CATALOGUE: add/hadamard/scale/fma (lifted), matmul/kron (committed), reduce_sum/transpose (materialized) | `docs/evidence/bench_*.json` — real measured numbers below; all `correct: true`, `max_residual: 0.0` | MEASURED |
| Deleted trees stay absent | `hyba_data/`, `golden_quantum_package/` absent from tree; both in `.gitignore` | `git ls-tree origin/main`, `.gitignore` | PASS |
| Kernel mirror integrity | `tests/test_chronus_fabric.py::test_kernel_mirrors_byte_identical` | PASS in worktree (md5 over `kernels/*.cl` vs `chronus/kernels/*.cl` — three identical pairs) | PASS |
| Paradigm + honesty gates | `scripts/paradigm_gate.py` — thesis_bounds, lemma_golden_stride, systems_vigpu_conformance, measurement_schedule_bakeoff, honesty_chaos (incl. `_LyingHardwareAdapter` `hardware_root_not_trusted_from_liar`) | all legs PASS; `docs/evidence/paradigm_triad_latest.json` written by the gate | PASS |

## Measured tensor benchmarks (CPU, f64, 32×32, 3 repeats, depth 3)

| op | path | lifted/committed ns | materialized ns | residual | promoted |
| --- | --- | --- | --- | --- | --- |
| add | lifted | 35200 | 28600 | 0.0 | yes |
| fma | lifted | 46000 | 31100 | 0.0 | yes |
| hadamard | lifted | 31400 | 27800 | 0.0 | yes |
| kron | committed | 581800 | 88000 | 0.0 | yes |
| matmul | committed | 792300 | 31700 | 0.0 | yes |
| scale | lifted | 17300 | 26500 | 0.0 | yes |
| reduce_sum | materialized | — | 21200 | 0.0 | no (honest) |
| transpose | materialized | — | 24800 | 0.0 | no (honest) |

Lifted/committed paths slower than materialized at this size are still promoted
when verified — promotion records `decoded_bytes` honestly (0 bytes decoded on
lifted/committed paths). Small-size measured numbers only; no extrapolation.

## Gate results (this branch)

- `pytest tests/ -k "chronus or tensor or fold or kernel or igpu or opencl or gpu or committed or phi"`: **914 passed, 12 skipped, 0 failed**
- `scripts/import_graph.py cycles`: **17 cycles, 0 new vs baseline** — PASS
- `scripts/import_graph.py layers`: **27 items, 1 new vs baseline** — FAIL, **pre-existing on origin/main** (`tensor/capability.py:145 → tests/test_committed_execution.py`, from main commit 449a05f; baseline predates it). Verified identical on a detached origin/main checkout. Regen touches `scripts/` — outside Agent A trees.
- `scripts/regen_july_manifest.py --check`: **drifted** — **pre-existing on origin/main** (verified identical on detached checkout). Regen writes `manifests/` — outside Agent A trees.
- `tests/test_deploy_sentry.py::test_this_repository_has_no_deploy_path_errors`: **FAIL, pre-existing on origin/main** — stale editable-install finder resolves `turing_universal_quantum_computer` to a foreign checkout → `relative_to` ValueError in `scripts/deploy_sentry.py:110`. Environmental.

## Defects fixed in this branch

1. `deadline_ms` declared-but-unenforced → enforced with timeout results/receipts.
2. `Quota.max_bytes` declared-but-never-checked → byte quota enforced at submit.
3. `RECOVERING` state unreachable → `recover()` with bounded re-probe budget.
4. `cancel()` no late-result honesty → cancelled work reports `status="cancelled"`.
5. Scalar operand cannot fold (`PhiFoldError: cannot fold a segment of 1
   elements`) making `scale`'s declared domain unreachable → depth-0 floor in
   `store_tensor` and benchmark fold ladder.

## GATED / UNAVAILABLE

- CUDA device execution (real path, no device on executor) — fails closed.
- Metal device execution (kernel not production-verified) — fails closed always.
- OpenCL/iGPU device execution — no device; probe paths fail closed.
- embedded / cloud_instance delivery — descriptive probes only; no endpoint.

## OWNER DECISION REQUESTS

1. Notion canonical corpus unreadable from this session — CHRONUS manual,
   WF01–08, THESEUS manual, register, triad, risk log all MISSING. Smallest
   resolution: grant Notion MCP access to executor sessions or export pages
   into `docs/`. Until then, canonical-vs-repo conflicts cannot be detected.
2. Two repo gates (`layers` baseline, july manifest) are stale on origin/main
   independent of this branch. Both need their regen scripts run; the files
   live outside Agent A's owned trees (`scripts/`, `manifests/`).

## CROSS-AGENT DEPENDENCIES

- `scripts/import_graph_baseline.json` and `manifests/` regen (files outside
  Agent A ownership; pre-existing drift on main).
- `tests/test_deploy_sentry.py` env failure (editable-install finder resolves
  to foreign checkouts) — owns `scripts/deploy_sentry.py`.
- THESEUS custody contract: `aethel.theseus` interface used as-is; no
  insufficiency found this round.
