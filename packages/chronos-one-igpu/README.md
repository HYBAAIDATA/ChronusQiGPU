# Chronos ONE iGPU — M5-integrated release candidate

**Distribution:** `hyba-chronos-one-igpu` · **Import:** `chronos_one_igpu` ·
**Candidate:** `3.11.2rc3` · **Owner:** HYBA Software Limited · **License:** MIT.

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
