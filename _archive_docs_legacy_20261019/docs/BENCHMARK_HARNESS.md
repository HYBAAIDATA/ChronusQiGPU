# Verifiable Lucas-matrix benchmark

This harness executes one sealed fingerprint workload through classical and
PQSC paths while applying the Lucas ladder independently by capability. It is
offline and makes no pool or external API calls.

## Scaling matrix

The allowed exact Lucas powers are `7, 10, 12, 15, 18, 20, 31, 50, 76`, producing:

```text
L7  = 29
L10 = 123
L12 = 322
L15 = 1364
L18 = 5778
L20 = 15127
L31 = 3010349
L50 = 28143753123
L76 = 7639424778862807
```

The matrix is not one-size-fits-all. Each domain has its own power:

```text
search          -> L10
memory          -> L7
tensor          -> L12
virtual_quantum -> L15
hardware        -> L31
intelligence    -> L50
coherence       -> L18
verification    -> L20
schedule        -> L76
```

This assignment is configuration, not a hidden law. Change it through
`--scale-matrix-json`; the complete matrix is included in the workload
fingerprint and every result. The verifier rejects a result carrying a
 different matrix or dimension set.

Lucas scaling is applied exactly, as integer ceiling of `base * L_power / L10`:

- search space and search budget;
- memory units;
- tensor width and depth;
- virtual-qubit count and exact state dimension `2^q`;
- mathematical hardware core and memory capacity;
- intelligence budget;
- verification budget;
- deterministic schedule stride.

No floating-point value is used to derive these dimensions.

## Measurement paths

- **Classical:** ascending nonce search using the configured hash primitive.
- **PQSC:** the same workload and predicate, visited by the Lucas-powered
  deterministic schedule. It does not switch to a different hash primitive.
- **Quantum model:** exact integer square-root query-scale model only. It is
  marked `UNPROVEN_NO_QPU_BACKEND`; no QPU or simulator result is fabricated.

Every measured candidate is re-hashed by the independent verifier. The JSON
artifact contains the matrix, dimensions, workload fingerprint, raw results,
environment, and SHA-256 seal.

## Run

```bash
python scripts/benchmark_harness.py \
  --workload-id fingerprint-001 \
  --seed-hex 0000000000000000000000000000000000000000000000000000000000000000 \
  --nonce-bits 12 \
  --target-bytes 1 \
  --scale-matrix-json configs/lucas_scale_matrix.example.json \
  --trials 3 \
  --output artifacts/fingerprint-001.json
```

## Target evaluation

`configs/benchmark_targets.example.json` contains the external target vector:
classical anchor `20`, quantum model `13`, and PQSC `5`. These remain target
values; the artifact retains actual measurements. A passing PQSC comparison is
not a physical quantum result, iGPU hashrate result, or accepted mining share.

```bash
python scripts/benchmark_harness.py ... \
  --targets-json configs/benchmark_targets.example.json \
  --output artifacts/fingerprint-001.json
```

## Tests

```bash
python -m pytest -q tests/test_benchmark_harness.py
```

The tests verify the exact ladder, independent per-domain powers, matrix-bound
fingerprints, scaled dimensions, schedule coverage, tamper rejection, model
labeling, artifact sealing, and reproducible outcomes.

## Formal matrix engine

The benchmark is bound to `scripts/lucas_scale_matrix.py`. It computes exact
`(L_n, F_n)` pairs with fast doubling in `O(log n)` and produces a canonical
matrix manifest. The workload stores the manifest SHA-256 fingerprint; the
verifier rejects mismatched recurrence indices, capacities, or fingerprints.

Domain capacities use exact rational multipliers and explicit upward alignment:
`floor(L_n * numerator / denominator)`, followed by alignment to the configured
cache/page boundary. Composite domains use the exact ring identities:

```text
L(a+b) = (L_a L_b + 5 F_a F_b) / 2
L(a-b) = (-1)^b (L_a L_b - 5 F_a F_b) / 2
```

The formal manifest supports additional domains and indices beyond the primary
benchmark matrix, including network `L11`, database `L13`, sharding `L16`,
I/O `L21`, and the requested `L7`, `L31`, `L50`, and `L76` domains.
