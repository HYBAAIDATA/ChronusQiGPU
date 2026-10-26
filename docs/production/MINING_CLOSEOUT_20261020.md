# Mining / TOE / SALAMANDER closeout — partial implementation

**PRODUCTION READY: false. PUBLICATION READY: false. HOLD.**

Runtime candidate frozen at `80fe0d413255c45b910da4599e4d276bc9098321`, based on main `4f71b5647e5cacd053e9a9d545ab5f26d38b4f34`. Documentation/evidence-only commits may follow this runtime SHA; they do not retroactively make it fully qualified. No production tag was created.

## Delivered

- Off-event-loop, single-worker hash windows; cancellation drains native execution instead of abandoning it during device teardown.
- Superseded negotiated targets invalidate stale generations before submission.
- Actual healer mutations run through the canonical recovery governor, sharing its recovery ID; missing/denied/incomplete actuation cannot produce a success ACK.
- Lease-clearance postconditions are observed; one recovery observation cannot verify unrelated recoveries; measured elapsed time replaces the fabricated fixed 1 ms.
- Optimizer unlock occurs only after successful same-generation/fingerprint rebind. Missing or changed work remains inhibited.
- [Actual wiring map and missing joins](../MINING_WIRING.md), two new regression modules, and raw evidence.

## Fresh execution on the candidate export

| Run | Result | Qualification meaning |
| --- | --- | --- |
| New mining/healer regressions | 15 passed, zero skips/failures | Local TCP Stratum fixture; real governor/optimizer/agentic lease objects with a fixture coordinator; no real device/pool/custody claim |
| Same new tests under `python -O` | 15 passed; expected pytest warning retained | Same fifteen cases, not thirty independent tests; pytest rewrites test assertions while ordinary imported assertions are disabled |
| Existing mining + SALAMANDER suites including new cases | 34 passed, 1 failed | Scaled execution receipt caller cannot import missing exported nested TURING `turing_core`; this is not a repository-wide absence claim or a passing caller qualification |
| TOE runtime + API + ASI | 67 passed | D/E and API subset only; not full Gate A/G deployment certification |
| Mining consensus boundary | Collection exit 2 | Genuine missing export dependencies restored incrementally; latest blocker `chronus.mla1517.quantum`. Initial errors/logs retained. No agent C pass invented |
| Gate B enterprise collapse | 16/16, all_passed=true, exit 0 | Fresh scoped export run; prior PR #124 16/16 remains accepted separately. No physical-quantum/causal-universality/production-domain claim inferred from experiment prose |
| New-test critical lint | 0 under E9,F63,F7,F82 selection | Not full flake8 / Gate A |
| Negative control | 12 failed, 3 passed against original miner window/target + original healer logic | Optional scaled-import isolation retained to expose the targeted code, and additive governor API retained. Some failures identify new APIs, not distinct defects; not a twelve-defect count |

No counts are summed across overlapping runs. Earlier supervisor/operator passes retain their original source and scope; they are not transferred to this candidate.

## Provenance and limitations

The runtime SHA is a genuine GitHub commit, not a fabricated local tag. This environment has a **partial genuine source export, not an authenticated complete clean Git checkout**. No empty `git status`, full ROOT identity, baseline tag, full worktree or installed-wheel attestation is asserted. Five changed runtime/test file digests bind the exact pushed payload. Current Chronus mining directory base comparison matched 75 unmodified files, with only recovery_authority.py intentionally changed. Other earlier genuine dependency exports remain hash-listed rather than silently declared fully refreshed.

Source manifests before/after the frozen run are attached. No runtime or test source changed during it. Gate B rewrote generated experiment JSON: `toe_enterprise_collapse_results.json` is copied separately; `quantum_lucas_scaling_results.json` is recorded as an expected generated-output diff. This is not an all-files/mid-run manifest-diff-zero attestation. Restoring learning.py after the initial run is separately recorded for the later failed consensus retry; it does not change runtime/test candidate bytes.

A Python worker thread cannot forcibly interrupt a hung native driver. Device-context thread affinity, actual GPU execution, backend shutdown under device faults and bounded driver recovery require hardware tests. The TCP fixture is a localhost fake Stratum endpoint, **not a Bitcoin Core regtest node or external testnet pool**. It proves client mechanics only. It does not prove canonical RecoveryGovernor participation in socket failover, live shares, 30-second operational failover or a four-hour heartbeat p95 SLA.

## Task disposition — no silent completion

| Plan item | Disposition | Remaining evidence / owner lane |
| --- | --- | --- |
| Baseline + RC | PARTIAL | Real base/runtime SHA and payload hashes delivered; complete clean checkout/tag and dependency closure still needed |
| Wiring map | DELIVERED, gaps explicit | Reconcile canonical/standalone/TypeScript entrypoint lineage; no research-to-live promotion |
| Boundary suites | PARTIAL | New 15 and fast 67 green; one legacy caller import failure and consensus collection error remain |
| Gate B | SCOPED PASS 16/16 | Full-source RC rerun required for global release qualification |
| Regtest/socket recovery chain | OPEN | Real regtest/testnet canonical client + one governor + healer inhibition/verified resume, difficulty jump, receipts |
| Four-hour heartbeat | OPEN | Replay/live artifact with p95 <2 s; no claim from sub-second fixtures |
| Ordering A/B | OPEN | Frozen held-out header/work budget, Hendrix/geodesic versus linear; SHA256d acceptance and measured outcomes only |
| Multi-process rate limiting | DEFERRED / RELEASE BLOCKER for multiworker service | Real Redis atomicity/outage/tenant/load proof and deployment configuration; no in-memory fallback claimed |
| Service hardening/container/SLA | PARTIAL HISTORICAL / NOT REQUALIFIED | Deployed payload cap/auth/key policy, timeouts, tenant stress, health/ready/metrics and monitoring |
| Mining Gate F | OPEN | Real telemetry fixtures, domain negative controls, planted-driver rank-1, drift and named mining operator approval |
| Custody/audit/rollback | OPEN | Canonical THESEUS sink + restart/export/restore drill, not local mirror alone |
| Hardware/licenses/legal/sign-off | OPEN | Respective lane owners; no waiver or signature invented |
| Gate H | REPORT UPDATED; approval false | All required gates/owners must be green before readiness promotion |

No mainnet action, merge, tag, deploy, registry upload or manual paid-workflow dispatch occurred. GitHub automatic checks are not certified by `[skip ci]`. No `production_ready` configuration was enabled. The documentation-only PR #127 is untouched.

## Reproduction commands

Run from a complete checkout of the runtime SHA, using real dependency closure and separate basetemps. No substitute engine/custody modules are permitted.

```bash
python -m pytest mining/tests/test_closeout_window_isolation.py salamander/tests/test_mining_healer_dispatch_closeout.py -p no:cacheprovider --basetemp=/tmp/hyba-closeout-safety -q
python -O -m pytest mining/tests/test_closeout_window_isolation.py salamander/tests/test_mining_healer_dispatch_closeout.py -p no:cacheprovider --basetemp=/tmp/hyba-closeout-safety-opt -q
python -m pytest mining/tests salamander/tests -p no:cacheprovider --basetemp=/tmp/hyba-closeout-compat -q
python -m pytest tests/test_toe_runtime.py tests/test_toe_ciaas_api.py tests/test_asi_core.py -p no:cacheprovider --basetemp=/tmp/hyba-closeout-toe -q
python -m pytest tests/test_toe_consensus_boundary.py -p no:cacheprovider --basetemp=/tmp/hyba-closeout-consensus -q
python experiments/toe_enterprise_collapse.py
```

Actual environment/commands/basetemps/log exits are in `release-evidence/mining-closeout-20261020/frozen/report.json`. The exact export reproduction needs the listed manifests/dependencies; a fresh full checkout may expose additional failures and must not be pre-labelled green.
