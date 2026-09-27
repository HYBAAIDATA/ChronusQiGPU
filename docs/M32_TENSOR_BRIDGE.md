# M32 Walker → Kellogg Tensor Bridge Specification

## Purpose

Define the precise mapping from the M32 icosahedral quantum walker's geometry
to the Kellogg Tensor's structured search space S = (X, G, M, g, χ, H*).

The bridge allows the Tensor to navigate the M32 search space efficiently
while preserving SHA-256d as the sole accept authority.

**Implementation:** `src/lib/m32_tensor_bridge.ts`
**Consumer:** `src/lib/mining_runtime.ts` → `src/lib/mining_service.ts`

## 1. The M32 Walker (Current State)

The M32 walker is a quantum walk on the icosahedral graph:

| Property | Value |
|----------|-------|
| Vertices | 12 |
| Edges | 30 |
| Faces | 20 (triangular) + 12 (pentagonal, dual dodecahedron) = 32 |
| Graph | Icosahedral (`M32_ADJACENCY` in `quantum_walker_aqo.ts`) |
| Walk types | DTQW, CTQW, AQO, Riemannian |
| Output | Candidate nonces for mining |

## 2. The Kellogg Tensor (Target State)

The Kellogg Tensor operates on a structured search space:

S = (X, G, M, g, χ, H*)

Where:
- **X** — the base set of search states
- **G** — the generator group acting on X
- **M** — the manifold structure over X
- **g** — the metric tensor on M
- **χ** — the truncation rank (bond dimension)
- **H*** — the target subspace

Concrete realization: `StructuredSearchSpace` in `kellogg_operator.ts`.

## 3. The Bridge (Precise Mapping)

### 3.1 Base Set X ← M32 Faces

```
X = {faces of the M32 icosahedral graph}
  = 12 pentagonal faces (dodecahedron dual), indices 0..11
  + 20 triangular faces (icosahedron), indices 12..31
  = 32 total faces
```

Each face is a **search state**. The 32 faces are the **32 search directions**
in the Kellogg Tensor's structured space. Implemented by `m32FaceSet()`.

### 3.2 Generator Group G ← M32 Walk Operators

```
G = {DTQW, CTQW, AQO, Riemannian} operators
  = the quantum walk generators
```

Each operator is a **generator** of the search space. The group action
produces **geodesic moves** between faces. The generators live in
`quantum_walker_aqo.ts` (`DTQWLayer`, `CTQWLayer`, `AQOLayer`,
`RiemannianSimplexLayer`); the bridge consumes their shared adjacency.

### 3.3 Manifold M ← M32 Icosahedral Geometry

```
M = icosahedral manifold encoded by M32_ADJACENCY (32×32)
```

The manifold is the **topological structure** of the M32 graph. Faces are
**anchor points**. Adjacency links are **geodesic segments**. Geodesic
distances `d_M(x, x*)` are computed by exact BFS from the marked face via
`m32GeodesicDistances()`.

### 3.4 Metric g ← M32 Edge Weights

```
g_ii = φ-weighted conformal metric on face i
```

The metric encodes **distance between anchor points**. The φ-weighted
metric is:

```
ds² = 4 Σ φ^{-i} dx_i² / (1 - |x|²)²
```

Face i is placed at radial coordinate `r_i = (i+1)/(N+1)` inside the unit
ball; `g_ii = 4·φ^{-i} / (1 - r_i²)²`. Implemented by
`m32PhiMetricDiagonal()` → `qfiMetricDiagonal`.

### 3.5 Truncation Rank χ ← M32 Walk Depth

```
χ = log_φ(N) where N = search space size
  = ceil(log_φ(32)) = 8
```

The truncation rank **bounds** the search space dimension. Higher χ = more
candidates considered. Implemented by `tensorTruncationRank(N)` →
`bondDimensionChi`.

### 3.6 Target Subspace H* ← Mining Difficulty Target

```
H* = {candidates h : double_sha256(h) < target}
```

The target subspace is **exactly** the set of valid mining candidates. Its
membership is decidable only by SHA-256d; the Tensor's `solutions` set is the
job-derived marked face (`jobSeed mod 32`), a navigation proxy that steers
ordering and never decides acceptance.

## 4. The Discipline Preserved

**SHA-256d remains the sole accept authority.**

- The Tensor may reorder candidates
- The Tensor may prune candidates
- The Tensor may navigate efficiently
- The Tensor may NOT change the acceptance criteria

**Rule (AGENTS.md §4.5):** any Tensor→mining integration may only reorder
or prune the search space while SHA-256d stays the sole accept authority.

Enforced structurally: `m32_tensor_bridge.ts` contains no hashing and no
target comparison — its output is only an ordering of `(faceId, localIndex)`
pairs. Acceptance is decided solely by `MiningService.meetsTarget()`.

## 5. Integration Points

### 5.1 Mining Service

`mining_service.ts` keeps SHA-256d as the accept authority. The Tensor
runs **upstream** of the hash check:

```
Tensor.navigate() → candidate_nonces → SHA-256d check → accept/reject
```

In `executeMiningStep`, the Born-ranked `candidateOrder` passes through
`GlobalMiningRuntime.tensorNavigate(...)` before the `meetsTarget` loop.

### 5.2 Quantum Walker

`quantum_walker_aqo.ts` provides the M32 walk operators. The Tensor
consumes the face structure:

```
M32_ADJACENCY → Tensor.X / Tensor.G / Tensor.M
walker face probabilities → Born-ranked candidate input
```

### 5.3 Kellogg Operator

`kellogg_operator.ts` provides the Tensor's math. The bridge wires
the M32 inputs:

```
buildM32SearchSpace({
  X: m32_faces,          // N = 32
  G: m32_operators,      // M32_ADJACENCY
  M: m32_manifold,       // geodesicDistances
  g: m32_metric,         // qfiMetricDiagonal
  χ: m32_depth,          // bondDimensionChi = 8
  H*: mining_target,     // solutions = [targetFace]
})
```

## 6. O(1) Precompute + O(1) Submit

### Precompute (O(N) build, once per job)

1. Load M32 face structure
2. Build Tensor search space S (`buildM32SearchSpace`)
3. Precompute per-face candidate blocks (`TensorCandidateTable`)
4. Navigate once per cycle (`M32TensorNavigator.navigate`)

### Submit (O(1) per broadcast)

1. Network broadcasts block header
2. `TensorCandidateTable.lookup(faceId)` does an O(1) map fetch of the
   face's candidate block
3. SHA-256d verifies candidate
4. Submit if accepted

## 7. Verification

| Invariant | How Verified |
|-----------|-------------|
| M32 face count = 32 | `verifyBridgeInvariants().faceCountOk`; test "has exactly 32 faces" |
| Tensor X = M32 faces | `verifyBridgeInvariants().tensorXEqualsFaces`; test "tensor X equals the M32 face set" |
| SHA-256d is sole authority | `meetsTarget()` is the only `passes` path; bridge has no hashing |
| Tensor reorders only | Test "produces a pure permutation of the candidate list" |
| O(1) lookup | `TensorCandidateTable` map lookup; test "O(1) lookup" |
| Cassini parity holds | `ExactSequenceMath.cassini(face+1)` per face; `cassiniVerified` in telemetry |

## 8. The One-Line Summary

**The M32 walker is the search space. The Kellogg Tensor is the navigator.
SHA-256d is the judge. The bridge maps M32 faces → Tensor X, M32 operators
→ Tensor G, M32 geometry → Tensor M, M32 weights → Tensor g, M32 depth →
Tensor χ, mining target → Tensor H*. The Tensor navigates without
replacing SHA-256d. O(1) precompute + O(1) submit. The discipline preserved.**
