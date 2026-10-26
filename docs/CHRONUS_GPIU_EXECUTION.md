# Chronus GPIU execution and closure register

Owner request: complete every expressed and implied directive in the ten-specialist
blueprint. All twenty directives remain in scope. This register describes actual
implementation and the remaining work; the presence of a row does not close it.
`OWNER_DECLARATIONS.md` D6/D7/D9/D10 and the existing execution contracts govern.

## Executable additions

The existing `virtual_igpu_v1` seam now accepts four additional workload kinds.
They use the existing tenant admission, delivery policies, memory custody,
receipts, evidence ledger and result verification. Each is software execution;
required physical adapters are never satisfied by the software adapter.

| Kind | Input | Semantic owner | Independent check |
|---|---|---|---|
| `quantum_program` | TURING Program dictionary; optional exact backend, amplitude budget, shots and seed | TURING | Canonical certified execution replay outside the adapter; compares full result and certificate |
| `exact_graph` | Named Q8 sites, physical indices, graph/tree/PEPS topology, contraction budgets | Kellogg | Canonical contraction/certificate replay outside the adapter; tests compare against a separate full bond enumeration |
| `grid_geometry` | Rectangular integer grid and `op=d4` or `components` | Chronus integer kernels | Separate coordinate maps or component flood fill |
| `modular_geometry` | Rational x/y and determinant-one integer matrix `[a,b,c,d]` | Chronus rational geometry | Complex cross-product identity and upper-half-plane metric factor |

Replay through the same canonical engine protects the transport/adapter boundary;
it is not an independent implementation of the quantum or tensor mathematics.
The quantum, MPS, Clifford and six-phase tests remain separate engine evidence.

```python
from chronus.virtual_igpu.abi import Workload
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
from chronus.virtual_igpu.runtime import RuntimeDaemon, RuntimeConfig
from turing_universal_quantum_computer.backends import Program

runtime = RuntimeDaemon(RuntimeConfig(store_root="/tmp/chronus-gpiu-example"),
                        adapters=[CPUEmulatorAdapter()])
program = Program(2).then("h", 0).then("cx", 0, 1).then("t", 1)
result = runtime.submit(Workload(
    id="bell-phase", tenant="example", kind="quantum_program",
    input={"program": program.to_dict(), "shots": 16, "seed": 42},
    execution_policy="standalone_software"))
assert result.status == "ok"
assert result.receipt["verification"]["verdict"] == "match"
```

### Exact domains and budgets

- Quantum requests admit explicit Clifford+T(+Toffoli) gates only, with strict
  integer qubit/shot/seed domains. TURING's exact Toffoli decomposition is reused.
  No opaque execution options, physical provider selection or float diagnostics
  are accepted. TURING's certificate-bound `exact_payload=True` option omits
  display-only approximations before they are computed; default TURING tables
  retain their existing display fields. Limit: 1,024 qubits, 4,096 input and lowered operations, 4,096
  materialised amplitudes, 4,096 shots; the MPS lane retains its own static rank
  admission. Wider exact domain engines are unchanged by this ABI envelope.
- PEPS/TTN sites use Kellogg `Q8`, field Q(zeta8). Every virtual edge appears
  twice with equal dimensions. Trees must be connected and acyclic; rectangular
  PEPS must have exactly their nearest-neighbour bonds. Fixed-physical-index
  contraction avoids materialising the full statevector. Intermediate sizes and
  scalar product counts are admitted before allocation. No SVD discard occurs.
  The ABI admits at most 64 sites, 65,536 input field values, eight bonds per site,
  65,536 elements in any intermediate and 1,000,000 scalar products. General
  contraction depends on graph width; no universal polynomial PEPS claim follows.
- D4 actions include all eight symmetries, including rectangular grids.
  Components are four-connected and same-colour, including colour zero.
  Grid side limits are 256, cells are integers 0..255. Work is proportional to
  grid size, not an unqualified O(1) per arbitrary trial.
- Upper-half-plane coordinates are integers or `[numerator, denominator]`,
  never decimal text or floats. `y>0`, `ad-bc=1`; rational values are bounded to
  4,096 numerator/denominator bits. The metric factor is `1/|cz+d|²`, computed
  exactly. This is a modular isometry primitive, not a claim that an arbitrary
  search problem has been solved or that SHA256d hit probabilities changed.

## Every directive and its acceptance condition

`Integrated` means the named bounded path is executable. `Partial` means some
required behavior still needs implementation. `Open` identifies the missing
specific implementation, not a change in the owner's scope.

| ID | Directive | Canonical implementation and present disposition | Remaining acceptance condition |
|---|---|---|---|
| 1.1 | Exact Galois/cyclotomic and golden fields | **Partial:** `kellogg/cyclotomic.py`, `exact_field.py`, `scales.py`; `chronus/lucas/pisot.py`, `algebra.py`; exact quantum ABI consumes existing fields | General Z[zeta_m] field admission/composita and a register-wide algebraic-field dispatch contract; do not replace these with another implementation in Lucas |
| 1.2 | Exact Rz/H/Toffoli compilation | **Integrated, bounded:** TURING `hilbert.py`, `software_stack.py`, algebraic backend; exact Toffoli lowering now crosses Chronus ABI | Wire general exact rational-turn symbolic rotations through this ABI; reject phases outside a selected field rather than round |
| 2.1 | Symplectic Clifford with magic injection | **Partial:** TURING stabilizer and exact Clifford+T/MPS lanes; Chronus delegates; 1,024-qubit ABI regression | Explicit magic-state injection/resource tracking and an exact representation-switch certificate; Clifford-only tableau must continue rejecting T |
| 2.2 | Hyperbolic CTQW | **Partial:** canonical TURING quantum walks and `Intelligence/poincare_cassini_search.py`; exact modular isometry primitive added | Admit a hyperbolic graph/Hamiltonian, certify Hermiticity, exact evolution and composition; coined discrete walks and CTQW remain distinct |
| 3.1 | MPS/PEPS/TTN compression | **Integrated, bounded:** existing exact MPS/MPO plus new `kellogg/graph_network.py` PEPS/TTN amplitude contraction and Chronus workload | Full state operations, norms/observables, custody of graph site blocks and scalable topology-specific contraction execution |
| 3.2 | Adaptive bonds with rigorous error bounds | **Partial:** existing exact rank factorization/minimal MPS bonds; graph contractions retain discarded weight zero | Extend rank minimization to graph boundaries and certify resource admission at scale; an area law alone does not certify a rank bound |
| 4.1 | Polyhedral fusion/cache tiling | **Partial:** `chronus/compiler/` existing IR, lowering and intrinsics | Dependence analysis and legality proofs for fused Lucas/stride/Cassini kernels; measured cache/SLM behavior |
| 4.2 | Identical AST across SIMD/OpenCL/SPIR-V/Metal | **Partial:** existing reference/OpenCL intrinsics; portable exact ABI and semantic digests | Implement the named remaining target lowerings, overflow and reduction semantics, and execute same-workload digest conformance per target |
| 5.1 | Poincare-Beltrami/modular geodesic navigation | **Partial:** existing manifold/search modules; exact PSL(2,Z) action and metric certificate oracle added | Integrate certified geodesic/Jacobi trajectories with existing search-plan/coverage contracts; preserve Float64 11-D boundary |
| 5.2 | Cassini basin Hamiltonian/gradient flow | **Partial:** existing Cassini/search operators | Implement declared potential and exact/symbolic singularity-aware flow; gradient descent is dissipative, so do not label it Hamiltonian evolution without its own equations |
| 6.1 | Functorial OVID representation translation | **Partial:** existing folded custody/tensor interoperability; graph cores consume exact values without float conversion | Define actual admitted objects/morphisms and lossless conversion laws; a grid feature map is not generally invertible or equivalent to a stabilizer state |
| 6.2 | Local-to-global fleet consistency | **Partial:** `chronus/fleet/capacity.py`, lease/custody checks and disjoint partitions | Specify overlaps/restrictions/gluing and test conflicting local updates; tenant isolation remains an admission invariant |
| 7.1 | Remote zero-copy RDMA ring | **Open:** existing intra-host unified fabric is not RDMA | Registered-buffer lifetime, transport/verbs binding, remote fencing, replay protection and target-host execution; local queues cannot certify RDMA |
| 7.2 | Continuous HMAC authority and pre-mutation custody | **Existing:** `authority_admission.py`, `native_elevation.py`, `recovery_security.py` | Execute continuous renewal/revocation/cross-tenant mutation scenarios on distributed transport; uncertain commits retain reconciliation latch |
| 8.1 | Cohort Lyapunov control | **Partial:** existing `kellogg/phi_stability.py` diagnostics and Salamander recovery | Define cohort state, control law, disturbance bounds, invariant region and Lyapunov decrease certificate using actual telemetry |
| 8.2 | Autonomous fenced exact recovery | **Partial:** fleet termination/fencing/failover, Salamander, uncertain-commit latch | Connect controller actions through admitted recovery and show lease reissue without duplicate commit; shrinking below exact Schmidt rank must refuse |
| 9.1 | D4 native/vector primitives | **Integrated, bounded:** integer vector kernels and separate coordinate oracle; regression parity with EUCLID primitives | EUCLID world accepts `ChronusARCGeometry` as an explicit executor; chosen trials preserve world results and failed required adapters propagate. Measure device dispatch and end-to-end performance; this is not an ARC score |
| 9.2 | Topological graph morphisms/cellular automata | **Partial:** four-connected component kernel now crosses ABI; existing EUCLID topology | Cellular transition rules, graph morphism contracts and feature integration; report work versus cells/edges and batch width |
| 10.1 | Golden-stride/Fibonacci pipeline and FIFO eight | **Integrated, bounded RTL:** `hyba.vhd`, `chronus/hardware/golden_stride.vhd` and testbenches; `scripts/verify_chronus_rtl.py` | ISA/runtime integration and target FPGA mapping/place/route; GHDL synthesis elaboration and source conformance are not physical-device execution |
| 10.2 | Exact algebraic systolic/Galois datapath | **Partial:** registered exact Z[phi] multiplication with full-width coefficients and GF(256) RTL; exhaustive finite-field testbench | Dot-product/systolic composition, ISA integration, synthesize/place/route and measure timing before claiming a physical one-cycle rate |

## Compatibility decisions

The blueprint asks for dynamic singular-value truncation. D6/D7 require exact
execution. The implementation retains exact rank factorization and rejects a
budget that cannot preserve the admitted state. Existing observational float
operators keep their existing semantics and labels. A universal replacement of
all numeric kernels by an exact field is not claimed.

OVID holds authoritative durable state; THESEUS holds rebuildable projections
per D9. Existing runtime hooks named THESEUS are preserved for compatibility;
renaming a hook does not migrate custody. No independent learner or quantum
engine is introduced; EUCLID retains learning/reward and TURING quantum semantics.

## Verification

Run the new regression slice from the repository root:

```bash
python -m pytest tests/test_chronus_gpiu_exact.py tests/test_kellogg_graph_network.py tests/test_virtual_igpu.py tests/test_arc_euclid_adapter.py tests/test_chronus_fleet.py chronus/fleet -q
```

Run RTL conformance with `python -m scripts.verify_chronus_rtl`.
Run TURING tests with its package as working directory. Full repository gates,
transport/device qualification, FPGA synthesis, cloud deployment and measured
acceleration are separate evidence. Do not mark the complete blueprint delivered
until every remaining acceptance condition above has executed evidence.

The implementation pass verified 136 affected tests, the full TURING suite
(683 tests), three distribution wheel builds and installed-wheel execution,
and GHDL simulation/synthesis elaboration. The control API and built operator
UI returned HTTP 200 in a local smoke check with workers disabled. Repository-wide
checks are not all green: the core suite stops at a missing episodic-memory
artifact, two platform tests disagree with current response contracts, import
graph construction rejects a null-containing source literal, and existing
formatting/deployment findings remain. These failures are recorded separately
from the passing exact execution and RTL checks.
