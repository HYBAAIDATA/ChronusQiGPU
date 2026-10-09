# Resident Hendrix / Chronus ONE iGPU implementation

## Delivered ownership and runtime

PYTHIA owns mining intelligence and issues the sealed SearchPlan. Hendrix is
its default structured algorithm. The executor cannot invoke an advisor or
recompile an unsealed plan. Missing seals, altered semantic fields, wrong
headers/targets and foreign nonce-lease bounds fail closed.

Production call graph:

```
existing pool/proof adapter
  -> PythiaProductionMiningCoordinator._apply_pythia_authority
  -> _bind_plan_execution_intent
  -> resident_search.compile_hendrix_plan
     -> exact Q(phi) dual32 / positive symbolic-radical phi-weighted 11D frames
     -> retained H4 120 vertices / 600 tetrahedra / 600 dual cell-normal positions
     -> exact header-bound vertex itinerary / explicitly selected Turing Hilbert ranking
     -> retained Cassini shard permutations / retained Hendrix coprime stride
     -> versioned, digest-bound ResidentHendrix transport
  -> ProductionExecutionRouter.execute_plan
  -> bounded _run_chunk (one plan, not 600 controller calls)
  -> ChronusOneIGPUHasher.grind_target_hendrix_plan
  -> chronos_one_igpu.OneIGPU.execute_hendrix
     -> cached O(600) position operator, immutable geometry transport
     -> OpenCL resident positional kernel when actually bound; exact CPU parity
     -> actual prepared native SHA256d or an actually bound SHA256d overlay
     -> independent hashlib candidate verification
  -> ExecutionRecord / plan + geometry + resident-execution identities
  -> existing coordinator causal ledger / MiningStorageRecorder custody observer
  -> existing PYTHIA learning and Salamander observation
  -> existing guarded Stratum submission; pool ACK remains external
```

The logical 600 positions are the repository's canonical mining fabric, not a
claim that the geometric 600-cell has 600 geometric vertices or that 600
physical devices executed. Logical scale is never converted into measured H/s.

## Preserved and recovered lineage

- `chronus/h4_600.py`, `h4_group.py`, `h4_coverage.py`, `cell600_bind.py` and
  mining `h4_600_execution.py`: existing source recovered from canonical main,
  not replaced by M32 or by a generic solver. H4 lineage includes the canonical
  staging commit `89a52fb1c277daa068f3fb3e7e52e30e27689f32`.
- `pythia_search.py`: retained 32 -> 11D -> 600 dual-position mapping, exact
  Turing cycle-walk rank, connected degree-four dual adjacency (1200 edges).
- `Intelligence/search_crystal.py`: retained exclusive partitions and Cassini
  local permutations, reused by planning-side compilation.
- `hendrix_order.py` and Turing `pisot.py`: retained coprime positional order.
  The latter's verifier previously enumerated worker positions merely to test
  non-emptiness; it now checks the first position in constant time, with its
  gcd and worker-domain obligations unchanged.
- `pythia_turing_math.py`: corrected the orientation of the dodecahedral family
  to the already-existing Turing `turing_core.core` dual construction. An
  independent triangle-centroid test demonstrates the actual 20-face dual.
  The source package's retained `build_m32()` is checked for point-set parity;
  its historical face order is not silently asserted byte-identical.
- `lucas/fold.py`: existing M15 byte transport and inverse, used without
  approximate floating-point restoration. The sealed manifest binds all
  exact field coordinates and positive symbolic radicals. Binary64 geometry
  is rejected even when outer content seals have been recomputed.
- Original standalone Lucas engine, Golden Quantum module and structured
  solver are byte-preserved. Existing source notes and prior delivery docs
  remain in the standalone package; this increment does not erase their
  outstanding qualification/security work.
- No separate Young-* mining primitive was evidenced in the searched retained
  sources. No Young subsystem, physical QPU or fabricated execution was added.

## Exact new/changed canonical files

```
chronus/exact_geometry.py
chronus/resident_hendrix.py
chronus/one_igpu_mining.py
chronus/mla1517/mining/exact_search.py
chronus/mla1517/mining/pythia_authority.py
chronus/mla1517/mining/resident_search.py
chronus/mla1517/mining/resident_router.py
chronus/mla1517/mining/search_plan.py
chronus/mla1517/mining/geodesic_support.py
chronus/mla1517/mining/coordinator.py
chronus/mla1517/mining/backend_registry.py
chronus/mla1517_platform/python/pythia_turing_math.py
turing_universal_quantum_computer/turing_universal_quantum_computer/pisot.py
tests/test_exact_geometry.py
tests/test_resident_hendrix.py
.github/workflows/resident-hendrix.yml
docs/RESIDENT_HENDRIX_ONE_IGPU.md
```

The complete preserved standalone source is under `packages/chronos-one-igpu`.
Its increment changes the facade, overlay, package metadata/entrypoints and adds
`igpu/resident_hendrix.py`, `igpu/hendrix_execution.py` and
`igpu/kernels/hendrix600.cl`. `source-manifest.json` enumerates exact published
paths and digests; the large source snapshot is not a claim that every file's
mathematics changed.

## Install and select

```
python -m pip install ./turing_universal_quantum_computer '.[ml,dev]'
python -m pip install ./packages/chronos-one-igpu
```

Use the explicit backend policy `one_igpu` through the existing BackendRegistry;
this does not silently change existing automatic hardware policy. Its startup
probe performs actual ordered SHA256d checks. The installed standalone namespace
is `chronos_one_igpu`; the repository's existing `chronos` is not overwritten.
The preserved standalone `src/chronos` source API is retained for lineage and
source regressions but is excluded from the installed distribution.

The adapter can receive an explicitly bound ONE iGPU instance for physical
execution. The CPU-only lane is the independent resident software accelerator,
not a report that a physical GPU ran. Apple/OpenCL bindings are operation-specific;
unavailable operations must not be described as executed hardware.

## Exact-math correction after v3.11

The v3.11 byte-exact binary64 transport did not make its geometry exact.
The strict profile now uses the preserved PhiElement rational Q(phi) core,
symbolic positive radicals, exact distance/incidence equalities, and exact
normalised comparisons. All 632 M32/H4 fold certificates are independently
restored. H4 uses squared edge length 2-phi rather than a tolerance.

PYTHIA.plan_exact supplies the header-bound coarse order. Learned predictions,
advisory face bias and VQC checkpoint output cannot enter the strict resident
compiler. Chronus does not select or improve that order. The actual Turing
Hadamard-coin C600 quantum evolution is independently replayed using exact
complex integer numerators, with unit Born mass checked after every step.
The independent replay must match the actual Turing rank and digest; no sampled
distribution or classical random walk is relabelled quantum.

This correction is a strict **geometry/search execution profile**, not a
certificate for all old APIs. The wider coordinator still inherits operational
policy/admission machinery, and preserved standalone numerical S6/FP64 APIs
remain outside this profile. Their presence prevents a whole-product claim
of no approximation/no heuristics. They are not silently removed or certified.
Hardware execution remains reported per operation; no physical-QPU claim is made.

## Tests and evidence scope

Historical v3.11 canonical focused integration: 32 passed. Actual Bitcoin genesis-header
positive control, target-zero negative controls, exact reference ordering for
windows spanning the 600-partition boundary, bounded full uint32-domain batches,
lease checks, stale-job refusal, immutable plan checks, exact geometry restoration,
real M32 adjacency/dual incidence, default Hendrix, and real router/ONE iGPU
hashing and receipts are covered.

The installed isolated native wheel also runs those 32 tests successfully.
The preserved standalone source suite: 371 passed. Installed doctor: 10 checks
passed, including actual exact-core and SHA256d checks. Native wheel, portable
wheel and sdist are built; wheel metadata validation is recorded.

The local canonical source is a dependency-scoped MCP-retrieved snapshot, not a
full clone. A test bootstrap binds the real retained Turing core exports missing
from that snapshot's package initializer. It does not simulate math, devices or
hashes. This scoped run does not prove full coordinator/Stratum/custody deployment.
The PR workflow installs the actual complete repository and runs focused,
standalone and broad repository tests; its results must be checked separately.

Plans and seal identities are wired into existing `plan_created`,
`execution_started`, `execution_finished` causal events and execution snapshots.
The standalone now also persists the exact issued plan and executed receipt
through the existing MLA-certified PRIME-DB when a database is configured.
Actual genesis execution and independent fresh-process restoration are recorded
in the evidence pack. Local PRIME-DB persistence is not relabelled THESEUS custody.

The unchanged canonical storage recorder already writes every event detail into
content-addressed, THESEUS-custodied receipts when configured. This wiring does
not assert that a full THESEUS/OVID deployment was exercised locally.

Latest exact-profile validation: 45 tests passed against the installed native
v3.11.1 wheel and 45 passed against the installed portable wheel (same tests,
not 90 unique tests); 371 preserved standalone source regressions passed. An actual
Bitcoin genesis SHA256d execution was independently verified, and its new exact
plan/receipt was restored and verified in a separate standalone process.
See `docs/evidence/exact-hendrix/` for current source identities and test evidence.
Historical v3.11 evidence is retained separately and is not rebound to this release.

## Readiness verdict

Implemented and software-validated resident execution increment, with installable
artifacts. Not yet a fully production-qualified deployment of the entire route.
Actual physical-GPU compilation/execution, full repository CI, configured durable
custody/restart integration and literal pool acknowledgement are separate evidence
gates. No ASIC, Apple M5, competitor, 10 EH/s or physical multiplication claim is
made by this delivery. No formal consensus-security theorem is manufactured.
