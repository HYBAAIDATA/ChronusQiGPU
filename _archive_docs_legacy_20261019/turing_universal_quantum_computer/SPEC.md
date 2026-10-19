# Pure Quantum Mathematics Specification

Version: 1.0  
Status: executable exact-mathematics contract

## 1. Claim boundary

The system proves exact algebraic identities for the TURING Virtual Quantum
Computer. It does not claim that a physical QPU exists. Hashrate capacity and
SHA-256d work are Mining's and are not specified here.

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
9. Mining formal-capacity claims are delegated to Mining and are not TURING release claims.
10. Independent review cannot be self-issued.

Exact computational proof evidence is labeled `exact_verified`, never
`measured`; the latter is reserved for physical observations.

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
- boundary: rough left/right, smooth top/bottom (planar)
- data placement: edges, n = d^2 + (d-1)^2
- X checks: d(d-1) vertex stars, weight 4 in the bulk and 3 on the boundary
- Z checks: d(d-1) square plaquettes, weight 4 in the bulk and 3 on the boundary
- distance definition: exact minimum nontrivial logical-operator weight,
  computed as the shortest odd-parity boundary path (not declared)

Every star/plaquette pair is checked over GF(2). The logical qubit count is
computed exactly (k = n - rank Hx - rank Hz = 1), the declared logicals are
checked to commute with every check and to anticommute with each other, and
the distance is computed exactly. Distance 31: n = 1861, 930 stars, 930
plaquettes, `930^2 = 864900` mixed pairs, k = 1, exact distance 31,
correction bound 15. These counts must not be substituted with counts from a
rotated-code convention.

The earlier convention placed a star on every vertex and a plaquette on every
face of a 32 x 32-vertex grid (`32^2 * 31^2 = 984064` commuting pairs). Its
check ranks give k = 0: it encodes no logical qubit, so its distance and
correction bound were undefined. `all_vertex_star_report` reproduces it.

## 5. Exact capacity

Moved to Mining. The exact formal-capacity model (H = M * N * f / I, the
homogeneous and heterogeneous fleet certificates, initiation intervals and
pipeline fill) is a hashrate model, not a property of the virtual quantum
computer. It lives in `mining.deterministic_hashrate` and
`mining.fault_tolerant_asic`, specified in
`docs/DETERMINISTIC_10_EH_MATHEMATICAL_CAPACITY.md`.

## 6. Certificates

Every certificate this package issues (run witnesses, computation
certificates, the surface-code proof digest) is verified by reconstructing all
derived values from the canonical inputs; any mismatch raises an error.
Capacity certificates are Mining's (section 5).

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

Moved to Mining. The SHA-256d Landauer boundary and the cryo-CMOS reference
profiles describe mining hardware, not the virtual quantum computer; they live in
`mining.thermodynamics_exact` and `docs/THERMODYNAMIC_FLOOR_OF_BITCOIN_MINING.md`.

## 9. Formal/computational split

Lean checks the two TURING-owned dependency-free kernels without `sorry` or axioms:

1. zeta_8 exponent periodicity
2. even-overlap surface-code commutation predicate

The historical exact capacity predicate and 10 EH/s arithmetic witness are preserved
under `mining/formal/MiningCapacity.lean` and are not part of TURING's formal release
claim set.

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