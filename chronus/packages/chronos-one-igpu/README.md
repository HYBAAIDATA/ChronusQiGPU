# Chronos ONE iGPU — M5-integrated release candidate

**Distribution:** `chronos-one-igpu` · **Import:** `chronos_one_igpu` ·
**Candidate:** `3.11.3rc2` · **Owner:** HYBA Software Limited · **License:** MIT.

**Status: release candidate; not yet authorised for production publication.**
PR #140 has merged, but merging does not close its QC hold. No current-head
whole-product certification, Apple M5 target qualification, registry upload,
or external pool acceptance is asserted by this README. The build verification
below produces package evidence, not a substitute for those gates.

## One product, two execution modes

- **Independent resident iGPU:** runs the existing bounded mathematical
  primitives on the host without requiring a physical GPU. Suitable for
  GPU-less cloud/container deployment; the receipt names the executing backend.
- **Host-GPU augmentation:** binds a real supported executor. Explicit `metal`
  or `opencl` binding fails if unavailable. Logical lanes (80, 800, 8000 or a
  Lucas-derived count) partition work; they do not create physical cores or
  establish a throughput multiplier.

The M5 additions are now included in the standalone distribution and joined to
ONE iGPU through `OneIGPU.m5_resident`. The canonical source remains
`chronus/m5_ultra.py`. A byte-identical packaged copy is checked by
`scripts/sync_m5_model.py`, so installation does not require the monorepo or
shadow its `chronus` namespace.

### What is combined

| Component | Current role |
|---|---|
| Exact Lucas/Fibonacci/Binet/Cassini/Zeckendorf primitives | Existing execution core, preserved |
| M5 multi-pad, uniform/asymmetric elevation, consortium formulation | Packaged canonical model, arithmetic and symbolic descriptors; not hardware evidence |
| ResidentRuntime | Existing bounded, tiled execution and independent result verification |
| M5ResidentRuntime | Binds the complete model digest to real resident work and replay; does not substitute an algorithm |
| MLX/Metal overlay | Optional actual Apple GPU tensor execution; float32, not exact quantum arithmetic |
| CoreML ranker | Optional supplied-model inference; OS-selected compute units, no asserted ANE dispatch |
| Sealed Hendrix mining execution | Existing exact plan-bound route; PYTHIA authority remains unchanged |

Modelled GPU core counts, GHZ/QRAM descriptions, interconnect bandwidth, AI
projections and Hilbert dimensions are never promoted into detected hardware,
executed quantum operations, SHA-256d counts or measured performance. Institution
labels in the model express design inspirations, not partnership or endorsement.
The model descriptor is not a production replacement for any exact algorithm.

## Install and operate

Build and install the candidate wheel from this source revision:

```bash
python -m pip install build twine
python scripts/verify_m5_package.py --variant native
python scripts/verify_m5_package.py --variant portable
python -m pip install dist/m5-native/*.whl
chronos-igpu version
chronos-igpu doctor
chronos-igpu m5-info --virtual-units 8000
```

`doctor` checks installed package diagnostics. It uses the new distribution
name and exact rational structured-operator parity; it does not need reference
approval and does not certify the whole product.

```python
from chronos_one_igpu import OneIGPU, ResidentConfig

with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
    session = gpu.m5_resident(
        ResidentConfig(host_binding="native", virtual_units=8000)
    )
    payload = {"rungs": [1, 2, 10, 18, 31]}
    receipt = session.execute("lucas", payload)
    session.verify(receipt, payload)
```

This example executes Lucas operations, not hashes. The M5 model digest and
actual resident execution receipt stay distinct and are bound together. Receipt
digests provide content identity and replay checks, not an external signature.

On an Apple Silicon host, install the Apple extra and request the actual binding:

```bash
python -m pip install '.[apple]'
chronos-igpu m5-info --bind metal --virtual-units 800
```

Metal availability does not establish M5 device identity, hardware expansion,
physical quantum execution, SHA-256d support, or ANE use. The current MLX overlay
exposes tensor operations, not an exact Hendrix or SHA-256d Metal kernel. An
operation requiring a physical executor fails closed if that operation is not
supported; an M5 descriptor cannot satisfy that requirement.

## Exact M5 quantum operators and backend-neutral execution

`M5ResidentRuntime.execute_quantum("exact_m5_ghz"|"exact_m5_cluster")`
now executes the existing pad-state definitions using exact H/CX/CZ gate algebra,
not numeric eigensolvers or canned state outputs. A separate closed-form verifier
checks each amplitude, Born probability and exact normalisation. Receipts bind
algorithm, model, topology, implementation source digest, actual gate applications
and substrate. Fresh-process replay rejects identity or amplitude substitutions.

The explicit domain is **one logical qubit per pad, at most 10 pads**. It is not
the entire modelled register (64 bits per subunit), physical inter-pad entanglement,
a QPU dispatch, or proof of mining success. These are exact mathematical quantum
operators executed on the host. Physical execution requests fail closed while no
qualified exact gate executor exists. Nothing is counted as SHA-256d work.

```bash
chronos-igpu m5-quantum --state ghz --pads 4
chronos-igpu m5-quantum --state cluster --pads 10 --topology mesh
```

`OneIGPU.bind_execution_adapter(adapter)` admits actual backend-neutral Lucas
and SHA-256d batch methods. Every output is independently checked; undeclared
operations, changed adapter identity, duplicate nonces, invalid domains and
corrupt outputs are rejected. This permits integrations without making CUDA,
Metal, OpenCL, Apple M3/M5 or a specific vendor the product's identity.

A third-party adapter declaration is **not hardware certification**. Its declared
physical status is retained separately, but it cannot self-certify physical
execution or fabricate a silicon core count. Existing discovered Metal/OpenCL
bindings remain separate. Resident physical-operation requests now check the
actual bound physical capability as well as the operation route. A claim of
80→800→8000 physical GPU cores or corresponding performance still needs actual
hardware evidence; the logical scheduling contract remains executable without it.

## Generic M5-derived feature runtime (RC3)

This runtime is no longer tied to an Apple model. `FeatureProfile` supplies
immutable logical register sizes and graph edges; M5 is an optional origin.
`OneIGPU.feature_runtime(profile)` and `gpu.m5_resident().features()` expose the
same executable implementation. The `exact_features` ABI and installed
`feature-info`/`feature-run` CLI carry that contract without vendor dependencies.

Implemented and integrated:

- **Full declared Clifford registers:** the base M5 profile has 512 logical
  qubits. Exact bit-packed H/S/CX/CZ/SWAP algebra prepares GHZ/cluster states,
  verifies commuting independent stabilizers and answers exact joint Born
  queries without allocating 2^512 amplitudes. This is an exact encoding for
  Clifford states, not an approximation or an arbitrary-state compression claim.
- **Prepared neural and tensor kernels:** dense, bias, identity/ReLU, matmul,
  add and Hadamard operations over the preserved Q(phi) field. Exact zero
  coefficients are eliminated; rational-subfield operations use exact rational
  arithmetic. Independent dense verification remains. No trained model or ANE
  dispatch is fabricated, and these operations are not labelled quantum gates.
- **Neural Hamiltonians and operator contracts:** supplied Hamiltonian sums
  execute as one exact exponential, not a Trotter approximation. Projector
  commutation, projector annihilation and general operator commutation are
  distinct checked contracts. Invalid conditions fail; they are not repaired
  by changing the request.
- **Unified memory:** actual bounded OS shared-memory blocks, content identity,
  read-only leases, pinned-block protection and deterministic eviction.
- **Logical inter-pad transport:** real worker queues carry shared-memory
  descriptors, verify payloads at each authorised hop, bound in-flight work,
  coalesce exact retries and reject conflicting workload identities. Zero-copy
  here refers to CPU shared segments, not qualified GPU or physical die links.
- **Dynamic preparation cache and custody:** bounded content-addressed immutable
  programs/weights; fresh inputs/results; exact receipts, PRIME-DB checkpoint
  and fresh-process replay. Existing custody is retained and made thread-safe.

```python
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.igpu.feature_profile import FeatureProfile

profile = FeatureProfile((64, 64), ((0, 1),))  # no vendor identity needed
with OneIGPU(db_path="features.db") as gpu:
    with gpu.feature_runtime(profile) as runtime:
        receipt = runtime.execute({
            "kind": "stabilizer", "algorithm": "exact_stabilizer_ghz",
            "layout": "full_register", "assignments": [[0, 0], [127, 0]]
        })
        assert runtime.verify(receipt)
        object_id = runtime.checkpoint(receipt)
```

Feature coverage is recorded in `docs/M5-GENERIC-FEATURE-COVERAGE.json`.
Original M5 rates, core counts and physical strategies remain separate model/
hardware requirements. A software counterpart is not proof of Apple-equivalent
silicon, physical entanglement, optical/RDMA performance or competitor supremacy.
No mathematical work is counted as SHA-256d. Sealed Hendrix mining semantics are
unchanged. Existing statevector APIs are retained alongside the new exact
Clifford representation; non-Clifford requests are not silently substituted.

`benchmark_generic_features.py` measures prepared vs independent dense kernels
on equal exact transforms of public Bitcoin genesis bytes and Fibonacci diagonal
weights. It reports the full-runtime observations separately. Any ratio is a
CPU kernel-control measurement—not M5 hardware, trained AI, mining, whole-product
or competitor performance. Native/portable package validation preserves the raw
samples and artifact/source digests. No historical ratios are compounded.

## M5_ULTRA bounded contract continuation (3.11.3rc2)

This is a separate, deeper contract over the original bounded pad-state API.
It does not expand its span or remove the broader RC3 feature runtime. The
bounded contract has **one logical qubit per pad, `PAD_MAX=10`**, with no physical
entanglement claim. New operator chains have `DEPTH_MAX=55`, derived from the
prior maximum ten-pad full-mesh preparation (10 H + 45 CZ). The prior API had
no separately named D_max; this is an explicit admission ceiling, not a claim
that a pre-existing declared constant was unchanged.

- H/X/Z/S/S†/T/T†/CX/CZ/SWAP, GHZ and topology-linked cluster preparation,
  composition, inverse and adjoint within the sealed pad/depth domain.
- Four reduced rational coefficients encode each amplitude in Q(sqrt(2),i).
  Canonical JSON byte equality defines parity **in the contract**, not tolerance
  in tests. The production field kernel and independent symbolic basis-column
  implementation must agree; disagreement fails, with no chosen winner.
- Exact normalisation after every gate, independently recomputed Born values,
  local symbolic unitarity and exhaustive finite-basis adjoint proofs (bounded
  to three pads for the exhaustive audit). Tensor embedding and gatewise
  unitarity apply to larger admitted chains; no claim of an executed 10-pad
  exhaustive matrix proof or Lean certification is made.
- Receipts bind revision, algorithm, implementation, topology, pad permutation,
  operator chain, device contract, result and exact work counts. Host
  differential-verifier counts are separate from source-level device integer
  helper-call/write/dispatch counts; neither is an ISA-cycle or rate claim. Receipts contain
  no timing/rate/speedup/hardware figures. Raw coefficient buffer shapes and
  canonical byte counts are stated; they are not a whole-process RAM model.
- CPU_REFERENCE and IGPU here are two **host-CPU exact software paths**, not
  evidence of two physical devices. The new OpenCL integer executor consumes
  immutable chains using resident device buffers and cached plan tables. Its
  exact GPU domain is dyadic Q(sqrt(2),i), common denominator exponent <=60;
  unsupported rational inputs are never approximated. A GPU request fails if
  its device/domain is unavailable unless CPU_REFERENCE fallback is explicitly
  authorised. Such a fallback never satisfies GPU parity.
- PRIME-DB restart/replay and caller-owned Ed25519 signed custody are exposed.
  Hashes alone are content identity, not authentication; replay pins a device
  contract and signed custody additionally pins the trusted public-key digest.
  No production signing key is bundled or invented.

```python
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.igpu.m5_ultra_contract import preparation, device_contract

# rc_sha must be the externally sealed source revision, not a guessed value.
with OneIGPU(db_path="ultra.db") as gpu:
    bounded = gpu.m5_resident().ultra_contract(rc_sha)
    chain = preparation(bounded.model, "exact_m5_ghz")
    receipt = bounded.execute(chain.then(chain.adjoint()))
    assert bounded.replay(receipt, device_contract("IGPU"))
    object_id = bounded.checkpoint(receipt)
```

Installed command: `chronos-igpu m5-ultra-run CHAIN.json --rc-sha REVISION`.
An exact-normalised input may be supplied; zero/non-unit norm, floating input,
invalid pad identity, over-depth and unrecognised gates fail admission.

Contract validation deliberately runs **without new benchmarks**:

```bash
python scripts/verify_m5_package.py --variant portable --skip-benchmark --contract-rc-sha REVISION
python scripts/verify_m5_package.py --variant native --skip-benchmark --contract-rc-sha REVISION
```

`audit_m5_ultra_contract.py` records differential, symbolic, determinism,
mutation and fallback evidence, including unavailable GPU parity rather than a
false pass. `verify_internal_m5_ultra.py` downloads hash-pinned wheel artifacts
from a supplied HTTPS internal origin and installs fully offline in a clean
venv. It neither publishes nor contacts PyPI/TestPyPI; all dependency wheels
must be in the authorised internal manifest. Existing generic verification may
still run its historical benchmark outside this contract, but this increment
and its workflow skip it. Registry policy is **INTERNAL_INDEX only**.

The continuation branch is based on post-PR151-merge main `8dd57e49` and recovers
the bounded commits that had been pushed to the old branch after its merge.
Required gates remain fail-closed. Without an actual internal-index endpoint,
trusted production signing key, actual exact GPU parity and complete-checkout CI
results, the record must not return
`ELEVATION_COMPLETE`. The implementation is **INCREMENTAL_EVIDENCE_ONLY**;
whole-product composition, full-register semantics, iGPU-qualified VQC beyond
these bounded operators and any public-publication decision remain unresolved.

### Executable closure machinery

- `ExactOpenCLExecutor` compiles the actual integer kernel; there are no float
  coefficients, approximate reductions or fast-math options. Device detection,
  allocation, cached buffers, cached immutable plans and kernel dispatch are
  real PyOpenCL calls, not a supplied mock adapter. All outputs are independently
  checked against host field arithmetic and symbolic Born probabilities. Missing
  hardware/compiler capability is UNAVAILABLE. CPU compilation/execution of the
  kernel body tests integer logic only; it is not OpenCL driver qualification.
- `replay_m5_ultra_evidence.py` checks a pinned source-report hash, exact model
  identity and revision, then independently replays without hardware redispatch.
  It can additionally require caller-owned signed custody. A cross-runner CI job
  consumes the producer's actual installed-artifact evidence. Runner fingerprint
  differences are recorded, not promoted into proof of physical machine identity.
- `m5_release_gates.evaluate_contract_gates` keeps unavailable GPU cases, skips,
  zero executed CI steps, missing trusted signatures, public indexes, survivors
  and wrong-revision evidence from closing required gates. Its inputs must first
  be acquired/authenticated through the evidence tools: JSON flags alone are not
  authentication. It can only qualify the bounded contract; it never authorises
  whole-product certification, public publication or physical quantum claims.
- The internal-install tool downloads only same-origin, hash-pinned wheel files,
  enforces a total download quota, installs with `--no-index --no-deps`, checks
  installed dependencies offline, and runs the installed bounded entry point.
  This does not supply a missing registry endpoint, signing key or upload consent.

The previously unimplemented public `OpenCLAdapter.compile/dispatch` now has
an explicit exact hybrid implementation: actual OpenCL Lucas execution plus
the complete exact host six-stage datapath and independent value checks. The
existing interface is preserved; five host stages are never labelled GPU stages.
All-device placement requests still fail closed. Rate fields may be `None` for
executed-but-performance-unqualified receipts; existing CPU rate behaviour is
unchanged. This replacement does not claim a six-stage physical GPU pipeline.

Public M32 exact transport now preserves the historical 20-face +12-dual
ordering through Q(phi) collinearity/orientation, not cosine argmax/tolerances.
Its same 7/10 adjacency contract is evaluated with exact radical scores, and
immutable geometry is cached by content. Legacy float display interfaces remain
projections, with exact uniform-state access added. Prime-ROM sieve bounds now
use integer isqrt; caller/output contracts remain intact.

The current environment has no qualified exact OpenCL GPU, so GPU execution
evidence remains UNAVAILABLE. No new throughput or speedup measurement is run.
The progress ledger is `docs/M5-ELEVATION-FEEDBACK-LEDGER.json`; unresolved feedback
is recorded as open, never inferred closed from scoped installed tests.

## Mining ownership and reference boundaries

PYTHIA selects and seals Hendrix SearchPlans. Chronos executes the supplied
plan through M32 → certified 11D → H4/600 → bounded nonce evaluation → actual
SHA-256d → independent verification → receipt. M5 integration does not change
plan order, lease ownership, target checks, custody or submission authority.
Pool acknowledgement remains a separate external boundary.

Legacy numerical/interval solver APIs, advisory search and floating projections
remain retained behind the explicit reference-approval contract where guarded.
They cannot satisfy an exact production request. For example, `structured_ground`
is not an exact-production ground-state API, and old GoldenRuntime `mine`/`search`
examples must not be used as the canonical Hendrix entry point. Preservation of
these APIs is not whole-product certification.

## Release gates and evidence

`verify_m5_package.py` checks source parity, builds wheel + sdist, runs Twine,
checks namespace/metadata/source identity, installs the wheel in a fresh process
outside the checkout, executes M5 model/resident/CLI tests, rebuilds the sdist,
and reruns installed tests. It records commands, exit codes, source revision,
working-tree state, artifact SHA-256 and JUnit digests. It never uploads.

Package checks must not be reported as the full repository suite. Before
production promotion, close the outstanding whole-product/import/platform
contract findings and run complete current-head evidence. Canonical Chronus
readiness (`chronus/readiness.py`) separates six native-software evidence gates
from optional device-specific certifications; absent physical GPU hardware alone
does not invalidate native software readiness.

The adjacent `packaging/chronos-core` distribution is the **v3.3 mathematical
plane**, not this resident product: its deliberate wheel boundary excludes M5,
virtual iGPU and delivery modules. Installing it is not a substitute for installing
ONE iGPU. Do not combine distributions by copying over each other's namespaces.

Previous measurements remain scoped to their original environments and versions.
No new speedup is claimed here. Scripted local pools prove local protocol exercise,
not external accepted shares. Registry status remains **NOT PUBLISHED**.

Historical documentation is preserved in
`docs/HISTORY-README-through-v3.11.1.md`; it is not the current release contract.
