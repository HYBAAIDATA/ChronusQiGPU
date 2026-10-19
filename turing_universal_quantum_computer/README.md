# Turing Universal Quantum Computer

Consolidated Python package for the **Turing Virtual Quantum Computer (VQC)** —
the exact-math quantum substrate scattered across the PYTHIA / MLA1517
repository. Per the repo thesis (AGENTS.md §1): quantum computation is exact
linear algebra over complex Hilbert spaces; the substrate is incidental. This
package is that substrate, as a single installable unit.

## Release 1.0.0

- **Kellogg is the substrate.** Exact fields, state vectors and the exact MPS
  come from `hyba-kellogg-tensor` (a declared dependency); `exact_tensor`,
  `quantum_tensor` and `exact_field` are aliases of Kellogg's modules, not forks.
- **`mps_exact` backend and representation.** Clifford+T at any width when a
  static Schmidt bound stays within χ_max; the full pipeline (plan, execute,
  certify, THESEUS custody, replay) runs GHZ on 10,000 qubits followed by T and S
  exactly.
- **Surface code corrected.** The planar edge code now encodes one logical qubit
  with exact distance d (the earlier star-on-every-vertex convention encoded
  none).
- **Product boundary.** The hashrate capacity model, the SHA-256d thermodynamic
  boundary and the mining execution plane moved to Mining; copies of TOE,
  Intelligence and Mining modules were removed in favour of their owners. See
  `product_registry.CARVED_OUT`.
- **Release gates.** `python -c "from turing_universal_quantum_computer.product_registry import verify_registry; print(verify_registry())"`
  and `python -m turing_universal_quantum_computer.benchmark [--quick]`.
- **Public release identity.** Distribution `hyba-turing-vqc`
  1.0.0 is the publication target of HYBA Software Limited from
  `QuantumPhiRedux/PhiMiner`. The release workflow builds a staged wheel and
  sdist, verifies the exact artefacts on Python 3.11/3.12/3.13, runs the full
  VQC/certificate/custody/replay/benchmark/formal gates, and only then exposes
  reviewer-gated OIDC publication to TestPyPI or PyPI. Production publication
  is never automatic.

## Package organization and public entry point

TURING remains one distribution, `hyba-turing-vqc`, and one canonical import,
`turing_universal_quantum_computer`. The new `TuringPipeline` facade delegates
to the existing `VQCPipeline`; it is not a replacement engine or a physical-QPU
execution requirement. `QuantumPipeline` remains an alias for compatibility.

- **Software:** the existing inner Python package and its typed contracts,
  native adapter, job lifecycle, estimator, and finite-domain optimizer.
- **Research evidence:** `experiments/` contains executable configurations and
  runners; `results/` documents manifests and generated summaries.
- **Publication:** `paper/` contains a clearly labelled manuscript scaffold,
  bibliography, and generated-table instructions, not invented findings.
- **Validation:** `tests/` checks API behavior, packaging, exact reference
  values, manifest integrity, and reproducible analysis.

Start with [installation](docs/installation.md), the [API](docs/api.md),
[architecture](docs/architecture.md), and [reproducibility](docs/reproducibility.md).
Run `examples/turing_pipeline.py` after installation. The
[layout decision](docs/decisions/0001-preserve-canonical-package.md) explains why
this change preserves the current working distribution rather than mechanically
moving its engine into a new `src/advanced_quantum_pipeline` package.
The facade's present bindings are documented separately from the capabilities
of the full TURING engine. No empty pulse/QEC modules are introduced.

## Install

```bash
pip install ./turing_universal_quantum_computer        # from the repo root
# optional extras
pip install "./turing_universal_quantum_computer[discovery]"   # scipy+networkx
pip install "./turing_universal_quantum_computer[hardware]"    # pyopencl
```

For in-tree use without installing, put the distribution directory on
`sys.path` (i.e. `PYTHIA-main/turing_universal_quantum_computer/`) and
`import turing_universal_quantum_computer`.

## What the VQC is

Quantum is maths, and maths is substrate-agnostic — the qubit count is a
parameter of the algebra, not a hardware ceiling.  The canonical engine is
`TenThousandQubitSystem` (the architecture documented in
`INTELLIGENCE_ONTOLOGY_EUCLID §4`): a universal n-qubit system — default
**n = 10,000** — dispatching to the exact representation each state class
admits:

| Backend | States | Memory | Exactness |
| --- | --- | --- | --- |
| `stabilizer` | Clifford states (`\|+⟩^n`, GHZ, cluster, codes) | O(n²) bits | exact tableau |
| `sparse` (`hilbert.QuantumRegister`) | bounded-support states | O(#nonzero amplitudes) | exact symbolic |
| `closed_form` | hypercube walk, TFIM free-fermion | O(1) formulas | exact symbolic |
| `mps_exact` | Clifford+T with bounded Schmidt rank (GHZ + T, shallow circuits) | O(n·χ²) exact cores in custody | exact over Q(ζ₈) (Kellogg) |
| `symbolic` | dimension/coverage manifests | never densified | exact |

A *dense* 2^10000-amplitude vector cannot exist on any substrate —
including physical quantum hardware, which never materialises it either —
so the package refuses to fake one: operations that would densify fail
closed (`MemoryError`, `StabilizerDomainError`), and every result carries
`truth_class`/`materialized` fields.  No floats-as-amplitudes, no mocks,
no truncation.

Capabilities: superposition, entanglement (with exact entanglement
entropy via stabilizer rank), quantum walks (coined + continuous-time
closed form), annealing (exact TFIM spectrum), tunnelling (Landau-Zener),
swarming (agents sampling exact Born distributions), and entangled
subsystem broadcast via `register_subsystem_entanglement()` under the
non-adjacent-Fibonacci (Zeckendorf) constraint.

**What "exact" does and does not claim.** Every backend above is an exact
*classical simulation* of a restricted, efficiently-simulable quantum
state class (Clifford/stabilizer, closed-form free-fermion, closed-form
walk) — the amplitudes and probabilities it reports are mathematically
exact for that state class. It is not a claim of quantum hardware
performance: none of these backends gain the runtime speedup that real
quantum hardware would provide for a hard search/optimization problem,
because simulating a quantum circuit classically does not confer the
circuit's own complexity-class advantage. Any `quantum_advantage_*` or
`speedup` figure reported by the optional `turing_core.discovery` engine
describes the textbook query complexity of the algorithm under analysis,
not a measured improvement from running this package.

The production mining plane keeps `VIRTUAL_QUANTUM_QUBITS = 11` as its
*default* lane width — a default, not a limit; the executor accepts any
`n_qubits >= 1`.

## Two public surfaces

The package exposes two public surfaces; they answer different questions
and neither stands in for the other.

**`TenThousandQubitSystem` — the algebra surface.**  Exact algebra over
Q(ζ₈): 10,000-qubit stabilizer states, closed-form walks, annealing,
tunnelling, swarms and entanglement registration. Its verdicts are exact
statements about the algebra, not an executed workload.

The hashrate capacity model (`PureQuantumMathASIC`, the deterministic 10 EH/s
certificate, H = M·N·f/I) and the SHA-256d thermodynamic boundary belong to
Mining (`mining.fault_tolerant_asic`, `mining.deterministic_hashrate`,
`mining.thermodynamics_exact`). They consume this package; they are not part of
it.

**`VQCRequest` / `execute_certified` / `run_pipeline` — the run
surface.**  One program through the canonical execution pipeline:
validated, executed on an admitted backend, witnessed (`RunWitness`),
certified (`VQCComputationCertificate`), and optionally placed in
THESEUS custody.  Its artefacts are *evidence of a specific run* — the
replayable record a first workload is judged against.

| Question | Surface |
| --- | --- |
| What can the algebra verify? | `TenThousandQubitSystem` |
| What did this run do, byte for byte? | `VQCRequest` → `PipelineReport` |

Custody contract: `custody=True` alone is in-process scope.  Binding
`custody_dir=<path>` commits to an on-disk THESEUS store — receipts carry
a non-`None` `durable_index` and replay from a fresh process
(`TuringCustody.reopen()`); without it the receipt honestly reports the
shorter guarantee.

## Operator console

`turing-vqc` is the operator surface of the machine. It allocates a register,
applies gates, samples shots, and reports exact measurement distributions,
expectation values and entanglement.

```bash
turing-vqc                    # interactive console
turing-vqc --demo             # run the built-in demonstration
turing-vqc --script x.vqc     # run a console script
```

```
vqc⟩ init 10000
allocated |q10000⟩
  representation  tableau — exact Clifford state in 20000 bits; non-Clifford gates will be refused, not approximated
vqc⟩ h 0
applied h 0  [stabilizer · exact · tableau 20000 bits]
vqc⟩ cx 0 9999
applied cx 0 9999  [stabilizer · exact · tableau 20000 bits]
vqc⟩ prob 0 9999
exact marginal on q0 q9999
  uniform over 2 outcome(s), 1 free bit(s)
  |00⟩  1/2  ██████████████··············
  |11⟩  1/2  ██████████████··············
vqc⟩ measure 128 --seed 3 --readout 0,9999
job  128 shots   backend stabilizer   seed 3
readout  q0 q9999
  |00⟩       69   0.5391  ███████████████·············
  |11⟩       59   0.4609  █████████████··············
  the distribution is exact; the draw is a labelled classical sampling of it.
```

## Product boundary

Three modules make the machine's claims checkable rather than asserted:

- **`backends`** — a registry that decides *which* engine answers a program and
  *what kind of claim* the answer carries (`execution_class`, `truth_class`).
  Admission is decided **before** execution, so an out-of-domain program is
  refused rather than truncated.
- **`capabilities`** — the published capability matrix, plus `audit_claims()`, a
  fail-closed lint over claim text. `capability_report()["claim_boundary_clean"]`
  is asserted in CI, so a wording regression is a test failure rather than a
  quiet overclaim.
- **`certificates`** — verifiable run witnesses. `verify_witness` rejects a
  witness that claims a theorem, consensus authority, or hardware it did not use.

Two state representations, both exact, both first class:

| Representation | Gate set | Width | Amplitude list |
| --- | --- | --- | --- |
| `dense_algebraic` | universal Clifford+T over `Q(√2) + iQ(√2)` | bounded by `max_amplitudes` | yes |
| `tableau` | Clifford | any `n`, including 10,000 | no — and neither does hardware |
| `mps_exact` | Clifford+T | any `n` while a static Schmidt bound stays ≤ χ_max (default 64) at every cut | no; exact marginals, samples, purity and Schmidt rank |

`mps_exact` admits a program only when a static bound — each two-qubit gate
multiplies the Schmidt rank across its cut by at most its operator Schmidt
rank, with a factor 2 for SWAP routing — stays within χ_max. The decision is
made before execution, so a program that could entangle beyond the bound is
refused, never truncated. GHZ on 10,000 qubits followed by T and S runs exactly:
bond dimension 2, ‖ψ‖² = 1, marginal {00: 1/2, 11: 1/2}.

`materialised = False` is **not** a degraded mode. The tableau is the correct
representation for that state class, and it is what makes the wide register
real: gates, shot sampling, marginals, expectation values and entanglement all
work at `n = 10,000`. Reading out more qubits than `READOUT_LIMIT` is refused
because sequential collapse is O(n) per qubit, not because the state is missing.

### Hardware

`QPUBackend` is the only hardware backend and **no provider adapter is
bundled**. It refuses every program, never returns a simulated result in its
place, and `measured_qpu` stays `False`. `assert_measured_qpu()` is the only
sanctioned path to that claim, and it requires a completed provider job record
carrying a provider name, job id, completion timestamp and result digest.

Callers may repeat the register/width and exactness statements above; they must
not state unqualified universal computation at 10,000 qubits, a physical
quantum computer, a hardware speedup, cryptanalytic capability, theorem proofs
or consensus authority. See `docs/TURING_VQC_CALLER_CONTRACT.md` for the full
contract.

## Module map (source → package)

| Original file | Package module |
| --- | --- |
| `turing_core.py` (root) | `turing_core.core` (re-exported by `turing_core`) |
| `chronus/mla1517_platform/python/turing_core.py` | `turing_core.schedule` |
| `legacy/Intelligence/mathematical_discovery.py` | `turing_core.discovery` (optional deps) |
| `mtheory/hilbert.py` | `hilbert` — `QuantumRegister`, `GroverExact`, exact gates/QFT |
| `kellogg/exact_tensor.py` | `exact_tensor` — alias of Kellogg's module (dependency, not a fork) |
| `kellogg/exact_field.py` | `exact_field` — alias of Kellogg's module |
| `kellogg/quantum_tensor.py` | `quantum_tensor` — alias of Kellogg's module |
| `legacy/src/euclid/pythagoras/quantum/quantum_tensor.py` | `register_tensor` — audited `QuantumTensor` |
| `legacy/lucas/pisot.py` | `pisot` — scale contracts, Hendrix schedule, Hilbert coverage |
| `legacy/src/euclid/pythagoras/quantum/hendrix.py` | `hendrix` — `HendrixChronusSearch` |
| `chronus/mla1517/.../mla1517/quantum.py` | `exact_state_vector` |
| `legacy/core_engine/quantum_cuda.py` | `quantum_cuda` — iGPU/Turing simulator facade |
| `Intelligence/grover_exact_scale.py` | `grover_exact_scale` — folded run helper |
| `Intelligence/quantum_algorithms.py` | `quantum_algorithms` |
| `lucas/` (root package) | `lucas/` — exact Lucas limbs + pool kernels |
| repo test suite (mla1517 quantum + turing schedule) | `tests/` |
| — (new, per ontology §4) | `stabilizer` — exact Clifford tableau backend |
| — (new) | `quantum_walk` — coined + closed-form hypercube walks |
| — (new) | `annealing` — exact TFIM free-fermion + Landau-Zener |
| — (new) | `swarm` — exact-distribution agent swarm |
| — (new, ontology §4 `TenThousandQubitSystem`) | `turing_core.ten_thousand` |
| — (new) | `trotter_simulation` — Trotter-Suzuki Hamiltonian evolution (explicit, honestly-approximate; see module docstring) |
| — (new, v1.2) | `backends/` — registry, capability envelopes, admission, fail-closed QPU boundary |
| — (new, v1.2) | `capabilities` — published capability matrix + claim-boundary audit |
| — (new, v1.2) | `certificates` — verifiable run witnesses |
| — (new, v1.2) | `console` — the operator console (`turing-vqc`) |
| — (new, v1.3) | `backends.mps` — `mps_exact`: Clifford+T at any width under a static Schmidt bound (Kellogg exact MPS) |

Modules that belong to other products were carved out: the mining production
plane (`four_layer_stack`, `scaled_execution`), the capacity surface
(`fault_tolerant_asic`, `deterministic_hashrate`, `thermodynamics_exact`) moved
to `mining/`; copies of live modules (`bitcoin_hasher`, `hash_pipeline`,
`search`, `turing_adapter`, `strict_quantum`, `toe_system`,
`hardened_unified_substrate`, `manifold_bridge`, `unified_punch`,
`backend_binding`, `intelligences`, `duality`, `kk_spectrum`, `rings`,
`extended_algebra`) were removed in favour of their owners.

`toe/exact_tensor.py`, `toe/quantum_tensor.py`, `toe/exact_field.py`,
`Intelligence/quantum_tensor.py`, `Intelligence/exact_tensor.py`, and
`Intelligence/strict_quantum.py` are pure alias shims to the kellogg/toe
canonicals — they are consolidated, not duplicated.

## Quick start

```python
import turing_universal_quantum_computer as tqc

# TURING core: exact algebra + self-verification
assert tqc.run_self_verification()

# Canonical 11-qubit register (requires sympy)
reg = tqc.QuantumRegister(11)          # C^2048 sparse exact state vector
reg.uniform_superposition()
dist = reg.distribution()              # exact Born probabilities

# Audited tensor facade + Hilbert coverage plan (requires sympy + numpy)
qt = tqc.QuantumTensor()               # n_qubits = 11 (platform width)
qt.h(0).cnot(0, 1)
plan = tqc.plan_hilbert_coverage(11, data_bytes=112)

# Clifford+T at 10,000 qubits, exact, when entanglement stays bounded
from turing_universal_quantum_computer.backends import Program as P, execute as run
ghz_t = P(10_000).then("h", 0)
for i in range(9_999):
    ghz_t = ghz_t.then("cx", i, i + 1)
res = run(ghz_t.then("t", 0), marginal_of=[0, 9_999])   # selects mps_exact
assert res.payload["marginal"]["probabilities"] == {"00": "1/2", "11": "1/2"}

# The universal engine — 10,000 qubits, exact
sys = tqc.TenThousandQubitSystem()
res = sys.superposition()                     # |+>^10000, exact tableau
ghz = sys.ghz()                               # 10,000-party entanglement
assert ghz["state"].entanglement_entropy({0}) == 1  # 1 e-bit, exact
walk = sys.quantum_walk("hypercube")          # closed-form, zero materialised
gap  = sys.anneal()["critical_gap"]           # 4 sin(pi/20000), symbolic-exact

# Product boundary (v1.2): run through the registry and certify the result
from turing_universal_quantum_computer.backends import Program, execute
from turing_universal_quantum_computer.certificates import issue_witness, verify_witness

program = Program(2).then("h", 0).then("cx", 0, 1)
result = execute(program, shots=1024, seed=7)
assert result.truth_class.value == "exact"
assert verify_witness(issue_witness(program, result))

# Wide register: the same surface at 10,000 qubits, exact and not materialised
wide = Program(10_000).then("h", 0).then("cx", 0, 9_999)
assert execute(wide, prefer="stabilizer", entropy_of=[0]).payload[
    "entanglement_entropy_bits"
] == 1

# Discovery engine (optional: pip install .[discovery])
from turing_universal_quantum_computer.turing_core.discovery import (
    MathematicalDiscoveryEngine,
)
```

## Production execution plane

The mining execution plane that used to live here
(`LucasScaledAethelExecutionAdapter`, the four-layer mining stack and the
sha256d grind) is Mining's: `mining.scaled_execution`. It consumes this
package's exact algebra; SHA-256d consensus remains the sole accept authority.
