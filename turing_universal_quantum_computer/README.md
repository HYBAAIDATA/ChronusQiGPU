# Turing Universal Quantum Computer

Consolidated Python package for the **Turing Virtual Quantum Computer (VQC)** —
the exact-math quantum substrate scattered across the PYTHIA / MLA1517
repository. Per the repo thesis (AGENTS.md §1): quantum computation is exact
linear algebra over complex Hilbert spaces; the substrate is incidental. This
package is that substrate, as a single installable unit.

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

## Module map (source → package)

| Original file | Package module |
| --- | --- |
| `turing_core.py` (root) | `turing_core.core` (re-exported by `turing_core`) |
| `chronus/mla1517_platform/python/turing_core.py` | `turing_core.schedule` |
| `legacy/Intelligence/mathematical_discovery.py` | `turing_core.discovery` (optional deps) |
| `mtheory/hilbert.py` | `hilbert` — `QuantumRegister`, `GroverExact`, exact gates/QFT |
| `mtheory/duality.py` | `duality` |
| `mtheory/kk_spectrum.py` | `kk_spectrum` |
| `kellogg/exact_tensor.py` | `exact_tensor` — canonical Q(√2)+iQ(√2) witness |
| `kellogg/exact_field.py` | `exact_field` |
| `kellogg/quantum_tensor.py` | `quantum_tensor` — first-principles C^N layer |
| `legacy/src/euclid/pythagoras/quantum/quantum_tensor.py` | `register_tensor` — audited `QuantumTensor` |
| `legacy/lucas/pisot.py` | `pisot` — scale contracts, Hendrix schedule, Hilbert coverage |
| `legacy/src/euclid/pythagoras/quantum/hendrix.py` | `hendrix` — `HendrixChronusSearch` |
| `toe/strict_quantum.py` | `strict_quantum` — Q(i) work-window certificates |
| `chronus/mla1517/.../mla1517/quantum.py` | `exact_state_vector` |
| `mining/search.py` | `search` — Grover-exact / Merkle / preimage |
| `chronus/mla1517/.../mining/turing_adapter.py` | `turing_adapter` — `TuringMiningSubstrate` |
| `legacy/core_engine/quantum_cuda.py` | `quantum_cuda` — iGPU/Turing simulator facade |
| `Intelligence/backend_binding.py` | `backend_binding` |
| `toe/hardened_unified_substrate.py` | `hardened_unified_substrate` |
| `Intelligence/unified_punch.py` | `unified_punch` |
| `mining/bitcoin_hasher.py` | `bitcoin_hasher` |
| `mining/hash_pipeline.py` | `hash_pipeline` |
| `toe/manifold_bridge.py` | `manifold_bridge` |
| `toe/intelligences/*` | `intelligences/` |
| `toe/system.py` | `toe_system` — `TOESystem` provenance arbiter |
| `legacy/Intelligence/four_layer_stack.py` | `four_layer_stack` — Aethel→Tensor→TURING→iGPU |
| `legacy/mining/scaled_execution.py` | `scaled_execution` — `LucasScaledAethelExecutionAdapter` (the VQC executor) |
| `chronus/mla1517/.../mla1517/rings.py` | `rings` |
| `chronus/mla1517_platform/python/extended_algebra.py` | `extended_algebra` |
| `Intelligence/grover_exact_scale.py` | `grover_exact_scale` — folded run helper |
| `Intelligence/quantum_algorithms.py` | `quantum_algorithms` |
| `lucas/` (root package) | `lucas/` — exact Lucas limbs + pool kernels |
| `*.cl` kernel sources | `kernels/` (package data) |
| repo test suite (mla1517 quantum + turing schedule) | `tests/` |
| — (new, per ontology §4) | `stabilizer` — exact Clifford tableau backend |
| — (new) | `quantum_walk` — coined + closed-form hypercube walks |
| — (new) | `annealing` — exact TFIM free-fermion + Landau-Zener |
| — (new) | `swarm` — exact-distribution agent swarm |
| — (new, ontology §4 `TenThousandQubitSystem`) | `turing_core.ten_thousand` |
| — (new) | `trotter_simulation` — Trotter-Suzuki Hamiltonian evolution (explicit, honestly-approximate; see module docstring) |

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

# Strict-quantum work-window certificate (Q(i), exact Fractions).
# The 76-byte header prefix must encode a non-null state — all-zero input
# fails closed because a null vector has no Born distribution.
cert = tqc.certify_work_window(bytes(range(76)), nonce_start=0, nonce_count=1024)
assert tqc.verify_certificate(cert)

# Hendrix / Turing nonce schedules
sched = tqc.HendrixStructuredSearch(workers=4).plan(10_000)
assert sched.verify()
order = tqc.TuringMiningSubstrate().exhaustive_order(1024, seed=7)

# The universal engine — 10,000 qubits, exact
sys = tqc.TenThousandQubitSystem()
res = sys.superposition()                     # |+>^10000, exact tableau
ghz = sys.ghz()                               # 10,000-party entanglement
assert ghz["state"].entanglement_entropy({0}) == 1  # 1 e-bit, exact
walk = sys.quantum_walk("hypercube")          # closed-form, zero materialised
gap  = sys.anneal()["critical_gap"]           # 4 sin(pi/20000), symbolic-exact

# Discovery engine (optional: pip install .[discovery])
from turing_universal_quantum_computer.turing_core.discovery import (
    MathematicalDiscoveryEngine,
)
```

## Production execution plane

`scaled_execution.LucasScaledAethelExecutionAdapter` is the fabric's VQC
executor (any `n_qubits`; 11 is the production default, not a bound). It wires strict-quantum certification, the Hendrix
Lucas/Pisot schedule, the tensor fold, and the sha256d grind. SHA-256d
consensus remains the sole accept authority — the quantum layer orders and
certifies the search; it never replaces the target check.
