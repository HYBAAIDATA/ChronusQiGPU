# Lucas System Tutorial — Sections 9–10

## 9. Extended theoretical properties and algebraic invariants

### 9.1 Divisibility and periodicity

The system uses

```text
L0 = 2, L1 = 1, Ln = L(n-1) + L(n-2)
F0 = 0, F1 = 1, Fn = F(n-1) + F(n-2)
```

with `L_n = φ^n + ψ^n`, `ψ = -1/φ`, only as an algebraic identity. The
runtime implementation uses exact integer recurrence and never evaluates `φ`
or `ψ` in the primary path.

For `a | b` with odd quotient `b/a`, `L_a | L_b`. The even-quotient converse
is false: `L2 = 3` does not divide `L4 = 7`.

The Lucas GCD rule used by the matrix tests is:

```text
g = gcd(m,n)
if (m/g) and (n/g) are odd:
    gcd(L_m,L_n) = L_g
otherwise:
    gcd(L_m,L_n) ∈ {1,2}
```

The Fibonacci state is periodic modulo every positive modulus. Therefore
`L_n = 2F_(n+1) - F_n` is periodic modulo the same modulus. The implementation
exposes exact `pisano_period(m)`, `lucas_period(m)`, and `lucas_rank(m)` helpers.

Verified examples:

```text
π(10) = 60
π_L(10) = 12
π(7) = 16
π_L(7) = 16
ρ(3) = 2
```

A rank may not exist for every modulus; `lucas_rank` returns `None` rather than
inventing one.

### 9.2 Correct fundamental matrix and fast doubling

The fundamental matrix is the Fibonacci Q-matrix:

```text
Q = [[1, 1],
     [1, 0]]

Q^n = [[F_(n+1), F_n],
       [F_n,     F_(n-1)]]
```

Consequently:

```text
trace(Q^n) = L_n
det(Q^n)   = (-1)^n
```

The eigenvalues of `Q` are `φ` and `ψ`. Fast doubling derives from squaring
`Q^k`:

```text
F_(2k)   = F_k (2F_(k+1) - F_k)
F_(2k+1) = F_k² + F_(k+1)²
L_n      = 2F_(n+1) - F_n
```

The implementation is in `scripts/lucas_core.py`, with matrix use in
`scripts/lucas_scale_matrix.py`. The previously used matrix with eigenvalues
`2` and `-1` is not used as the fundamental Lucas representation.

## 10. Multi-engine federation protocol

### 10.1 Full fingerprint handshake

Before exchanging capacities, offsets, or schedules, each node exchanges the
complete 64-character lowercase SHA-256 matrix fingerprint. Truncated hashes
are not accepted.

### 10.2 Authority and quorum

A strict two-node reject-on-mismatch rule can deadlock. The implementation uses
an explicit `FederationManifest`:

```text
authority_ids
threshold
full declared fingerprints
schema_version
matrix_version
```

A node accepts when either:

1. its fingerprint equals every peer fingerprint; or
2. its fingerprint equals the unique fingerprint declared by the configured
   authority quorum.

Otherwise it returns:

```text
INCOMPATIBLE_MATRIX_FEDERATION
```

The decision includes local, peer, canonical, schema, matrix-version, authority,
and threshold diagnostics. No capacity coercion or midpoint negotiation occurs.

### 10.3 Versioning

Both `SCHEMA_VERSION` and `MATRIX_VERSION` are part of the manifest and the
composite fingerprint. Matching content under different namespaces is rejected
as a federation incompatibility.

### 10.4 Operational example

```python
from scripts.federation import FederationManifest, handshake
from scripts.lucas_scale_matrix import LucasScaleMatrixEngine

engine = LucasScaleMatrixEngine()
fp = engine.compute_fingerprint()
manifest = FederationManifest(
    authority_ids=("host-a",),
    threshold=1,
    declared_fingerprints={"host-a": fp},
)
decision = handshake(engine, {"host-b": fp}, manifest)
assert decision.accepted
```

A changed alignment, recurrence index, multiplier, matrix version, or domain
capacity changes the fingerprint and prevents scheduled work from crossing the
boundary.

## Engineering consequence

The mathematical layer supplies exact identities. The matrix layer turns those
identities into domain-specific, aligned capacities. The benchmark layer
measures execution. The verifier and federation layer decide whether evidence
is admissible. These are separate claims and remain separately testable.

## 10.5 Canonicalization rules

All fingerprints use one canonical serialization:

1. JSON object keys are lexicographically sorted.
2. Separators are compact: `,` and `:` without whitespace.
3. Text is UTF-8 encoded.
4. Byte fields are represented as lowercase hexadecimal strings or explicit
   hex wrapper objects where applicable.
5. Sets are serialized in sorted order.
6. Matrix manifests are generated with sorted domain names.
7. Fingerprints cover schema/version fields and all capacity/alignment inputs.
8. Verification compares full 64-character lowercase SHA-256 values with
   constant-time digest comparison where a comparison is security-sensitive.

A formatting-only change that alters canonical input is therefore a deliberate
provenance change, not an invisible presentation change.
