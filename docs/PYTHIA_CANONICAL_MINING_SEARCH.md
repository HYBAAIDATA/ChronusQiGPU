# PYTHIA Canonical Mining Search

## Authority

PYTHIA is the composition root for mining cognition and the agentic mining
workforce. EUCLID remains the wider enterprise-intelligence orchestrator and a
bounded advisory dependency; Chronus owns physical execution; Salamander owns
bounded healing and measured optimisation; Stratum, SHA-256d, the negotiated
target and the literal pool response remain mining truth.

No search topology, Hilbert-space operation, intelligence decision or device
result can bypass those proof boundaries.

## Canonical production search

The production miner prepares its job-independent search substrate before it
connects to Stratum:

```text
PYTHIA
  -> dodecahedron / icosahedron dual overlay
       12 dodecahedron face directions
       20 icosahedron face directions
       = 32 coarse directions
  -> phi-weighted 11D Poincare/Klein manifold embedding
  -> H4 600-cell construction
       120 primal vertices
       600 tetrahedral cells
  -> dual 120-cell search directions
       600 dual vertices
       degree 4
       1,200 dual edges
  -> Turing exact coined Hilbert walk
       600 positions
       10 position qubits + 1 coin qubit
       exact sparse 11-qubit register, C^2048
       structural reachability horizon = 300 steps
  -> complete 600-vertex traversal rank
  -> 600 nonce shards
  -> Cassini-certified local affine permutations
  -> exact leased nonce itinerary
  -> Chronus explicit-nonce execution
  -> independent SHA-256d / target / freshness verification
  -> serialized mining.submit
  -> literal pool acknowledgement
```

The 600 high-resolution directions are obtained from the existing H4 600-cell:
the normalized centroid direction of each tetrahedral cell is a vertex
direction of the dual 120-cell up to a common radial scale. Those 600
directions are lifted into the same 11D phi-weighted manifold used by the
32-face search crystal.

## Precompute-before-mine contract

`precompute_pythia_search()` runs during
`PythiaProductionMiningCoordinator.__init__` before the inherited production
runtime can establish live pool work.

The startup precompute validates:

- exactly 32 coarse dodecahedron/icosahedron directions;
- exactly 120 H4 primal vertices and 600 tetrahedral cells;
- exactly 600 dual search vertices;
- degree-four dual adjacency and 1,200 dual edges;
- every coarse face owns at least one high-resolution vertex;
- all 600 search vertices fit injectively in the 2,048-state 11-qubit basis;
- Turing's exact 600-position coined walk occupies exactly 11 qubits;
- the exact walk reaches all 600 positions over the structural 300-step
  cycle-diameter horizon;
- the Hilbert traversal rank is a 600-element permutation;
- a stable precompute digest binds the topology and Hilbert traversal.

A precompute failure is a startup failure. The runtime does not silently
construct a weaker search after `mining.notify`.

## Live-job binding

The following facts are deliberately **not** precomputed because they are
external truth available only from live work:

- Stratum session identity;
- job generation and fingerprint;
- header bytes;
- negotiated share target;
- `extranonce2`;
- the exclusive nonce lease;
- current/stale status;
- pool acknowledgement.

When a real job arrives, PYTHIA uses the observed header and its bounded
`preferred_face` decision to choose the first 32-face search basin. It builds a
connected 600-vertex manifold ordering, then applies the precomputed exact
Turing Hilbert-walk rank to that **complete** manifold basis. Position zero is
kept first so the live PYTHIA basin decision remains effective.

No vertex is pruned. No nonce is skipped. The final nonce order is verified to
be a complete, unique permutation of the exact lease.

## Agentic mining workforce

The runtime exposes the workforce roles in evidence rather than treating
"agentic" as a label:

| Role | Owner | Authority |
|---|---|---|
| Mining world model / causal intelligence | PYTHIA | predict, diagnose, rank; never proof |
| Agentic planner / lease owner | `AgenticMiningController` | bounded plan and exclusive nonce lease |
| Search topology | PYTHIA | canonical 32 -> 11D -> 600 search architecture |
| Exact Hilbert traversal | Turing | exact traversal ranking; never Bitcoin proof |
| Physical execution | Chronus | execute the authorised nonce batch on a capability-proven substrate |
| Proof / epoch guard | `StratumProofAdapter` | SHA-256d, target, current work |
| Submission | `IntelligentPoolCoordinator` | one serialized `mining.submit` writer |
| Healing / optimisation | Salamander | bounded repair/reprobe and measured retain/rollback |
| Outcome learning | PYTHIA | learn only from measured execution and literal pool outcomes |

## Accelerator utilisation

The canonical 600-vertex itinerary is not forced into an M32 or contiguous
kernel that would change its order. The execution router uses the existing
`grind_target_batch(header, target, explicit_nonces)` contract when a selected
Chronus lane supports it.

That explicit-batch surface already exists on the relevant software paths for
OpenCL/native/remote/composite execution. A selected hardware route that cannot
consume the exact itinerary must fall back/refuse explicitly; it may not
silently substitute another search order.

`HARDWARE_EXECUTED` remains an evidence class, not a configured state. It is
reachable only after a measured physical launch and completed work. CUDA,
Metal, OpenCL, remote GPU, ASIC and SUPER ASIC remain independently gated by
real capability and deployment evidence.

## Hendrix, M32, geodesic and other discoveries

These are retained and utilised at their justified authority level:

- **M32** is the 32-lane/coarse dual-solid execution compatibility structure;
  it is not the identity of the complete production search.
- **Hendrix** remains an available coprime-stride traversal refinement and
  compatibility/reference path; it is not the canonical production search
  identity.
- **Geodesic ordering** remains bounded, membership-preserving advice to the
  chooser.
- **TOE** may supply bounded causal steering and throttle evidence; it cannot
  establish proof.
- **Lucas** continues to bound scale/window/rung behaviour.
- **Turing VQC policy audit** remains an independent exact cross-check of
  operating-policy choices; a disagreement does not override the authoritative
  production choice.
- **Turing exact coined walk** is now directly used in the canonical startup
  precompute to rank the complete 600-position Hilbert traversal.

This separation prevents a discovery from being either abandoned or promoted
beyond its evidence.

## Claim boundary

The new search architecture currently establishes software-level facts:

- the mathematical structures are present;
- they are composed into the production mining path;
- the search is precomputed before pool work;
- the live job affects the actual execution order;
- the 600-vertex/Hilbert/Cassini itinerary preserves exact nonce coverage;
- capability-proven executors can consume the explicit itinerary;
- every reported candidate remains independently rehashed.

It does **not** by itself establish:

- a higher probability of finding a Bitcoin share;
- a cryptographic weakness in SHA-256;
- a hashrate improvement;
- an accepted live-pool share on the current revision;
- physical CUDA/Metal/OpenCL/ASIC/SUPER-ASIC execution on the current revision;
- a green full-repository CI run.

Those are separate measured-evidence gates.
