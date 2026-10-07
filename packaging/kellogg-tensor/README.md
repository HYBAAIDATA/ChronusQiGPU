# kellogg-tensor

Kellogg is an exact tensor-network library. States, operators and
channels are held in exact number fields, so a norm that should be 1 is 1,
a probability that should be ½ is ½, and a gate that should be unitary is
checked by equality, not by a tolerance.

```
pip install kellogg-tensor        # import name: kellogg; only hard dependency: numpy
```

## What you get

| Area | Module | What it does |
|---|---|---|
| Exact tensor networks | `kellogg.exact_network` | Tensor trains, MPS and MPO over Q(ζ₈) = Q(i, √2). Every Clifford+T gate is exact. Every two-site split is an exact rank factorization, so bond dimensions always equal the exact Schmidt rank. |
| Custody | `kellogg.custody` | Each tensor core lives in a custody store as an immutable, content-addressed block. Identical cores share one block. The working set is a bounded window. |
| Certificates | `kellogg.certificate` | Every exact operation emits a content-addressed certificate that binds the field, input and output state roots, parameters, invariants and custody bytes moved. Certificates compose, aggregate under a Merkle root, and replay. |
| Channels, Hamiltonians, Fisher information | `kellogg.channels` | Exact Kraus maps (trace preservation by equality, Stinespring isometry, Choi rank). Pauli-sum Hamiltonians and MPOs. Exact rotations on the π/4 grid. Exact quantum Fisher information, Cramér–Rao and Heisenberg checks. |
| Surface code | `kellogg.surface_code` | Planar code over GF(2) with exact algebra and exact distance. Exact minimum-weight and union-find decoders. |
| Golden substrate | `kellogg.substrate`, `kellogg.scales` | Z[φ] and Q(φ). Lucas = trace(Rⁿ), the Cassini identities, the golden cat map, the φ-β-expansion, Fibonacci-lattice star discrepancy. |
| 11D vector | `kellogg.vector11` | φ-weighted 11D lift and Klein fold. Exact round trip in Q(φ). |
| Float plane | `kellogg.tensor_network`, `kellogg.dmrg` | TT-SVD with a guaranteed error bound ‖T − TT‖_F ≤ ε‖T‖_F, and two-site DMRG checked against dense diagonalization. |
| Specification | `kellogg.spec` | The canonical tensor specification as a machine-checked registry. |
| Benchmarks | `kellogg.benchmark` | Correctness, cost and meta benchmarks. Every result is a content-addressed artifact with provenance. |

## Quick start

```python
from kellogg.exact_network import ghz_circuit
from kellogg.cyclotomic import Q8

psi = ghz_circuit(10_000)                    # H, then a 9,999-gate CNOT chain, exactly
assert psi.norm2() == Q8(1)                  # <psi|psi> = 1, exactly
assert psi.probability(5_000, 0) == Q8(1, 0, 0, 0, 2)   # 1/2, exactly
assert max(psi.bonds()) == 2                 # Schmidt rank 2 at every cut
print(psi.unique_blocks())                   # 10,000 sites held in 3 custody blocks
assert psi.ledger.verify_chain()             # every operation's certificate re-verifies
bits = psi.sample(seed=7)                    # seeded sampling against exact marginals
```

Run the benchmark suite, quick or full:

```
kellogg-benchmark --quick
kellogg-benchmark --out results/
```

## Exact and float planes

Every structure declares its field. The exact path covers Z, Q, Q(i),
Q(√2), Q(ζ₈), Z[φ], Q(φ) and GF(2), and has no floating point. The float64
plane covers SVD truncation, eigen-solves, DMRG and entropies. Results that
cross from exact to float are marked as a boundary crossing and are never
promoted back.

Some things cannot be exact, and Kellogg refuses them rather than
approximating:

- **Rotations off the π/4 grid.** `exp(−iθP)` is exact only when θ is a
  multiple of π/4. Other angles raise `NotInF4`.
- **SVD truncation.** Singular values are square roots outside these
  fields. Exact compression is lossless rank factorization; ε-compression
  is `tensor_network.tt_svd`.
- **Von Neumann entropy.** It is transcendental in general. Kellogg reports
  the exact purity Tr ρ_A² and the exact Schmidt rank; entropy is a float
  value.

## Custody

The engine owns no private storage. `default_custody()` binds to an Aethel
fold store when one is installed and otherwise uses Kellogg's built-in
resident custody. The choice is recorded in every accounting report.
Releasing a block keeps its identity (digest and size) and drops its bytes.
Reading a released block fails until it is regenerated, and regeneration is
proven by digest equality. To bring your own custody, implement `put`,
`get`, `release`, `regenerate`, `record` and `accounting`.

## Certificates

A certificate is tamper-evident: change any bound byte and its digest
changes. It is not, by itself, forgery-resistant. Signatures, revocation,
transparency logs and policy belong to a security service, and Kellogg
provides the canonical encoding (CEX: sorted keys, no floats) and
RFC 6962-style Merkle inclusion proofs for that service to use.

## The specification registry

`kellogg.spec.REGISTRY` lists every constituent of the canonical tensor
specification with one status:

- **EXACT**: implemented on the exact path.
- **FLOAT**: implemented on the float64 plane.
- **CORRECTED**: the statement as written was wrong, and the corrected one is
  implemented.
- **REFUTED**: false as stated.
- **DELEGATED**: owned by another product.
- **RESEARCH**: no precise statement yet.
- **NOT_STARTED**: a declared target with no evidence yet.

`verify_registry()` checks that every named symbol and benchmark exists.
Examples of corrections: the Lucas Cassini identity is 5(−1)ⁿ⁺¹, not
5(−1)ⁿ. An MPS with bond χ is exact iff the Schmidt rank is at most χ at
every cut; entropy at most log χ is necessary but not sufficient. A Kraus
rank is a purification dimension, not an MPO bond dimension.

## Benchmarks

There are 23 benchmarks:

- **Correctness (15)**: fold round trip, the TT-SVD error bound, MPO norm
  preservation, Kraus trace preservation, cross-version digests,
  determinism, boundary isolation, substrate identities, Zeckendorf round
  trip, surface-code algebra and correction, 11D fold, Fisher information,
  Hamiltonians, and DMRG against dense diagonalization.
- **Cost (7)**: gate throughput, contraction throughput, TT-SVD cost,
  compression against fidelity, exact field-operation cost, certificate
  emission, and memory footprint.
- **Meta (1)**: the 10,000-qubit voyage. It builds the state, runs the
  circuit, measures, verifies every certificate, and replays bit-for-bit.

Every row is classified MEASURED, MODELED or NOT_RUN. Kellogg never reports
TFLOPs or hashrate, and it reports compression as a representation ratio
(dense amplitudes over stored parameters), never as physical compression.

## What Kellogg does not do

Kellogg does no device execution, scheduling, hashing, consensus,
signing or durable storage. It imports only the Python standard library
and numpy, and it can be installed and used on its own.

## Licence

MIT.
