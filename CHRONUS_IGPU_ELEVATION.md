# CHRONUS / iGPU ELEVATION — PSEUDOCODE (End-State Locked)
# Repo: PhiEnterprise1/EuclidPhiEnterprise @ main — package: chronus/
# README truth: "Chronus is software-defined GPU & heterogeneous execution. CPU,iGPU,dGPU,cloud,FPGA/ASIC are places it may execute; none is prerequisite. Not a physical QPU."

## 0. AUTHORITY + INVARIANTS
TRUTH: chronus/README.md + chronus/*.py + kernels/*.cl + evidence/chronus/* > docs
MODES (never conflate):
  A) native_chronus_gpu (standalone_software) — Chronus IS the GPU. Runs with NO host GPU. CPU/reference adapter is substrate, NOT degraded fallback, NOT mislabelled device.
  B) host_gpu_augmentation (preferred_accelerator) — binds certified iGPU/GPU if present, same workload contract.
 Missing GPU gates B only. A is always available. No silicon fabricated by software.
SEEDS=[1337,42,2026]; LABELS: MEASURED vs SIMULATED vs HYPOTHESIS vs NOT_RUN
Route invariant: every exec returns Route{requested, executed, fallback_reason}. CPU never labelled iGPU/device.

## 1. MYTHS TO BUST (agents tested smoke, not this)
C1 "iGPU needs a GPU to exist" — FALSE. Mode A runs on CPU/reference. Prove: `PYTHIA_EXECUTION_DEVICE=cpu` boots, /healthz PASS, workload completes, Route{requested:cpu,executed:cpu_reference}.
C2 "CPU fallback = iGPU execution" — FALSE. Prove: force OPENCL_UNAVAILABLE, assert executed==cpu_reference + fallback_reason set + hashrate==NOT_RUN + no device label.
C3 "Same code can't run Docker-local and Azure" — FALSE. Prove: one digest `pythia:<sha>` boots local `docker run -v state:/state` AND Azure Container Apps; /healthz both PASS; /ready-to-mine unavailable-without-HW in both (correct, not fail).
C4 "Golden stride saves hashes" — FALSE. Prove: kernels/bitcoin_sha256d.cl GOLDEN_STRIDE=0x9E3779B9 odd => gcd(2^32)==1 => permutation (verify_golden_stride()==True). Ordering only. FIFO depth==fib(6)==8==BitcoinHasher.GOLD_FIFO_DEPTH.
C5 "HTTP health == mining readiness" — FALSE. Prove: Azure /healthz PASS while /ready-to-mine==unavailable + workers disabled + no horizontal scale. From deploy/azure/README.md.
C6 "Chronus owns Turing VQC" — FALSE. Prove: Turing workload -> Chronus classical kernel allowed; Chronus never absorbs Turing. Import graph: `import euclid/chronus` must not pull turing VQC ownership; `toe/intelligences/authority_boundary.py` holds.
C7 "Backend-specific code in core" — FALSE. Prove: `import euclid,lucas` pulls zero opencl/mla1517/azure. Backends only in chronus/backends/*, chronus/igpu, virtual_igpu, opencl_host.py, mla1517*.

## 2. ELEVATION PROCEDURE
```python
PROCEDURE ChronusElevate():
  LOG head_hash; BRANCH != main
  # --- static guards (no silicon needed) ---
  ASSERT grep -r "import pyopencl|import mla1517|import azure" euclid/ lucas/ == EMPTY
  ASSERT verify_golden_stride()==True; ASSERT GOLD_FIFO_DEPTH==8
  ASSERT require_lucas_execution_scale(7) FAILS (algebra-only rung); (10,12,15,18,20,31,50,76) PASS
  ASSERT QuantumTensorManifest(n=11).dimension==2048; coverage().fits logic; allocates 0 bytes

  # --- Mode A: native (no GPU) ---
  FOR seed IN SEEDS:
    r = RUN(workload=golden_walk+hendrix_scan+Hilbert_plan, requested=cpu, seed)
    ASSERT r.route.executed==cpu_reference; ASSERT hash==golden_ref_hash
    ASSERT silicon_status()[device_run] != PASS => hashrate==NOT_RUN
    LOG evidence/chronus/modeA_{seed}.json {hash,t_ms,route}

  # --- Mode B: augmented (if OpenCL present, else prove graceful gate) ---
  FOR seed IN SEEDS:
    r = RUN(same workload, requested=opencl, seed)
    IF device_found: ASSERT r.hash==modeA_hash  # same-hash-across-backends
                     LOG t_cpu,t_igpu,speedup ONLY with p95 + N>=10
    ELSE: ASSERT r.route=={requested:opencl,executed:cpu_reference,fallback:OPENCL_UNAVAILABLE}
          ASSERT NOT labelled device; ASSERT hashrate NOT_RUN

  # --- Same-hash + emulation ---
  q = QUANTUM_WALK(Hadamard coin+functorial shift,8 steps,seed 1337,CTCF triad)
  ASSERT hash(q.cpu)==hash(q.emu)==hash(q.igpu_if_present) else mark UNPROVEN, no speedup claim

  # --- Docker local == Azure control ---
  BUILD deploy/azure/Dockerfile :<sha>; RUN local volume mount; ASSERT /healthz PASS
  RUN scripts/docker_smoke.py --image <sha>  # ABI fixtures, never hashes/submits; CI artifact
  DEPLOY Azure (existing main.bicep): ASSERT Entra 401/403 anon, assigned loads UI,
    /ready-to-mine unavailable, workers OFF, no h-scale, audit persists across restart
  WRITE evidence/chronus/backend_matrix.csv {env,requested,executed,fallback,hash,t_p50/p95,device_run}

  # --- HW gate (separate host only) ---
  IF MLA1517_MMIO_DEVICE + driver + Stratum creds present:
    ASSERT grind_target_gold self-check PASS; ASSERT live submit ONLY after conformance+pool accept+reorg PASS
  ELSE: ASSERT control refuses boot without stratumUser/adminApiKey; mining endpoints fail-closed

  ASSERT ALL REQUIRED else ELEVATION=FAIL
```

## 3. END RESULT (PASS looks like this)
```
CHRONUS ELEVATION: PASS
HEAD:61032ce7a44a | SEEDS:[1337,42,2026] | IMAGE:pythia:61032ce7a44a@sha256:d19fe0a7e
MODES: A native PASS (3/3 seeds, hash match) | B augmented PASS-or-GATED (clean fallback, no mislabel)
SAME-HASH: cpu==emu==igpu TRUE (or UNPROVEN, no claim) | TIMINGS: {t_cpu_p95, t_igpu_p95, t_emu_p95}
GOLDEN: verify True, FIFO 8==8, ordering-only locked
DOCKER: local /healthz PASS, smoke PASS | AZURE: /healthz PASS, /ready-to-mine unavailable (correct), Entra enforced, state persists
HW: NOT_RUN (no device here) — no hashrate claimed. Correct.
ARTIFACTS: evidence/chronus/modeA_*.json, backend_matrix.csv, docker-live-smoke log, ledger head, CONVERGENCE_MANIFEST.json
IMPORT GRAPH: core clean (0 backend imports) | BOUNDARY: Turing!=Chronus, PYTHIA owns SearchPlan
FAILURES: NONE | SIMULATED: NONE | MISLABELLED CPU-AS-DEVICE: 0
NEXT: merge fix branch; update docs/v2/03_QUANTUM_TENSOR_STATUS.md + deploy/azure/README hardware gate; close hype issues
```

## 4. FIX RULES
- One image digest local==Azure. No per-env Dockerfiles.
- Missing GPU never fails Mode A. Missing creds/device always fails miner closed (not fallback).
- No `SUCCESS` self-declared. `PASS` only from silicon_status or exact digest match.
- Horizontal scale of file-backed mining session FORBIDDEN.
- Publish matrix + hashes + ledger head. Downgrade wins honestly.

## 5. WORLD STATEMENT (only if PASS)
"Chronus runs anywhere: native mode needs no GPU (measured), augmented mode uses host iGPU when present with same hash (measured), Azure runs control only (measured unavailable mining, correct). No silicon fabricated. Matrix attached."

## 6. Exact GPIU workstreams

The ten-specialist blueprint is tracked directive by directive in
[CHRONUS_GPIU_EXECUTION.md](docs/CHRONUS_GPIU_EXECUTION.md). Its exact execution
paths reuse TURING and Kellogg through the existing Virtual iGPU ABI; completion
of a bounded software path does not complete every elevation gate above.
