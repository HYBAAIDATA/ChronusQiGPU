# Enterprise Chronus · Theseus · Ovid Custody Substrate

**Governance:** Veritas Integritas · Rule 7 (Strict Honest Measurement)  
**Package:** `aethel.enterprise`  
**Claim scopes:** software-measured only (see Proven below). `production_ready` remains **false**.

## Owner-declared operating model (2026-10-11)

The TRIAD is one system, three planes — as declared by the owner and anchored
to `UNIVERSAL_PRINCIPLE_MAP.md` §20:

- **Pulvini folds** — phi-folding / tensor-train data operators
  (`quantum_compute_substrate/pulvini/`, `aethel.encoding`). The folded
  representation is the working form.
- **Theseus stores the folded form** — durable, attested custody
  (`aethel.enterprise`).
- **Ovid documents where it is stored and how it is searched** — the data-
  organisation layer plus geodesic search
  (`python_backend/core_modules/geodesic_tensor_engine.py`).
- **Chronus executes on it** — the iGPU plane: `standalone_software`
  (independent of any host GPU) or `host_gpu_augmentation` /
  `preferred_accelerator` (climb into and scale a certified host);
  `required_adapter`/`required_device` pin explicit substrates and fail
  closed when absent. Its potential is bounded by the mathematics it
  executes — exponential reach through representation selection — and
  Lucas is the scale law of the machine (`lucas_transform` /
  `pisot_transform` are iGPU workload kinds).

Declaration ≠ measurement: the scopes below record what is *measured*
today; §20 records what the system is *declared to become*.

## Proven (extended software scopes)

| Scope string | What was measured |
|---|---|
| `enterprise_custody_software_single_root` | Single-process primary+replica+journal+HMAC+tenancy (A1–A19) |
| `distributed_consensus_software_multi_node_local` | In-process Raft-like majority commit, 3+ nodes, leader election + failover |
| `multi_root_multi_node_custody_software` | Distinct `EnterpriseCustody` root per cluster node |
| `cross_region_dr_software_simulated_regions` | region_a primary cluster + region_b DR root; snapshot, failover, restore |
| `hyperscaler_soak_software_local_fleet` | Local multi-worker soak (>=4 workers, >=200 ops); not infinite cloud |
| `chronus_hardware_perf_measured` | CPU baseline timings always; Chronus accel path when device present; no invented FLOPS |
| `solutions_api_readiness_software` | In-process Solutions API façade smoke put/get readiness |
| `enterprise_hyba_certification_gate_software` | Evidence-aggregating cert gate; PASS only if all required checks pass |

Evidence modules:

- `tests/test_enterprise_custody_substrate.py`
- `tests/test_enterprise_distributed_substrate.py`
- `tests/test_enterprise_capability_bridge.py`
- `aethel/enterprise/distributed.py`
- `aethel/enterprise/solutions_api.py`

## Still outside this package

Honest externalities **not** claimed here:

- Real multi-region **WAN** latency / packet loss / split-brain across geo facilities
- Third-party **vendor cloud fleets** (AWS/GCP/Azure SKUs, autoscaling groups)
- Physical Chronus **silicon roofline** when no device is present (CPU baseline is always reported; accel path only if device probes true)
- Legal / compliance / regulatory sign-off
- HYBA Intelligence product ABAC, clinical MRI, or whole-system production readiness

## Architecture (software)

```
SolutionsAPI ──► MultiNodeCluster (RaftNode × N)
                      │
                      ├─ node root_0  EnterpriseCustody
                      ├─ node root_1  EnterpriseCustody
                      └─ node root_k  EnterpriseCustody

CrossRegionDR: region_a = cluster, region_b = custody root (simulated region)
HyperscalerSoak: ThreadPool workers → cluster put/get
ChronusPerfProbe: timed put/get; cpu_only flag honest
HybaEnterpriseCertificate: required_evidence → PASS/FAIL
```

## Contracts

See `docs/enterprise_triad/00_*.md` … `07_*.md` for authority, consistency, authenticity, degradation, migration, acceptance, and failure model.

## HMAC policy

Explicit `hmac_key` required (>=16 bytes). `allow_insecure_dev_key=True` only in tests with known test keys. No silent production default.
