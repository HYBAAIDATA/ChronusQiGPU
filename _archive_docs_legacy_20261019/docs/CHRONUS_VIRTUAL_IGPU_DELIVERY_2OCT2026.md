# Chronus Virtual iGPU — delivery report (2 Oct 2026 prompt)

**BLUF:** Software capabilities requested for the portable Virtual iGPU substrate are **implemented and software-validated in PYTHIPhiMiner**. Physical GPU, cloud provisioning, live pool ack, hardware-rooted attestation, and UnifiedEnterprise package ownership remain **visible PENDING gates** — not closed with fabricated evidence.

## Repository identity

| Item | Value |
| --- | --- |
| Workspace | PYTHIPhiMiner-main |
| HEAD (at validation) | `0b2c1552ac64d261ce8ea20aff9d965af060ed82` (working tree elevated Virtual iGPU) |
| Branch | `reconcile-upstream` |
| PR #94 merge | `0ef9f8eafcd131376b564ac3028e830c574779ed` |
| PR #95 merge | `1ba0794fb40e4117601b4b1d5cecb87bf44a2569` (ancestor of HEAD) |
| UnifiedEnterprise | **Not available in this workspace** — cannot verify enterprise inventory/bugs against source |

## What was completed (software)

1. **Canonical ABI `virtual_igpu_v1`** — workloads, policies, delivery modes, trust classes, portable packages, execution receipts, capability manifests (`chronus/virtual_igpu/abi.py`).
2. **Control plane** — attach/probe/negotiate/ready/drain/detach; admission; quotas; idempotency; fail-closed required adapter/device (`runtime.py`).
3. **Standalone software adapter** — real classical execution for fold/unfold (Aethel when present), tensor ops, CGEMV, φ/Lucas/Pisot, SHA256d scan (`adapters.py`).
4. **Unavailable backends** — CUDA, ROCm, oneAPI, Metal, generic OpenCL as typed unavailability (not fake success).
5. **Optional OpenCL Intel path** — probe-only / evidence-gated; no invented UHD PASS.
6. **Memory plane** — content-addressed objects, tenant isolation, residency migration, artifacts, checkpoints (`memory.py`).
7. **Evidence** — durable ledger, content-addressed evidence files, `validate_receipt` with explicit trust model and adversarial rehash warning (`evidence.py`).
8. **Client + sidecar** — embedded (no network), remote fail-closed without local fallback (`client.py`, `wire.py`, `__main__.py`).
9. **Shape safety** — declared output-shape validation before dispatch (ABI + `tensor_compute`).
10. **Miner bridge** — `chronus/mining_bridge.py` routes plans through Virtual iGPU; SHA256d remains oracle.
11. **Acceptance suite** — software gates green; physical/cloud/pool skipped with reasons.

## Test evidence (software)

```text
python -m pytest tests/test_virtual_igpu.py tests/test_chronus_vigpu_acceptance.py -q
# 19 passed, 3 skipped
```

Skipped gates record exact reasons (no GPU SDK / no cloud credentials / no live pool) inside the acceptance module.

## Requirement status map

| # | Requirement theme | Status |
| --- | --- | --- |
| 1 | Source resolve + preserve #94/#95 | **Partial** — PYTHIPhiMiner done; UE unresolved |
| 2 | Canonical runtime + versioned contracts | **Implemented + software-validated** (in-tree; separate installable UE client PENDING) |
| 3 | Workload + virtual memory planes | **Implemented + software-validated** |
| 4 | Control plane + lifecycle | **Implemented + software-validated** |
| 5 | Adapters + cloud as deploy layer | **Software path + typed unavailable physical**; cloud packages external/PENDING live |
| 6 | Policy, isolation, delivery modes | **Implemented + software-validated** |
| 7 | Provenance + trust model | **Runtime-signed + negative hardware-rooted tests**; hardware-rooted mechanism PENDING |
| 8 | Miner + operational intelligence | **Bridge integrated**; full Salamander healing matrix not exhaustively expanded this pass |
| 9 | Acceptance suite | **Software gates pass**; physical/cloud/pool skipped honestly |
| 10 | Deliver packages/PRs/docs | **Docs + matrix updated**; linked multi-repo PRs require UE access |

## Remaining external gate owners

| Gate | Owner | Runnable when available |
| --- | --- | --- |
| UHD 620/630 physical evidence | Device host operator | `python -m bench.chronus_igpu_evidence ...` |
| CUDA/ROCm/oneAPI/Metal kernels | Backend owners | Real SDK + adapter implementation + evidence |
| Azure/GCP live execution | Cloud ops | Deploy manifests + credentials; still names underlying adapter |
| Pool acknowledgement | Mining ops | Live stratum; distinct from local_valid share |
| Hardware-rooted attestation | Security/attestation | Real mechanism only |
| UnifiedEnterprise canonical package | UE repo | Attach repo, pin client version, migrate callers |

## Claim boundaries

- Do **not** declare full production closure across all backends.
- Do **not** treat runtime-signed receipts as hardware proof.
- Do **not** treat Azure endpoint presence as a GPU capability.
- Classical software mode is a **valid product mode** and real computation.

## Primary paths

| Path | Role |
| --- | --- |
| `chronus/virtual_igpu/` | Runtime package |
| `tests/test_virtual_igpu.py` | Unit/contract |
| `tests/test_chronus_vigpu_acceptance.py` | Prompt acceptance gates |
| `docs/CHRONUS_VIRTUAL_IGPU_IMPLEMENTATION_MATRIX.md` | Living matrix |
| `bench/chronus_igpu_evidence.py` | Physical evidence CLI |
