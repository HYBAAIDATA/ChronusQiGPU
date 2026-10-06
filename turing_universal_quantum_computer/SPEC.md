# Pure Quantum Mathematics Specification

Version: 1.0  
Status: executable exact-mathematics contract

## 1. Claim boundary

The system proves exact algebraic identities and exact formal-capacity
statements. It does not relabel formal capacity as executed SHA-256d work and
does not claim that a physical QPU, ASIC, refrigerator, or fleet exists.

No production gate accepts simulation, heuristic ranking, floating-point
tolerance, a placeholder, or self-issued independent review as proof.

## 2. Axioms

1. Exact values are integers, rationals, finite-field values, or declared
   algebraic-number-field values.
2. Floating-point values are forbidden in exact certificates.
3. Q(zeta_8) = Q(i, sqrt(2)) is the canonical characteristic-zero field.
4. Pauli and CSS commutation is evaluated over GF(2).
5. Every proof report declares its convention and complete input parameters.
6. Canonical evidence uses the serialization in section 7.
7. Content digests are SHA-256 over canonical bytes.
8. Certificate verification reconstructs all derived values and fails closed.
9. Formal mathematical capacity is not executed protocol work.
10. Independent review cannot be self-issued.

## 3. Unified exact field

The representation `Q(sqrt(2)) + i Q(sqrt(2))` is the degree-four cyclotomic
field `Q(zeta_8)`, where `zeta_8 = (1+i)/sqrt(2)`.

It contains Q, Q(i), and Q(sqrt(2)). H, S, T, Pauli gates, CNOT, CZ, and SWAP
have exact entries in this field. The Toffoli matrix itself is a rational
permutation matrix; an exact Clifford+T decomposition also remains in
Q(zeta_8).

## 4. Surface-code convention

The exhaustive checker declares:

- lattice: unrotated square edge code
- boundary: mixed planar
- data placement: edges
- X checks: vertex stars, including reduced boundary support
- Z checks: square plaquettes
- distance definition: minimum declared nontrivial logical-operator weight

Every star/plaquette pair is checked over GF(2). Distance 31 checks
`32^2 * 31^2 = 984064` mixed pairs, verifies declared logical
anticommutation, and records correction bound 15. These counts must not be
substituted with counts from a rotated-code convention.

## 5. Exact capacity

For a homogeneous fleet:

`H = M * N * f / I`

For heterogeneous classes:

`H_total = sum_i(M_i * N_i * f_i / I_i)`

All operands are positive integers or exact rationals.

`I` is the initiation interval in cycles per admitted SHA-256d result:

- fully packed: `I = 1`
- serialized three-compression-block path: `I = 3`
- exact bubble fraction `e`: `I = 1 + e`
- custom: exact rational value plus a non-empty justification

Pipeline latency is independently declared as
`compression_blocks * rounds_per_block`. A finite-window certificate subtracts
pipeline fill exactly. The certificate truth class is
`exact_mathematical_capacity_not_executed_work`.

The fixed SHA-256d object is a datapath, not a general-purpose ISA. It has no
instruction-selection or register-allocation claim.

## 6. Certificates

Verification reconstructs the design, exact rates, finite-window result,
floor flags, Merkle root, and certificate digest. Any mismatch raises an error.
Heterogeneous fleet class identifiers are unique and each class declares its
own exact clock, core count, chip count, initiation interval, mode, and
justification.

## 7. Canonical serialization

Canonical bytes are UTF-8 JSON with:

- lexicographically sorted string keys
- no insignificant whitespace
- Unicode emitted directly
- integers only; floats are rejected
- rational `p/q` encoded as
  `{"$rational":{"numerator":p,"denominator":q}}` in reduced form
- bytes encoded as `{"$bytes_hex":"..."}`
- tuples encoded as arrays
- unsupported types rejected

This canonical form, not an implementation-specific runtime representation,
is hashed.

## 8. Thermodynamic boundary

The many-to-one SHA-256d interface is logically irreversible. Its circuit can
be reversibly embedded with retained ancillary state, but end-to-end reset and
I/O obligations remain. Landauer applies per erased bit:

`E >= b * k_B * T * ln(2)`

No numerical energy is asserted without measured physical inputs.

Cryo-CMOS reference profiles are explicitly labeled:

- current reference: 10 mW/tile
- five-year target: 5 mW/tile
- ten-year target: 1 mW/tile

Targets are not current measurements.

## 9. Formal/computational split

Lean checks three dependency-free kernels without `sorry` or axioms:

1. zeta_8 exponent periodicity
2. even-overlap surface-code commutation predicate
3. cross-multiplied natural-number capacity floor

Python exact arithmetic verifies full field generators, exhaustive distance-31
pair enumeration, exact rational certificates, canonical digests, and replay.
The Lean kernels are not misrepresented as a complete formalization of every
Python line.

## 10. Reproduction

```bash
python -m pip install -e ./turing_universal_quantum_computer
python scripts/verify_pure_quantum_math.py \
  --output artifacts/pure-quantum-math/reproduction.json
```

The focused CI executes on Python 3.11, 3.12, and 3.13 and requires identical
canonical reproduction digests. Lean runs separately and fails on any theorem
or build error. Independent model review remains an external gate.