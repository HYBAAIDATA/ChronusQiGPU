# Caller compatibility follow-up — 2026-10-20

Status: PASS for the enumerated local caller subset only. Production/publication HOLD. Draft PR #123 must not merge on this evidence alone.
Parent candidate: `7a2e749ef5f4c62299fed14eaac2ebf5e6927bde`.

## Defect and correction

`RuntimeDaemon.submit` persisted FOLD/UNFOLD output using `residency=adapter.id`. The fail-closed memory contract correctly rejects an execution adapter name as proof of allocation; ordinary CPU callers therefore raised `NotImplementedError`.

`chronus/virtual_igpu/runtime.py` now persists returned Python output as `host`, retaining the actual execution adapter ID and explicit `returned_host_output` metadata. Persistence occurs after result finalisation and independent verification and only for status `ok`. Failed, mismatched and timed-out FOLD/UNFOLD outputs receive no successful object handle. This is host-output accounting, not an execution fallback or proof of physical residency. No memory or journal protections are weakened.

## Fresh results

| Run | Result | Evidence under `release-evidence/closeout/caller-compat-20261020/` |
| --- | --- | --- |
| New real runtime/client/wire compatibility tests | 21 passed, 0 failed/skipped | `callers-final.log`, `callers-final.xml` |
| Prior 64 + new 21, normal Python | 85 passed, 0 failed/skipped | `all-normal.log`, `all-normal.xml` |
| Same four modules under `python -O` | 85 passed, 0 failed/skipped, one expected pytest warning | `all-optimized.log`, `all-optimized.xml` |
| Negative control: original parent runtime + new caller module | 12 failed, 9 passed, exit 1 as expected | `caller-negative-final.log`, `caller-negative-final.xml` |

The optimized warning notes assertions outside pytest-rewritten test modules are disabled. It is disclosed, not waived as full optimized-runtime certification.

## Tested caller matrix

`tests/test_chronus_memory_caller_compat.py` invokes genuine package initializers, runtime, ABI, CPU/software adapters, memory, verifier, embedded client and HTTP wire. It covers FOLD/UNFOLD host handles across four tenant strings; STORE/RETRIEVE/restart/cross-tenant refusal; malformed index and lookup; refused physical labels; failed/mismatched/timed-out execution without handles; reservation cleanup; explicit host/folded migration and refused tenantless migration; embedded client; authenticated loopback HTTP and sanitized cross-tenant/401 errors; software-fabric product mode; blob tamper refusal. Synthetic failure adapters test lifecycle behavior only.

Commands used `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `-p no:cacheprovider` and distinct `/data/closeout-followup/tmp/` basetemps. The combined runs collected exactly the four modules listed in `tested_inputs.json`. The unmodified negative-control runtime is separately hashed in the input evidence, and `runtime-caller.patch` records the correction.

## Evidence limits — not closed

- This is a pinned GitHub MCP source subset, not a complete Git checkout. No clean ROOT identity, clean-tree claim, local tag/worktree or installed-wheel acceptance is asserted.
- Optional `aethel.encoding` is absent: CPU fold/unfold follows the documented `length_prefix_identity` fallback. These tests do not qualify enterprise PULVINI folding.
- Local loopback HTTP is not deployed authentication/authorization qualification. No physical GPU/iGPU adapter ran.
- The three inspected original production-readiness/fail-closed/gap-closure test modules were **not collected**; these 85 results do not substitute for them, Arena 100, Sprint 154, v17, ineffable or integration gates.
- STORE's pre-adapter persistence path, global runtime idempotency identity, all external callers, full principal-to-tenant integration and physical allocation/rebind are not qualified by this patch.
- R01/R03/R05 custody completion, full fault-injection matrix, pool recovery, four-hour heartbeat, device evidence, APIs/licenses/legal and rollback drill remain open.
- No merge/tag/deploy/publication/manual workflow dispatch/protection bypass performed. `[skip ci]` does not guarantee automatic CodeQL suppression. PR122 red-check disposition remains unresolved because check-run access returned 403.
