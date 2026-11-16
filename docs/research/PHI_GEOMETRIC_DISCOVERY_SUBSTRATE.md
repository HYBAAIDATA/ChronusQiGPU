# Phi / H₄ Discovery Substrate — Implementation and Acceptance Contract

**Scope:** General geometric search, symbolic representation, tensor/quantum
mathematics, discrete gauge theory, workbench exploration, and measured
cross-domain computation. Bitcoin mining is one consumer, not the owner of
the geometry. Source implementation does not itself confer release status.

## Authority

- **CHRONUS** owns the finite graph geometry, reversible feature coordinates,
  discrete M32 search domains, execution order, finite fiber transport,
  root-system candidates, metric fitting, application adapters, and benchmark
  evidence. Maintained modules: `src/chronus/geodesic/`.
- **TURING** owns exact finite Hilbert states, algebraic operator application,
  interference/reflection, projective or unitary quantum-mathematics semantics
  and supported finite-step evolution. Modules:
  `packages/turing/src/turing/exact/geometry/`.
- **PYTHIA** is internal and may select or learn search plans; this library
  neither grants PYTHIA authority to execute nor offers it as a market product.
- **EUCLID** learns methods/skills and orchestrates research, but does not
  reclassify test evidence. **OVID** owns transformation/equivalence claims,
  **THESEUS** retains evidence/custody, **AL HARAS** authorises actions and
  **Salamander** handles bounded, auditable remediation.

## Concrete mathematical objects

| Object | Source | What is proved in code / checked by tests | Not established |
| --- | --- | --- | --- |
| 600-cell | `chronus.ns_dec` | 120 exact Q(sqrt5) vertices, 720 edges, degree 12, 600 4-cliques | Continuum 11D geometry |
| Dual 120-cell | `geodesic.dual_120cell` | 600 *tetrahedron centroids*, 1200 edges, 720 pentagon cycles, 120 incident dodecahedra; exact rational quadratic coordinates | H4 action explicitly enumerated |
| 11-coordinate mapping | `geodesic.embedding_11d` | Injective polynomial feature map, inverse via first four coordinates, exact affine rank certificate | Isometric embedding, irreducible H4 11D representation, smooth 11D manifold |
| M32 | `geodesic.m32` | Exact 12 dodecahedron-face / 20 icosahedron-face directions; deterministic nearest-direction index | Smooth 32D base, complete edge adjacency |
| Graph spectrum | `geodesic.spectral` | Exact integer Laplacian and sum-of-squares energy identity, optional labelled FLOAT64 diagnostic | Certified exact eigenvalues, continuum Laplace–Beltrami |
| Gauge | `geodesic.gauge` | SU2 Gaussian-rational links, plaquette transport, exact Wilson action and gauge covariance | Continuum Yang–Mills solution, positive QFT mass gap |
| Finite fiber | `geodesic.fiber_bundle` | 32x600 index bijection; checked H4 automorphism transition; actual closed-walk holonomy | Smooth fiber bundle, verified nontrivial smooth topology |
| Finite Hermitian | `geodesic.hermitian` | F257² conjugation and genuinely alternating tensor components | Complex quantum-geometric tensor/Berry curvature |
| Hilbert factors | `turing.exact.geometry.hilbert` | Exact sparse C^32 ⊗ C^600 basis, unit norm, Born weights, exact quarter-turn evolution for H²=I | 19,200 physical states, exact expm of arbitrary H |
| Interference | `turing.exact.geometry.operators` | Exact phase, known-marked reflection, amplitude amplification and involution tunnelling | Unknown-oracle speedup or hardware advantage |
| Discovery | `geodesic.discovery` | Exact SPD metric with bounded rational gradient descent and candidate signatures | Universal manifold learning or full Riemannian-metric flow |
| Root families | `geodesic.root_systems` | Aₙ, Dₙ, 240 E8 roots over rationals | E8 Lie algebra = 248 roots (incorrect); Leech implementation |
| Multi-domain | `geodesic.problems` | SAT, discrete Ising, rational quadratic-loss problems | Lattice QCD, continuous neural network optimization |
| A/B comparisons | `geodesic.benchmarks` | Actual call counts and local timings; same exhaustive objective, exact output parity | MCMC comparison, statistical significance, physical quantum advantage |
| Workbench | `geodesic.workbench` | Functional local Jupyter controls for supplied state inspect/phase injection and Matplotlib plots | Deployed live WebGL/Metal UI |

### Dimensional distinctions

The original 600-cell is a **4D** polytope with **120** primary vertices.
Its dual 120-cell has **600** vertices. A reversible 11-coordinate feature
embedding is not a proof of an 11D irreducible group representation.
The 32-domain M32 arrangement is a spherical search partition, not a 32D
smooth base. The optional 32×600=19,200 basis space exists as an exact
**finite tensor product**, not as an inferred 43-manifold.

### Proof boundary

`formal/ChronusUnivalence.lean` no longer asserts a universally false
unconditional equivalence between harmonic consensus and a Boolean share
predicate. It proves the individual characterizations and explicitly requires
a cross-subsystem equivalence witness. The supplied user's Lean draft still
contained `sorry`; it was not accepted as machine-checked evidence.
Lean compiler execution on the exact PR commit is required for proof admission.

### Exactness boundary

The graph Laplacian and root coordinates are exact. The optional spectral
floating-point diagnostic is explicitly an approximation; it is **not**
used inside the exact quantum semantics. The available exact operator
`exp(-i πkH/2)` is computed for Hermitian involutions `H²=I` and integer
`k`. This is an exact closed-form subfamily, **not** an arbitrary Chebyshev
matrix exponential. General evolution remains a separate mathematical
obligation for TURING.

The legacy `QuantumGeometricTensor.evaluate` uses a symmetric bilinear
form on real-subfield components and necessarily has zero antisymmetric
part. New `evaluate_hermitian` uses quadratic-field Frobenius conjugation;
this corrects the finite-field algebra, but does not prove the continuum
Fubini–Study or Yang–Mills physics claim.

## Reproducible focused validation

At the PR branch head with project dependencies installed:

```sh
python -m pytest -q \
  tests/test_geodesic_phi_foundations.py \
  tests/test_geodesic_cross_domain.py \
  tests/test_mining.py \
  tests/test_mining_readiness.py \
  packages/turing/tests/test_turing_exact_hilbert_geometry.py
```

Additional required admission evidence: full exact-commit CI, package build,
CodeQL, actual Lean 4 compilation, test/benchmark raw artifacts, measured
host/environment data where applicable, CodeRabbit/Qododo review, mandatory
product gates and an explicit release verdict. **Do not merge or designate
production-ready while mandatory checks fail or cannot be inspected.**

## Running a genuine multi-domain comparison

```python
from chronus.geodesic.problems import SATProblem
from chronus.geodesic.benchmarks import benchmark_json

problem = SATProblem(3, ((1, 2), (-1, 3), (-2, -3)))
print(benchmark_json(
    problem,
    repetitions=3,
    input_classification="USER_SUPPLIED_EXAMPLE",
))
```

The report contains observed local nanosecond timings (not manufactured test
numbers), SHA-256 of declared inputs, per-trial oracle calls, exact minimizers,
commit classification and the explicit admission boundaries. Sequential and
H4-BFS exhaustive walks deliberately make the same number of queries.
Improved ordering or timing does **not** demonstrate quantum advantage.

## Installing the optional workbench

The TURING mathematics package is a **separately built internal distribution**.
A base `pip install .` of Chronus does not include it. Install the
repo-local TURING distribution first, then the workbench extra:

```sh
python -m pip install -e packages/turing
python -m pip install -e '.[workbench]'
```

The `workbench` extra declares `hyba-turing==0.2.0.dev0`, IPython,
ipywidgets and Matplotlib. This is a local application inspection surface;
it is not proof of a live iGPU, a public dependency release or a hardware
quantum execution service.

## Compute Abstraction Layer for finite 32×600 states

The implemented `chronus.compute` bridge exposes exact host algebra and
optional physical Metal float32 numerical operations as separate execution
classes. **No unqualified GPU substitution and no dense 19,200×19,200
matrix allocation** is permitted.

```sh
python -m chronus.compute --mode geometry
python -m chronus.compute --mode exact-known-answer
# On Apple Silicon with MLX installed and an available Metal GPU:
python -m chronus.compute --mode metal-known-answer
# For a caller-supplied finite float32 32x600 tensor:
python -m chronus.compute --mode metal-state \
  --state-npy input.npy --output-npy output.npy
```

The Metal path invokes the already maintained `MetalTensorBackend` and
verifies readback against a host calculation with a declared tolerance.
Input/output SHA-256 and measured worker timing are emitted. Reported
device metadata are **not hardware attestation**. No `mx.time()`,
truncated-Taylor-as-exact `expm`, nonunitary amplitude rescaling called
Grover, unmeasured 40–50× acceleration or assumed fixed memory capacity
from the supplied prototype was adopted.

## Using the mathematical workbench

```python
from turing.exact.geometry.hilbert import SparseState, TensorHilbert
from chronus.geodesic.workbench import MathematicalWorkbench

state = SparseState.basis(TensorHilbert((32, 600)), (0, 0))
workbench = MathematicalWorkbench(state)
print(workbench.inspect())
# In Jupyter, with ipywidgets + IPython:
display(workbench.interactive_explore())
```

All interactive phase changes act on the provided exact state. No demonstration
data is presented as runtime telemetry. The optional Matplotlib and widget
dependencies must be installed by the user; they are not imported at package
startup.

## Outstanding acceptance gaps

1. Obtain green CI and complete exact-commit source/test/Lean verification;
   currently unavailable as independent run evidence.
2. Supply the intended nontrivial smooth 11D bundle, connection and
   transition data if the **continuum** claim remains required.
3. Prove exact spectral projectors and general unitary evolution beyond the
   supported involution class, under TURING authority.
4. Characterize structural discovery quality on independent non-mining
   problems and MCMC baselines; use real measurements and confidence intervals.
5. Add actual Leech-lattice construction/verification if the research program
   needs it. E8 root-system generator does not implement the entire E8 Lie group.
6. Integrate authorized dynamic plans into wider Chronus dispatch;
   do not implicitly alter existing mining or production execution.
7. Develop host-bound WebGL/Metal visualization only when its runtime/custody
   and access path can be verified; Jupyter inspection is currently local.

All unverified or unavailable claims are explicitly left **OPEN**.
