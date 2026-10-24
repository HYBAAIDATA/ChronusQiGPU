# PYTHIA

> **CANONICAL DOCUMENTATION (v2 — 2026-10-19):**  
> All legacy narrative and marketing documents have been safely relocated to `_archive_docs_legacy_20261019/`.  
> The fresh, code-verified, falsifiable system documentation is located in [`docs/v2/`](docs/v2/00_INDEX.md).  
> All documentation claims are strictly bound to code reality (`path:line`), measured test runs, and immutable evidence logs.

> **PUBLICATION IDENTITIES:** HYBA uses `hyba-<system>-<capability>`.
> The current catalog contains **11 distinct existing Python distribution
> candidates**, plus **2 planned CHRONUS splits** (13-package roadmap).
> See [the publication catalog](packaging/HYBA_PUBLICATION_CATALOG.md).
> Naming is not release qualification or evidence of registry publication.

> **CANONICAL MINING-SEARCH CONTRACT**
>
> PYTHIA's production mining path is **structured search with complete nonce-estate
> coverage**, with **Hendrix** as the default traversal. The owner-locked governing
> doctrine is `docs/CANONICAL_PYTHIA_SEARCH_DOCTRINE.md`; the machine-readable
> policy is `governance/canonical_mining_search.yaml`. A change that reclassifies
> the production search as blind/flat, demotes Hendrix, prunes authorised coverage,
> transfers PYTHIA's final SearchPlan authority, or weakens SHA256d/target proof
> semantics is not authorised without explicit written repository-owner approval.

> **CANONICAL DOCUMENTATION BASELINE (v2):**
> All architecture, cognitive mechanics, and execution runbooks are canonically documented in [`docs/v2/`](docs/v2/00_INDEX.md).
> - [00_INDEX.md](docs/v2/00_INDEX.md) — Documentation index and legacy archive map
> - [01_SYSTEM_TRUTH.md](docs/v2/01_SYSTEM_TRUTH.md) — System truth and seven canonical authority boundaries
> - [02_EUCLID_IMPLEMENTED.md](docs/v2/02_EUCLID_IMPLEMENTED.md) — Implemented EUCLID cognitive mechanics
> - [03_QUANTUM_TENSOR_STATUS.md](docs/v2/03_QUANTUM_TENSOR_STATUS.md) — Quantum substrate reality and closed claims
> - [04_MILLENNIUM_EVIDENCE.md](docs/v2/04_MILLENNIUM_EVIDENCE.md) — Millennium computational probes (not theorems)
> - [05_RUNBOOKS.md](docs/v2/05_RUNBOOKS.md) — Automated test sweeps and execution runbooks
> - [06_GLOSSARY_BOUNDARIES.md](docs/v2/06_GLOSSARY_BOUNDARIES.md) — Epistemic glossary, truth classes, and measurement contract
> - [07_EVIDENCE_SCOPED_READINESS.md](docs/v2/07_EVIDENCE_SCOPED_READINESS.md) — Readiness layer, system impact, authority boundaries and product distinction
>
> **FALSIFIABILITY & MEASUREMENT CONTRACT:**
> Code, tests, and logged evidence are the sole source of truth. Every performance claim must be MEASURED on executing silicon; unmeasured hardware defaults strictly to `NOT_RUN`. CPU fallbacks are never disguised as device execution (`requested_route`/`executed_route`/`fallback_reason`). Quantum amplitude amplification claims on flat search spaces are closed. Probes of mathematical conjectures are finite numerical computations, not general analytic proofs.

## Evidence-scoped readiness

**Intelligence-led execution. Evidence-scoped readiness.**

The merged readiness engine adds an executable assessment layer beside HYBA's
intelligence, execution, security, custody and recovery capabilities. It evaluates
**31 criteria across five operational areas**—AI infrastructure, cyber security,
resilience, sovereignty and energy/scaling—for a declared offering, environment
and source revision.

Its contribution is not another blanket green status. It separates claimed
capability from locally validated supporting evidence, applies dependency
constraints without awarding extra evidence credit, and generates a phased
engineering roadmap. Nine distinct gates cover regression execution, Docker,
actual GPU work, external pool acceptance, failover, custody, TOE, Salamander
recovery and release artifacts. Accepted risks remain visible without becoming
passing checks.

This strengthens our product distinction: intelligence-led computation is paired
with a concrete model of the conditions needed to operate, govern, recover and
scale it. That is an implemented architectural characteristic—not a claim of
exclusive market novelty, measured performance advantage or production approval.
The assessor is read-only; it does not replace subsystem verifiers, authenticate
signers, actuate repairs or override existing runtime authorities. Upstream
receipt exporters still require integration where absent.

- [System impact and product distinction](docs/v2/07_EVIDENCE_SCOPED_READINESS.md)
- [Technical contract and CLI](docs/readiness/TOMORROW_READINESS_INDEX.md)
- [Implementation](tools/tomorrow_readiness.py) and [assessment tests](tests/test_tomorrow_readiness.py)

## Deterministic hashrate — solving, not searching

Lucas scales every limb. Floating ASIC features (`hyba/hybrid/asic_solver.py`,
`hyba/hybrid/super_asic.py`, the Chronus iGPU ASIC adjacency path) are brought
into the same composition as the resident Hendrix walk and the Lucas-metallic
operators.

- **Solving, not searching.** The accept predicate remains SHA-256d ≤ target.
  The schedule is a deterministic bijection (golden stride or Hendrix coprime
  stride) over the leased window. Every nonce is visited exactly once; there is
  no probabilistic probe.
- **Hashrate is measured, not declared.** `hashrate.ceiling_hs` is an upper
  policy bound, not a floor, throughput guarantee, or performance measurement.
  Binding a device and passing a self-check does not establish a rate.
  Until a device reports
  `silicon_status()["device_run"] == PASS`, the hashrate figure is
  `NOT_RUN`. No module self-declares SUCCESS.
- **Composition.** `SuperAsicHasher` partitions windows by measured throughput
  across bound ASIC, GPU and remote agents. The aggregate is the sum of
  attested device rates; it is never assumed.

See `docs/CANONICAL_PYTHIA_SEARCH_DOCTRINE.md` for the governing search
contract and `hyba/operating_model/lemma.py` for the authorised Lucas and
Zeckendorf scopes.

**PYTHIA is HYBA's operational mining product.** Its singular function is to run the mining system, obtain honest device and pool measurements, sustain HYBA, and support Enterprise's route to market. Enterprise PRIME-DB, storage, treasury, and customer-product implementation are separate products and are not imported into PYTHIA.

## Intelligence-first composition

**EUCLID is the system's canonical intelligence and cognition orchestrator.**
Its production composition root is `EuclidRuntime.production()`; it owns the
cognition loop, representation choice, world modelling, memory, hypothesis
formation, planning, strategy learning, counterfactual plan evaluation,
long-horizon credit assignment, transfer evidence and mathematical discovery.

The canonical EUCLID intelligences are **Predictive, Causal, Counterfactual,
Topological and Geometric**. Quantum capability is an extension consumed
through the TURING / L-HRAS boundaries; it is not a sixth mining authority.

Authority remains separated:

```text
EUCLID      cognition, reasoning, learning, discovery, orchestration
PYTHIA      final mining authority and mining truth
CHRONUS     heterogeneous execution
TURING      virtual/quantum computational capability
SALAMANDER  bounded self-healing and self-optimisation
AL HARAS    security, policy, entitlement and mediation
THESEUS     durable custody / integrity / recovery provenance
```

EUCLID may advise mining operating policy but cannot own or rewrite
`SearchPlan` finalisation, nonce-estate coverage, Hendrix traversal,
Bitcoin-header/nonce semantics, SHA256d, target comparison, share validation,
credentials, submission or pool acknowledgement. The shared contract is
`toe/intelligences/authority_boundary.py`.

Mining is represented to EUCLID as a typed `CognitionProblem`: measured
Stratum/transport state forms the observation, measured share outcomes are the
only reward source, and the admissible operating objective is bounded dispatch
breadth. The PYTHIA production coordinator remains the sole actuator and
clamps the result to its declared bounds.

EUCLID discovery is on the governed production composition path:
`TheoreticalSpaceExplorer` produces evidence-bound candidates and
`salamander.discovery_optimisation.DiscoveryOptimisationBridge` can advance
them only through held-out measurement, independent verification and
Salamander's complete policy lifecycle. Discovery cannot directly mutate
production.

The live truth surface is available at
`GET /api/v1/intelligence/cognition/status` and is also embedded in
`GET /api/v1/intelligence/status`. The frontend renders runtime capabilities
and open evidence gates; it does not invent intelligence scores.

## Runtime boundary

PYTHIA has a Python backend and a React/Vite frontend:

```text
React/Vite operator frontend
        ⇅  HTTP status/control requests
main.py → control_api.py
        ⇅
chronus/mla1517_platform/python
  Python orchestration and exact reference
  C/C++ MMIO, transport, telemetry, persistence
  exact OpenCL payload
  negotiated Stratum coordinator
```

There is no Node/TypeScript backend in the canonical runtime. The frontend is a presentation layer; it does not own mining, proof checking, pool sockets, or hashrate claims.

## Entry points

```bash
# Operator API and built frontend
python3 main.py --host 0.0.0.0 --port 3000 --web-root dist/public

# Hardware miner; requires the actual MMIO device and pool credentials
PYTHONPATH=chronus/mla1517_platform/python \
  python3 chronus/mla1517_platform/python/headless_miner.py \
  --device /dev/uio0 \
  --user <stratum-user.worker> \
  --password x \
  --submit

# Stratum TLS: stratum+ssl:// endpoints, or --tls / MLA1517_STRATUM_TLS=1 on bare host:port
```

The miner fails closed when the device, negotiated job, proof adapter, credentials, or explicit submission approval is absent. `main.py` is the control service; it does not fabricate an active mining result.

The per-operation device policy is explicit rather than global. Device-bound operations — the hardware miner, the strict hardware gate, live submission — fail closed on a missing device or credential. The supervised solver route is different: `PYTHIA_EXECUTION_DEVICE` declares the intended backend (`opencl`, `cpu`, `remote`), and when an OpenCL route is requested but the device or that arm's kernel is unavailable the execution router records `executed_route=cpu_reference` with an explicit `fallback_reason` (`OPENCL_UNAVAILABLE` / `KERNEL_UNAVAILABLE`). A CPU result is always labelled CPU — it is never reported as device execution.

## Canonical structured mining path

The canonical mining package is `chronus/mla1517/mining`:

- `geometry.py` defines the connected 32-lane M32 allocation and complete lane order.
- `lane.py` declares the structured M32 and flat exhaustive work contracts.
- `chooser.py` selects a declared order from observed job/candidate evidence and learns only from real pool responses.
- `solver.py` enumerates the selected lanes without overlap and checks every visited 80-byte header with real double-SHA256.
- `pow.py` owns compact-target decoding, header construction, SHA256d, and target comparison.
- `coordinator.py` composes the chooser with the real MMIO/vault/Stratum coordinator; a label never becomes a share.
- `verification.py` independently verifies observed block records against the supplied header template and target.

The M32/manifold layer is therefore a **structured search and work-allocation mechanism**. It is not treated as a cryptographic shortcut: only the negotiated SHA256d target can accept a share.

## Python intelligence and TOE boundary

TOE is a first-class top-level package (`toe/`), shipped in the distribution alongside `mla1517` and the `kellogg/` tensor substrate it consumes. `toe.bridge` exposes state tomography, trajectory propagation, causal analysis, causal-ladder processing, and algebraic-family detection over the Kellogg tensor. The tensor implementation lives only in `kellogg/`: the former `toe.quantum_tensor`/`toe.exact_tensor`/`toe.exact_field`/`toe.tensor_ml` and `Intelligence/quantum_tensor.py`/`Intelligence/exact_tensor.py` alias modules were retired — importing a retired path fails loudly rather than silently aliasing.

The canonical coordinator invokes TOE through `chronus.mla1517.mining.toe_adapter`: each observed vault record (real Stratum job + real hardware state) is analysed, and the resulting context feeds the `IntelligenceController` control-plane signals. This is advisory context, not a proof mechanism: when TOE is absent or incomplete the coordinator fails closed on that record and continues — and only the negotiated SHA256d target can accept a share.

The declared Lucas ladder is exactly `10, 12, 15, 18, 20, 31, 50, 76`. Device execution is accepted only when its result agrees with the exact reference and the strict hardware gate passes.

## Golden-stride ASIC-mode traversal

`kernels/bitcoin_sha256d.cl` ships `bitcoin_sha256d_gold`, an ASIC-style scan kernel: the device derives each probe nonce in-register as `nonce_i = (seed + i·GOLDEN_STRIDE) mod 2³²` with `GOLDEN_STRIDE = ⌊2³²/φ⌋ = 0x9E3779B9`, reuses the header midstate, reduces the earliest hit with `atomic_min`, and records hit probe-indices in a bounded hit FIFO.

- **Bijection is proved, not benchmarked.** `GOLDEN_STRIDE` is odd, so `gcd(stride, 2³²) = 1` and the walk is a permutation of the full nonce domain — the two-line proof is executed by `verify_golden_stride()` in `hyba/operating_model/lemma.py` and stated in `docs/lemma_golden_ordering.md`. The empirical uniqueness sweep in `tests/test_golden_stride.py` is a cross-check, not the proof.
- **Ordering only.** The φ-resonance ordering (`LEMMA_PHI_RESONANCE`, same doc) authorises `order_device_probe_walk`/`order_host_probe_walk` and nothing else; it is explicitly not a proof of quantum advantage or any Millennium problem. `use_ordering_lemma()` refuses unknown usages and non-φ strides.
- **FIFO depth is derived, not magic.** `GOLD_FIFO_DEPTH = fib(6) = 8` — drawn from the Lucas pool; the kernel `#define` must equal `BitcoinHasher.GOLD_FIFO_DEPTH` (a test asserts it).
- **Silicon gate.** `grind_target_gold()` on a host with an OpenCL device runs a self-check at init (first golden nonce at max target must match the hashlib digest) and reports `silicon_status()["device_run"]` as `PASS`. Without a device it stays `NOT_RUN` — the kernel is a hypothesis until silicon executes it, never `SUCCESS`-self-declared.
- **Calibration.** `scripts/brier_difficulty_sweep.py` drives the wired stack across a difficulty ladder and reports the self-model's Brier score for the quantum-stack emergence signal per difficulty (`reports/brier_difficulty_sweep.json`); it moves, and the movement is reported as measured.
- **Observable audit.** Every emitted observable is a stated measured statistic (see `QuantumStack.OBSERVABLE_DEFINITIONS`); the IIT-derived composite is emitted as `iit_composite`/`iit_composite_state` — named for what it computes.
- The adversarial live-run transcript (`hyba/operating_model/live_run.py`) exercises no-silicon, hard-target, FIFO-overflow, wrong-seed, and non-φ-stride injections; each must survive.

## Measurement contract

- Hashrate is emitted only from executed device work or accepted pool shares.
- A CPU run is never labelled iGPU execution.
- A Cassini seal or manifold invariant is internal correctness evidence, not Bitcoin proof-of-work.
- A pool share requires a live negotiated job, valid credentials, a complete algorithm-specific translation, and the pool's independent acknowledgement.
- Missing hardware, unsupported translation, overflow, stale job, torn state, or failed invariant is a fail-closed result.
- A `cpu_reference` fallback carries its reason; the requested route and the executed route are recorded separately.
- No synthetic pool acceptance, fixed hashrate, or theoretical multiplier is reported.

## Verification

```bash
python3 scripts/re_paper_gate.py
python3 -m pytest tests/ -x -q
python3 -m unittest discover -s chronus/mla1517_platform/python

cd chronus/mla1517_platform
python3 -m unittest discover
MLA1517_STRICT_HARDWARE_CI=1 MLA1517_GPU_BACKEND=opencl make test
```

A missing device must produce an unavailable/failed-closed gate. It must never be converted into a pass.

## Evidence boundary

The repository contains the canonical M32 structured scheduler, SHA256d proof boundary, MMIO-to-vault-to-Stratum path, measured chooser, Python TOE subsystem, and exact OpenCL contract. `docs/STRUCTURED_MINING_AUDIT.md` records which of those components are on the live call graph and which require an end-to-end behavioral test. `docs/PRODUCTION_READINESS_AUDIT.md` is the latest full-repo classification (production / experimental / test-only) with the executed test matrix.

Every named PYTHIA capability is an engineering requirement. If it is not present in the canonical Python path and verified by an executable test, it is an open implementation defect—not a simulated success and not silently reclassified as research.

---

# HYBA → PYTHIA: a natural evolution

PYTHIA is not a departure from HYBA. It is a natural operational evolution of the same research direction: **change the representation, change the topology, preserve the truth boundary**.

HYBA began by asking whether data, memory, search, state and computation had to be represented in the conventional flat forms inherited from existing systems. Folding, exact reconstruction, structured state, manifold ordering, mathematical intelligence and evidence-first operation followed from that question. PYTHIA applies the same discipline to mining: not by changing Bitcoin consensus, and not by declaring a shortcut around SHA256d, but by changing how work is represented, prepared, ordered, allocated, observed and recovered before the canonical proof boundary.

The architectural principle is simple:

```text
STRATUM tells us what work is real.
INTELLIGENCE decides how to prepare and order that work.
EXECUTION performs exactly the authorised work.
SHA256d decides whether a candidate is valid.
THE POOL decides whether a share is accepted.
SALAMANDER keeps the machine alive without becoming proof authority.
```

PYTHIA therefore inherits HYBA's central instinct: **do not wait for the existing shape of a system to dictate the only possible shape of its computation**. Explore the mathematics, test the topology, instrument the execution, and keep every external claim subordinate to measured evidence.

## The HYBA / Taylor-Morris extension to the Church–Turing–Deutsch line

This repository adopts a **project thesis**, not a claim of a newly established theorem.

The historical line begins with the Church–Turing thesis: effectively calculable procedures can be represented by a universal model of computation. Deutsch extended the discussion into physics by asking for a universal computing device capable of simulating the behavior of finitely realizable physical systems under the governing laws of physics.

HYBA proposes a further engineering principle:

> **When a phenomenon admits a finite mathematical representation to a declared precision, and its governing transformations can be expressed as effective operators, the decisive computational question is not the label of the physical substrate but the quality of the representation, factorization, topology and operator structure used to realize the computation.**

We refer to this within the project as the **HYBA / Taylor-Morris Extension**.

In compact form:

```text
CHURCH–TURING
Effective procedure
→ universal computation

DEUTSCH
Finitely realizable physical process
→ universal physical simulation

HYBA / TAYLOR-MORRIS
Mathematically representable state + effective operators
→ substrate-agnostic computational realization
→ representation / topology determine practical tractability
```

The working premise is therefore not merely **"use mathematics to describe the system"**. It is:

> **The mathematical representation is itself part of the computer.**

A poor representation can make a tractable structure appear intractable. A better representation may expose symmetry, factorization, geometry, causal structure, sparsity, invariants or reversible transforms that are invisible in a flat representation. HYBA therefore treats representation choice, topology and operator design as first-class computational variables rather than preprocessing details.

This principle connects the project's major lines of work:

```text
folded memory / data
→ change representation without destroying information

Kellogg / tensor state
→ represent high-dimensional joint state algebraically

virtual quantum execution
→ execute quantum-state transformations as mathematical operators on non-QPU substrates

Poincaré / Klein / Cassini / Lucas geometry
→ change traversal and state-space organization

PYTHIA
→ change how search work is represented, leased, ordered, executed and learned from

AL HARAS
→ change the topology of trust, attack propagation, verification and recovery
```

The project therefore uses the operational chain:

```text
OBSERVE
→ REPRESENT
→ COMPUTE
→ VERIFY
→ ACT
→ ATTEST
→ LEARN
→ RECOVER
```

as a shared HYBA substrate contract. Representation precedes computation because the form in which a state is expressed determines which operators, invariants and decompositions become available to the machine.

### Scope and falsifiability

The HYBA / Taylor-Morris Extension does **not** assert that known undecidable problems become decidable, that complexity lower bounds disappear, or that every mathematical object has a finite effective representation. It also does not make an unmeasured hardware-speedup claim.

Its falsifiable engineering claim is narrower and stronger:

> **For computationally representable systems, substrate should not be treated as the first explanatory boundary. Representation, topology, operator structure, precision and resource scaling must be measured before a limitation is attributed to the substrate itself.**

Every HYBA implementation must therefore move through:

```text
mathematical object
→ executable representation
→ operator
→ invariant
→ falsification
→ measurement
→ evidence
```

If an implementation cannot complete that chain, it remains a hypothesis.

## Mining evolution timeline

The following timeline records the engineering trajectory rather than a claim of cryptographic advantage.

### 1. Conventional proof boundary

The starting point is Bitcoin's existing contract: construct a valid 80-byte header, execute double-SHA256, compare the digest to the negotiated target, and submit through Stratum. That boundary remains unchanged.

### 2. Structured M32 search

PYTHIA introduced deterministic 32-lane structured work allocation, TOE context, Lucas/Cassini geometry and complete-search ordering while retaining exhaustive SHA256d verification. The geometry can change **order and allocation**; it cannot change what constitutes proof.

### 3. Golden-stride traversal

The golden-stride path introduced a full-domain permutation using the odd `0x9E3779B9` stride, preserving coverage while changing probe order. Hardware execution and host reference checks became explicit evidence gates.

### 4. 11-dimensional search geometry

The research surface expanded into 11-dimensional Poincaré/Cassini and Klein/Poincaré representations. These are internal state/search-order geometries. They do not weaken SHA256d, replace the target, or create a separate consensus rule. Where a Klein transform is implemented numerically, it must be labelled as deterministic numerical ordering rather than exact arithmetic.

### 5. Agentic mining

Mining then evolved from reactive chooser logic toward an agentic workflow:

```text
live job
→ immutable job identity
→ precomputed SearchPlans
→ bounded queue / nonce leases
→ execution
→ ExecutionRecord
→ literal pool outcome
→ operational learning
→ next search
```

Intelligence is trained on operational evidence—job churn, stale work, queue starvation, execution latency, recovery and literal pool outcomes—not on invented claims that nearby nonces become cryptographically more likely after a win.

### 6. Salamander governance

Self-healing and self-optimisation are being consolidated into a measured governor loop:

```text
observe
→ classify
→ bounded action
→ actuator acknowledgement
→ post-action observation
→ verified recovery
→ resume
```

The optimiser yields to the healer. Recovery never changes SHA256d validity or pool truth.

### 7. Execution truth and route provenance

The current execution workstream is closing the gap between **requested execution** and **actual execution**. Its intended contract is:

```text
SearchPlan
→ route decision
→ freshness / lease guard
→ exact disjoint chunks
→ actual CPU/OpenCL execution
→ independent host SHA256d recheck
→ evidence-backed ExecutionRecord
```

A reported Cline delivery (`7cc591e`) adds an `ExecutionRouter`, explicit `requested_route` / `executed_route` / `fallback_reason`, execution completion evidence, exact chunk coverage and hardware-backed tests on an Intel UHD 620. At the time of this README update that delivery is treated as **integration evidence pending canonical merge into `main`**; this README does not convert an external workstream report into a merged-repository fact.

Reported workstream verification:

- 34 execution-router tests, including 4 hardware-backed tests;
- 136 platform mining/lease tests;
- 1208 tests in the reported `tests/` run with 0 failures;
- 4/4 kernel mirrors reported byte-identical;
- Intel UHD 620 OpenCL execution reported for the hardware-backed subset.

Still explicitly unverified in that workstream: fleet-scale hardware execution, live pool acknowledgement, full Stratum lifecycle, chain-reorg behavior, and the complete cross-subsystem production voyage.

### 8. The production trajectory

The target is not a collection of impressive modules. It is one continuous, evidence-correlated miner:

```text
BOOT
→ STRATUM CONNECT / SUBSCRIBE / AUTHORIZE
→ LIVE JOB / GENERATION
→ AGENTIC PRECOMPUTE
→ UNIQUE NONCE LEASE
→ EXECUTION ROUTER
→ CPU / OPENCL EXECUTION
→ SHA256d RECHECK
→ SUBMISSION
→ LITERAL POOL OUTCOME
→ LEARNING
→ CONTINUED MINING
→ FAULT
→ SALAMANDER RECOVERY
→ CONTINUED MINING
```

The system is not complete merely because individual modules pass tests. Production closure requires the joins between them to survive job churn, accepted shares, rejected shares, unknown submission outcomes, disconnects, failover, device recovery and process restart.

## Research trajectory: mathematics before labels

PYTHIA contains exact-state work, tensor/state geometry, swarm and agentic workflows, and computational probes over difficult mathematical problems. These surfaces are research inputs and capability probes, not permission to overstate what has been established.

The Millennium-problem probe suite, for example, may execute real finite computations, check identities or expose gaps, while still reporting that no new Millennium theorem has been established. **A partial computational result is not a proof, and an open result is not an impossibility claim.**

The project trajectory is therefore:

```text
mathematical structure
→ executable model
→ falsification
→ measured runtime evidence
→ bounded operational use
→ stronger integration
```

not:

```text
interesting mathematics
→ marketing claim
```

# Bitcoin stewardship doctrine

PYTHIA is not being built to dominate Bitcoin, threaten SHA256, weaken proof-of-work, or undermine network security.

The SHA256d and target boundary is deliberately outside Intelligence authority. PYTHIA may change ordering, scheduling, representation, topology, allocation, recovery and observability. It may not redefine a valid Bitcoin proof.

The posture is one of **quiet guardianship**:

- preserve consensus truth;
- never fabricate pool acceptance;
- never bypass SHA256d;
- make execution and provenance more observable;
- isolate experimental mathematics from proof authority;
- strengthen failure handling and recovery;
- treat evidence boundaries as security boundaries.

We do not need to build a bigger lock around every conventional door. Where architecture permits, reduce or remove unnecessary doors: shrink externally reachable control surfaces, isolate authorities, bind actions to explicit identities, prefer capability-scoped interfaces, fail closed, and make privileged transitions observable.

That is a security design direction, **not a claim that PYTHIA is impossible to hack**. No serious system is declared unhackable without a defined threat model and sustained adversarial evidence. The engineering objective is instead to make compromise materially harder by changing the attack surface and topology while keeping recovery and evidence intact.

## Security trajectory

The desired production posture is:

```text
minimal exposed surface
→ authenticated and authorised entry
→ least privilege / capability-scoped control
→ isolated Stratum, execution, proof and recovery authorities
→ immutable job / plan / execution correlation
→ no secret-dependent security assumptions
→ measured anomaly and recovery loops
→ fail closed on missing evidence
```

The 11-dimensional and other mathematical representations are internal computational structures, not access-control mechanisms. Security must remain grounded in authentication, authorization, isolation, provenance, integrity, least privilege, safe defaults and adversarial testing.

# Evidence classes for future documentation

Project documentation should distinguish at least:

```text
SOURCE VERIFIED
SOFTWARE EXECUTION VERIFIED
HARDWARE EXECUTION VERIFIED
POOL VERIFIED
UNVERIFIED
```

A discovered GPU is not hardware execution. A launched kernel is not a completed window. A submitted share is not an accepted share. An accepted share is not a block confirmation. A mathematical identity is not Bitcoin proof-of-work.

This evidence hierarchy is part of PYTHIA's identity and part of HYBA's natural evolution.