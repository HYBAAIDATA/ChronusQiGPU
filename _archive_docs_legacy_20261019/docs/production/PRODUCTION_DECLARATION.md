# Production Declaration — Chronus @ QuantumPhi2/PhiMiner

**Pin:** `main` @ `d1cb649` + the ledger fixes carried in this PR
**Generated from:** `docs/production/gate_ledger.md` (the executed ledger — every claim below cites it)
**Host truth:** Windows, Python 3.12.10, Node 20.19.0, **no OpenCL platform, no C++17 toolchain**

This document is the declaration step of issue #38 ("gate ledger to production declaration"). It states, per surface, what is **declared**, what is **conditionally declared** (declared for the environments whose prerequisites were exercised), and what is **not declared** — with the exact unblock requirement for each gap. Nothing here is asserted without an executed row in the ledger.

## Declared

| Surface | Declaration | Evidence |
|---|---|---|
| Assurance gate ledger | The 11-gate `make gates` ledger executes end-to-end and is aggregated by `assert_gate_rollup.py` — **10 PASS / 1 GATED** (privileged-path-audit, secret-bound). Every gate now emits `results/<gate>.json`, including rule7-no-float which previously produced none | `docs/production/gate_ledger.md` §1 |
| Exact math core | No floating point in the declared exact core — **17 paths** scanned (3 canonical + the 14-module `chronus/mla1517/` core) on Windows as well as POSIX | `results/rule7-no-float.json`, ledger defect #2 |
| Resilience suite | Present — supervisor crash recovery, custody replay, attestation policy, adversarial hardware-root compound failure | `results/resilience-suite.json` |
| Promotion manifest evaluation | All 7 subsystem targets evaluate `achieved == target` (guardian, identity, witness, schema, mediation: CONTRACTED; folded, pisot: RESEARCH) | `results/assurance-gates.json` |
| Test corpus | Root pytest **3497 passed / 20 skipped / 0 failed**; platform unittest **415 / 7 skipped**; TUQC pytest **197 + 39 subtests**; frontend **45 tests**, lint + build clean | ledger §Test surfaces |
| Paradigm + honesty gates | 5/5 legs including `_LyingHardwareAdapter` negative test | `docs/evidence/paradigm_triad_latest.json` |
| Chronus-1 ISA | 20-instruction acceptance PASS (barriers, divergence, matmul expressible) | ledger §Chronus |
| Remote GPU agent deviceless contract | Fail-closed verified live: valid work 503 / malformed 400 / unknown 404 — never a silent CPU fallback | `docs/evidence/remote_gpu_agent_deviceless.json` |
| Deployment claims discipline | External docs respect `claims.yaml`; re-paper gate PASS | ledger |
| Release gate (software profile) | rule7 console + MLA1517 reference runtime + 64-byte ABI | ledger |
| Ovid lineage | `lineage_id` is now execution-unique by construction (execution sequence mixed into the id material; `transform_ns` remains evidentiary) | `aethel/ovid.py`, `tests/test_ovid_contracts.py` |

## Conditionally declared (software surface only)

| Surface | Declaration | Condition |
|---|---|---|
| Application production preflight | PASS for the `application` profile (imports, writable `data/`, Python 3.12) | Device and live-pool profiles unexercised — they fail closed by design without `MLA1517_STRATUM_*`/`HYBA_ENABLE_LIVE_SHARE_SUBMIT` and a probed device |

## Not declared — with the exact unblock requirement

| Surface | Gap | Unblock |
|---|---|---|
| Mediation privileged-path promotion | `privileged-path-audit` FAILs without `MEDIATION_MANIFEST_KEY` (0 violations across 13 routes — audit itself clean) | Provision `MEDIATION_MANIFEST_KEY`; gate re-runs to PASS |
| Conformance vectors | SKIP: fewer than two independently available exact backends | Build `emulator/build/chronus-emu` (C++17 toolchain) + a second `cross_verification` adapter |
| Chronus emulator chain (checks 101–107) | GATED: `C++17 compiler unavailable` | Install g++/clang++ on the host/runner |
| UHD-620 evidence gate | FAIL `identity_negative` on zero-platform hosts — resolver refusal unexercisable | Any OpenCL platform for the negative check; the physical UHD 620 for full evidence |
| Hardware acceptance | `hardware-acceptance.yml` unexercised | Self-hosted `[self-hosted, opencl, <device_id>]` runner + `MLA1517_STRICT_HARDWARE_CI=1` |
| Remote GPU acceptance | GATED | `MLA1517_REMOTE_GPU_TOKEN`/`_ATTESTATION_KEY` + device-bearing agent endpoint |
| Profile assembly | GATED | `HYBA_ASSEMBLY_SIGNING_KEY` ≥32 bytes |
| **Signed production declaration (promotion receipt)** | The `promotion.yml` path cannot complete locally | (1) reviewed `config/promotion-roles.json` with real GitHub identities; (2) `chronus` `GateDefinition` in `al_haras/promotion_gates.py` + manifest target + `promotion.yml` input option **if** the issue intends chronus as a governed subsystem; (3) environment approvals (`promotion-verified`/`pilot`/`production` — SoD-enforced human gates); (4) `PROMOTION_SIGNING_KEY` → `advance_state.py` emits `results/promotion_receipt.json` |
| Live pool submission | NOT_RUN — triple-gated | Pool credentials + `HYBA_ENABLE_LIVE_SHARE_SUBMIT` + live acceptance |
| GitHub Actions | Not exercised for this change beyond this PR's own checks | First push/PR run |

## What "production" can and cannot mean from this host

The software-side ledger is green: every gate that runs without a device, a signing key, a GitHub environment, or a C++ toolchain has been executed and passes (or was honestly fixed to pass — see the ledger's defect list). The remaining rows are not code failures; they are **provisioning gaps** whose boundaries are exactly named above. A `PRODUCTION` declaration in this repository's own model additionally requires the signed promotion receipt, which is human-gated by design — the roles file, environment approvals, and signing key are operator steps no executor may simulate.
