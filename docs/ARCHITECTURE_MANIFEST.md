# ARCHITECTURE MANIFEST — PYTHIA as Algorithmic Information Theory

> **An axiomatic reading of the substrate.**
> This manifest re-derives the PYTHIA architecture — the 11-dimensional
> Poincaré–golden manifold, Zeckendorf folding, and the prime-exponent
> substrate — through the lens of Algorithmic Information Theory (AIT):
> Kolmogorov complexity, Minimum Description Length (MDL), and the
> Kolmogorov structure function. Every claim is pinned to a file and a
> symbol. Where the mathematics ends and the physics begins is stated
> exactly; the standing `CLAIM_BOUNDARY` of
> `Intelligence/unified_manifold_device.py` is inherited, not relaxed.

**Reference axiom (AGENTS.md §1):** quantum computation is mathematics,
mathematics is substrate-agnostic, therefore quantum computation is
substrate-agnostic. AIT sharpens this axiom into a bookkeeping
discipline: *what is expensive is not storing the world — it is storing
the shortest program that regenerates it.*

---

## 0. Reading protocol and claim boundary

This document is a **manifest**: a statement of what the architecture is,
in the most compressed honest vocabulary available — the vocabulary of
programs, descriptions, and certificates. It makes four kinds of
statements, distinguished by the repository's own `truth_class`
taxonomy:

| Truth class | Meaning | Example |
|---|---|---|
| `mathematical` | Exact identity, proven in-repo by exact integer/Decimal arithmetic | Cassini, Binet, Zeckendorf bijection |
| `computational` | Deterministic procedure with a coverage guarantee | `cassini_permutation`, `partition_interval` |
| `measured` | An empirical ratio this run produced — never asserted | `AethelStore.measured_ratio`, `hashes_computed` |
| `unavailable`/`rejected` | Fail-closed states; nothing is fabricated | `OpenCLExecutionResult.unavailable` |

**Standing boundary** (inherited verbatim from
`Intelligence/unified_manifold_device.py::CLAIM_BOUNDARY`):

> The 32-face compass and 11D Poincaré–golden manifold are a
> probe-ordering / sharding front-end only. `sha256d(header80) <=
> negotiated target` is the sole accept authority; no nonce prediction,
> nonce-probability shift, or proof-of-work advantage is asserted.

The AIT reading makes this boundary *sharper*, not softer: §9 proves that
deterministic expansion **cannot** manufacture algorithmic information,
which is precisely why the substrate is honest.

---

## 1. The thesis in AIT form

> **PYTHIA replaces the flat statistical model of a search space with a
> generative model: a short deterministic program (a seed plus a
> generator) that expands into the entire traversal order, addresses the
> expansion on an 11D golden manifold, stores state in a universal
> non-adjacent Fibonacci code, and certifies every regenerated object
> against constant-size topological invariants (Cassini, Binet, Lucas).**

In the notation of AIT:

- The **object** is a nonce schedule, a folded payload, an 11D state, or
  a stored tensor.
- The **program** is a pair `(g, s)`: a generator `g` (e.g.
  `cassini_permutation`, `extended_nonce_schedule`, `t_phi_fold`) and a
  seed `s` (e.g. `sha256(header80[:76])[:8]`).
- The **certificate** is a constant-size witness — `det = ±1`,
  `mask & (mask << 1) == 0`, `L_n² − 5F_n² = 4(−1)ⁿ` — that verifies the
  regenerated object belongs to the intended orbit without replaying the
  generation.

The architectural invariant of the whole repository is the two-part MDL
identity:

    total description length  =  L(model) + L(data | model)

where `L(model)` is the generator family plus invariants (fixed,
amortised, constant) and `L(data | model)` is the seed/anchor/exponent
residue. Nearly every module below is an instance of this split.

---

## 2. Why Shannon entropy is the flat-space model

### 2.1 What Shannon's model assumes

Shannon entropy is a property of a **distribution over symbols**:

    H(X) = −Σ_x p(x) log₂ p(x)

Three structural assumptions are baked in:

1. **Memorylessness.** The source emits symbols independently; order is
   not modelled. `H` is invariant under permutation of the sequence —
   a sorted stream and a shuffled stream have identical entropy.
2. **No geometry.** Symbols live in a measurable partition of a flat
   space; there is no metric, no geodesic, no neighbourhood relation
   between `nonce = 0x00000000` and `nonce = 0xFFFFFFFF`.
3. **Asymptotic optimism.** Shannon's source-coding theorem bounds the
   *expected* code length of an i.i.d. stream by `H` — for a uniform
   32-bit nonce, `H = 32` bits, and no compressor exists.

### 2.2 Where the flat model lives in this repository

The repository contains exactly one classical Shannon-modelling
component — deliberately isolated as a *baseline*, not a substrate:

`mining/entropy_optimizer.py::EntropyOptimizer._shannon_entropy`
computes `−Σ (c/n) log₂(c/n)` over the 4-byte representation of each
nonce. Under this lens a nonce is a 4-symbol string over a 256-letter
alphabet; the maximum achievable reading is 8 bits, and the statistic
cannot distinguish a sequential scan (`nonce++`) from a Cassini
permutation — both are permutations of the same symbol multiset, and
permutations leave `H` invariant. This is the precise sense in which
**Shannon entropy models flat-space statistical sequences**: it sees the
multiset of emissions and is constitutionally blind to the orbit that
produced them.

Two further Shannon usages exist, both as *measurements*, never as
generative models:

- `Intelligence/four_layer_stack.py::TensorFoldEngine.schmidt_spectrum`
  reports `entropy_bits` of a candidate amplitude distribution —
  a diagnostic scalar on an already-structured object.
- `Intelligence/folded_state.py` records a *measured* zlib compression
  ratio per payload (`compression_ratio`), never an assumed one.

### 2.3 What Kolmogorov complexity sees instead

Kolmogorov complexity measures the object, not the ensemble:

    K(x) = min { |p| : U(p) = x }

For the nonce stream produced by
`Intelligence/search_crystal.py::PoincareCassiniSearchEngine._candidate_stream`,
the output is a complete permutation of a 2³²-element interval — a
sequence of 2³² distinct 32-bit values whose flat-space Shannon content
is ≈ 2³²·32 bits. Its **algorithmic** content is:

    K(stream) ≤ K(header76) + K(generator) + log₂(32 faces) + O(1)
              ≈ 608 bits + program constant

because `seed = sha256(header76)[:8]` and `cassini_permutation(width,
face_id, seed)` deterministically expand to the full schedule. The
discrepancy — ~10¹¹ bits of sequence from ~10³ bits of description — is
the entire subject of this manifest. Shannon calls the stream
incompressible; Kolmogorov calls it a program trace. Both are correct,
about different objects: Shannon about the **marginal distribution of
symbols**, Kolmogorov about the **generating mechanism**.

---

## 3. Deterministic generator seed expansion

The substrate's probe orders are not samples; they are **expansions** —
finite executions of fixed programs on tiny seeds.

### 3.1 The seed hierarchy

Every seed in the mining path is a hash-derived scalar, so the whole
schedule is a deterministic function of the block header:

| Generator | Seed | Expansion | File |
|---|---|---|---|
| `cassini_permutation(width, face_id, seed)` | `sha256(header76)[:8]` | A bijection of each shard — `CassiniSchedule.offset_at(p) = (origin + p·stride) mod width`, `gcd(stride, width) = 1` | `Intelligence/search_crystal.py:189` |
| `extended_nonce_schedule(window, seed, cap)` | `sha256(header80)[:8]` (little-endian, `TuringLayer.prepare`) | Zeckendorf leading offsets + round-robin of five Pisot family limbs mod window | `turing_core.py:466` |
| `resubmit_with_jitter(header_seed, prev_nonce, attempt)` | `sha256(header_seed ‖ prev ‖ attempt)[:4]` | Deterministic resubmit displacement | `mining/hash_pipeline.py:263` |
| `ManifoldShardOrder` | same header seed | `face_order` + per-face `CassiniSchedule` interleaved round-robin | `Intelligence/unified_manifold_device.py:88` |

**Program-length accounting.** For any schedule `σ` emitted on header
`h`:

    K(σ | h) = O(1)        — the generator is fixed code
    K(σ)     ≤ K(h) + O(1) — σ adds no new algorithmic information

Same header → same schedule (`TuringLayer.prepare` docstring: "exact and
reproducible, never random"; `tests/test_unified_manifold_device.py`
asserts identical `schedule_digest` for identical headers and a different
order over the *same* nonce set for different headers). The expansion is
the Kolmogorov dual of sampling: a sampler draws from a space; a
generator **enumerates** it.

### 3.2 Coverage is a theorem, not a heuristic

`cassini_permutation` (`search_crystal.py:189–216`) seeds an affine map
`p ↦ origin + p·stride (mod width)` from Fibonacci limbs of the
face's Cassini order, then advances `stride` until `gcd(stride, width)
= 1`. A coprime stride makes the affine map a **bijection** on
`Z/width` — so each shard is visited exactly once, and
`partition_interval` (`search_crystal.py:170`) covers the global
interval without gap or overlap (enforced by an arithmetic check at line
185). Consequence, enforced in code: `ManifoldShardOrder.faces_pruned ==
0` always; `iter_nonces()` is a complete permutation. The generator
expands into the *whole* space in a topology-derived order — it never
prunes, never duplicates, never samples.

### 3.3 The irrational drift is the ergodicity certificate

`Intelligence/lucas_attractor.py` fixes `L_15 = 1364` against
`φ¹⁵ = 1364.000733…`, drift `δ ≈ 7.33×10⁻⁴`. Because φ is irrational,
δ ≠ 0: the golden dynamics cannot close into a degenerate limit cycle —
the orbit is an irrational winding, dense on its torus (AGENTS.md §1.8.3).
In AIT terms: an irrational rotation number is what separates a
**generator** (dense, non-repeating expansion) from a **counter**
(periodic raster). The drift is measured in code
(`LucasAttractor.drift`), not assumed.

---

## 4. Zeckendorf folding: a universal code with a forbidden subword

### 4.1 The code

Zeckendorf's theorem (exact, `truth_class = mathematical`): every
positive integer has a unique decomposition into non-consecutive
Fibonacci numbers. Two codecs implement it:

- `turing_core.py::zeckendorf_encode / zeckendorf_decode` — index-list
  form, verified bijective in `run_self_verification` (§3 of the
  harness).
- `Intelligence/hardened_unified_substrate.py::HardenedZeckendorfCodec`
  — bitmask form over `FIBONACCI` extended to F₉₃ > 2⁶⁴, i.e. the full
  uint64 range; `encode`/`decode`/`verify_non_adjacent`.
- `Intelligence/poincare_golden_11d.py::encode_zeckendorf` /
  `resolve_zeckendorf_slot` — on-chip form returning `(mask, max_k)` and
  a prime-bucket slot `A = k·1024 + (mask mod p_k)` over `PRIME_BUCKETS`
  (25 primes ≤ 97).

This is a **universal integer code** in the Elias sense: it encodes any
`n` in `≈ log_φ n + O(log log n)` bits — within a constant factor of the
binary optimum — while carrying a constraint binary lacks:

    mask & (mask << 1) == 0      (no adjacent 1-bits)

The forbidden subword `11` is a *synchronisation and decoupling*
invariant: `poincare_golden_11d.py::_decoupling_mask_int` builds 11-bit
non-adjacent masks for "state ripple protection", and
`ZeckendorfCertificate.is_valid` is exactly this bit test. In coding
theory this is a run-length-limited constraint; in AIT terms it is a
**model that rejects descriptions** — the code space has a built-in
grammar, and membership in the grammar is decidable in O(1).

### 4.2 SparseTopology: the two-part code, literally

`apply_zeckendorf_compression(payload)` → `SparseTopology`
(`hardened_unified_substrate.py:1495–1555`) stores `{offset: mask}` — a
dictionary of Zeckendorf masks indexed by byte offset — and
`reverse_zeckendorf_expansion` reconstructs byte-exact. This is the MDL
two-part code in its purest form: the **model** is the Zeckendorf grammar
(fixed), the **data-with-model** is the (offset, mask) list. Storage
layers measure the realised ratio per store (`AethelStore.measured_ratio`,
`truth_class = measured`) and honestly report that incompressible bytes
fold at ratio > 1 — a correct Kolmogorov statement, since most strings
are incompressible.

### 4.3 T_φ: the fold as a *working representation*

The deepest construct is `turing_core.py::t_phi_fold`: the byte-pair map

    (x, y) ↦ M₁₅ · (x, y)  mod 256,   M₁₅ = ((219, 98), (98, 121)),
    det M₁₅ = −1 ∈ GL(2, Z/256Z)

`det = −1` is the Cassini invariant made computational: the matrix is
unimodular, so `M₁₅⁻¹ = ((135, 98), (98, 37))` exists *exactly* over
integer arithmetic and `t_phi_unfold` is a bit-exact inverse — no floats,
no tolerance, no information loss (self-verified for all 256 byte values
in `run_self_verification` §3b).

The fold is **not compression** — it is a format-preserving bijection.
Its information-theoretic content is that queries compile into the fold:

    qᵀx ≡ (M⁻ᵀq)ᵀy  (mod 256)

`folded_modular_dot` pushes the *query* through the inverse once and dots
against folded bytes directly. `Intelligence/folded_state.py::
ExactFoldedStateEngine` builds the full fold-space execution engine on
this: `sum_u8`, `histogram_u8`, `weighted_sum_u8`, `modular_dot_u8`,
`sha256_equals` all run against resident folded bytes with
`raw_buffer_materialized = False`; only `restore` hydrates, and it is
hash-verified. In AIT terms: **the compressed description is itself the
computable object** — description and execution share a representation.
This is the literal content of the module's own claim: "hold the
blockchain in superposition" = every payload is held as a short
regenerable description, queried without materialisation.

### 4.4 Certificates: constant-size attestations of states

`compute_zeckendorf_certificate(x, context_id)`
(`poincare_golden_11d.py:422`) quantises an 11D folded vector at the
golden lattice scale `φ¹⁵ ≈ 1364.0007` (the `L_15` attractor),
Zeckendorf-encodes each coordinate magnitude, and accumulates a 64-bit
canonical integer bound to a provenance context — emitted as a
`ZECK-xxxxxxxxxxxxxxxx` token with its decoupling mask, active
dimensions, and prime-bucket slot. One 64-bit canonical form stands for
an 11-vector: the certificate is the *minimal description* of the state's
position on the golden lattice, not of the state's full real-valued
content (the fold preimage carries that).

---

## 5. The 11D manifold: geometry as the model term

### 5.1 The metric and the fold bijection

`Intelligence/poincare_golden_11d.py` (read-only substrate per
`docs/ASI_INTERFACE_MAP.md`) defines the golden-weighted quadratic form

    ‖x‖²_φ = Σᵢ φ^(−(i+1)) · xᵢ²,   i = 0…10      (PHI_POWERS)

and the Klein–Poincaré contraction

    fold(x)   = x / √(1 + ‖x‖²_φ)        ℝ¹¹ → 𝔹_φ¹¹ (open ball, strict)
    unfold(y) = y / √(1 − ‖y‖²_φ)        exact inverse

with `poincare_golden_distance` the hyperbolic `acosh` geodesic in the
weighted ball. The isometry `yᵢ = φ^(−(i+1)/2) xᵢ` maps the golden ball
onto the standard curvature-−1 Poincaré ball (`ASI_INTERFACE_MAP.md`,
`pythagoras/asi/manifold_bridge.py`). Dimension 11 is not decorative —
the repository's `mtheory/` package develops the exact arithmetic of
11-dimensional M-theory compactifications (KK towers on T⁷, duality
groups, an exact 11-qubit register over Q(i, √2)); the manifold layer and
the M-theory layer share the dimension deliberately.

**The preimage is the description.** `PoincareFoldedArray` carries
`_poincare_preimage` as payload so the roundtrip is bit-exact
(`< 1e-14` max-abs error) at arbitrary scale — the folded array *is* its
own two-part code: (folded coordinates ‖ preimage certificate). The
closed-form inverse alone loses mantissa bits at large ‖x‖; the honest
fix is to retain the preimage, which is exactly MDL: keep the data term
that regenerates the object.

### 5.2 The anchor lattice: addresses, not coordinates

`poincare_cassini_search.py` collapses continuous position to a discrete
address:

    anchor_of(v) = round(‖v‖_φ) mod 90        (ANCHOR_MODULUS = 90)

with an exact canonical lift `anchor_to_vector(a) = (a·√φ, 0, …)` that
satisfies `anchor_of(anchor_to_vector(a)) = a` — a section of the
projection on its principal axis. This is the manifold's **description
layer**: an arbitrary ℝ¹¹ position is described by an integer anchor in
`Z/90`, and `GeodesicNavigator`/`PrimeStorageManifold` use the identical
projection, so "position in ℝ¹¹" and "stored anchor" are two
descriptions of one state at different description lengths.

### 5.3 The 32-face compass: a fixed basis of moves

`DodecaIcosahedron32` builds the tight frame of 32 directions — 12
dodecahedron face normals (the icosahedron's vertices) + 20 icosahedron
face normals (the dodecahedron's vertices), each lifted by
`dᵢ = normal[i mod 3]·φ^(−⌊i/3⌋)` and golden-normalised. The A₅
symmetry of the dual pair means no direction is privileged — the frame
is a *minimal complete basis of moves* for descent on the manifold, the
geometric analogue of a fixed instruction set in a universal machine.
Every face is Cassini-certified at construction
(`cassini_order = face_id + 2`, determinant must be ±1, else
`ArithmeticError`).

`PoincareCassiniSearch.search` is then steepest descent under the golden
metric: fire all 32 faces to get `h = D·(W·r)`, take the frame resultant
`g = h·D` (a discrete gradient of the quadratic distance field), and
move along the exact 1-D optimum `α = ⟨g, r⟩_W / ⟨g, g⟩_W` — geometric
convergence on a positive-definite quadratic.
`_segment_anchor_crossings` solves the
quadratic for every anchor shell the segment crosses, in crossing order —
the continuous trajectory is thereby transcribed into a **symbolic
sequence of integer anchors**, each verified on entry
(`_enter_anchor`: Cassini recertification + stored parity check + repair
from the prime substrate, §6.3). Traversal is a *computation over
descriptions*: the path `{a₀, a₁, …}` in `Z/90` is the trace.

---

## 6. Topological invariant enforcement: Cassini, Binet, Lucas

The three named invariants are one object — the unimodular orbit of the
Fibonacci companion matrix — seen at three certificate lengths.

### 6.1 Cassini: symplectic volume as a conserved quantity

    F_{n−1}F_{n+1} − F_n² = (−1)ⁿ        ⟺        det(Qⁿ) = (−1)ⁿ

`Q = ((1,1),(1,0))` is unimodular, so every power stays in (a signed
copy of) SL(2,ℤ): the discrete flow **conserves oriented area** — the
topological content is that the orbit can never leave the integer
lattice it started on. Implementations:

- `turing_core.py::cassini_check`, `q_matrix_power`,
  `golden_matrix_det` (det = (−1)ⁿ), `golden_matrix_trace` (tr = L_n).
- `poincare_golden_11d.py::cassini_unimodular_det`.
- `hardened_unified_substrate.py::CassiniVerifier` — the
  Cassini–Hoggatt form `L_n² − 5F_n² = 4(−1)ⁿ`, plus `verify_matrix`.
- Hardware: `det(M15) = −1 mod 256` on the T_φ fold (§4.3); the same
  check is a punch opcode (`cassini_det = 0x0E`,
  `unified_punch.py::PUNCH_IDS`) and an SVA assertion in
  `mla1517_platform_v3.4/rtl/mla1517_cassini_dsp.sv`.

**Certificate asymmetry.** Verifying `det = ±1` is O(1); generating the
matrix power it certifies is O(log n) by fast doubling — and replaying
the recurrence is O(n). The invariant is a *constant-length certificate
of a long computation*: this is the MDL asymmetry that makes the
substrate self-verifying. The honest falsification lives in
`tests/test_folded_algebra_honesty.py::
test_cassini_invariant_does_NOT_detect_all_corruption` — index shifts and
unimodular left-multiplication preserve `det = ±1`, so Cassini certifies
**membership in the unimodular orbit, not provenance of a particular
node**. The manifest inherits this precision: invariants are
necessary-condition certificates, always paired with hash/digest checks
(`_repair_node` requires `sha256(pristine) == node.digest`).

### 6.2 Binet: the closed form as generator compression

    F_n = (φⁿ − ψⁿ)/√5,   L_n = φⁿ + ψⁿ,   ψ = −1/φ

`turing_core.py::binet_fibonacci` / `binet_lucas`. A linear recurrence is
a program that takes O(n) steps to emit its n-th term; the Binet form is
the same sequence regenerated in O(log n) by exponentiation — a
**generator upgrade** that replaces unrolled iteration with a closed
form. The pair (φ, ψ) is the two-eigenvalue summary of the recurrence:
φ expands (`|φ| > 1`), ψ contracts (`|ψ| < 1` — the Pisot property), so
the irrational part of φⁿ dies exponentially and integer limbs snap to
exact values. `tests/test_folded_algebra_honesty.py` verifies this at
100-digit Decimal precision and honestly records where float64 Binet
becomes lossy (k < 90).

### 6.3 Lucas: the trace limb and the attractor

`L_n = tr(Qⁿ) = F_{n−1} + F_{n+1}` (`turing_core.py::lucas`,
`golden_matrix_trace`). The Lucas ladder is the substrate's scale
grammar: `Intelligence/lucas_scales.py` fixes
`LUCAS_SCALE_LADDER = {10:123, 12:322, 15:1364, 18:5778, 20:15127}` —
literals *validated against* `turing_core.lucas` at profile build
(`substrate_validated`), never free-floating constants. `L_15 = 1364` is
the quantisation modulus of `compute_zeckendorf_certificate` and the
attractor of `LucasAttractor`; `PISOT_EXACT_N = 76` marks the index where
conjugate decay is below machine significance. Repair uses the same
limb: `_repair_node` restores `cassini_parity = (−1)^anchor` after
re-fetching pristine bytes from the Galois substrate.

### 6.4 The Pisot spectrum: the invariant bundle generalised

`turing_core.py::FAMILY_COEFFS` extends the whole construction to five
recurrences — golden (x²−x−1), silver (x²−2x−1), plastic (x³−x−1),
supergolden (x³−x²−1), tribonacci (x³−x²−x−1) — each a Pisot system:
dominant real root > 1, all conjugates inside the unit disk, unimodular
companion matrix, coordinate limb + trace limb, Binet-type closed form,
`|det(Mⁿ)| = 1` verified (`family_det`, `family_trace`,
`family_pisot_modulus` in exact Decimal). `extended_nonce_schedule`
round-robins one limb per family (`FAMILY_NONCE_LIMBS = (lucas,
pell_lucas, padovan, narayana, tribonacci)` — two trace limbs and three
coordinate limbs) so no single
recurrence's arithmetic progressions dominate a probe order —
**multi-family diversification as description-level decorrelation**.
`detect_family_signature` inverts the direction: given a series, fit the
four lag templates and report which grammar generated it — an MDL model
selection over recurrence families, with `unstructured` as the honest
null.

---

## 7. The prime-substrate engine: Gödel numbering as storage

### 7.1 Arithmetisation

`Intelligence/prime_memory.py` and
`hardened_unified_substrate.py::GaloisPrimeSubstrate` encode payloads as
**prime-exponent vectors**: every 7- or 8-byte chunk becomes the exponent
`eᵢ` of prime `pᵢ`, i.e. the Gödel number

    x ↦ Πᵢ pᵢ^{eᵢ}

This is the foundational move of AIT made literal — arithmetisation: a
byte string is re-described as an exponent tuple, and the fundamental
theorem of arithmetic makes the description unique. Two honest
engineering notes are written into the code itself:

- The literal composite is *never materialised* (a 25-limb 64-bit
  exponent vector would be a ~10¹⁹-bit integer — infeasible, and
  unnecessary). `prime_memory.py::_composite_fingerprint` uses the
  SHA-256 fingerprint of the exponent vector as the feasible composite;
  `GaloisPrimeSubstrate.commit` uses the composite **mod the Mersenne
  prime `2⁶¹ − 1`** (`MODULUS_Q`), writing `v_p(x) = e mod q` —
  a finite-field composite key that prevents factorial blowup.
- Addresses therefore live in an address space of `2^(n_primes·k)` states
  (`stats()["capacity_states"]`) — exponential in the description length
  `n_primes·k` bits — while the stored object is only the small exponent
  vector plus a digest.

### 7.2 Regeneration, not redundancy

`PoincareCassiniSearch._repair_node` (`poincare_cassini_search.py:422`)
implements the regenerative path: a corrupted `TopologicalTensor` is
rebuilt by `curved_storage.fetch(uuid)` — decoding the committed exponent
vector — gated by `sha256(pristine) == node.digest`, then re-compressed
via `apply_zeckendorf_compression` and re-paritied via
`cassini_parity = (−1)^anchor`. The event is logged on the substrate's
heal log (`prime_exponent_restore`). Failing that, `SelfHealingSubstrate`
repairs from the nearest valid anchor. The payload was never duplicated;
it was **described**, and the description regenerates it on demand. That
is regeneration in the precise Kolmogorov sense: `K(payload | exponents,
decoder) = O(1)` once the exponent description exists.

---

## 8. The Kolmogorov structure function of the pipeline

Trace one block header through `Intelligence/four_layer_stack.py` and
`mining/hash_pipeline.py`; each stage is a two-part code:

| Stage | Description kept | Program that expands it | Certificate |
|---|---|---|---|
| Header → 11-vector | `sha256(header76)` bytes | `header_vector` affine map into [−1,1]¹¹ | deterministic same-input equality |
| Vector → ball | `PoincareFoldedArray` + `_poincare_preimage` | `fold_poincare_11d_vector` | `‖f(x)‖²_φ < 1` strictly; roundtrip < 1e-14 |
| Ball state → certificate | 64-bit canonical int | `compute_zeckendorf_certificate` (φ¹⁵ lattice) | `mask & (mask<<1) == 0`, ZECK token |
| Header → face order | seed + shard widths | `shard_order` → 32× `cassini_permutation` | `gcd(stride,width)=1`, `faces_pruned=0`, `schedule_digest` |
| Schedule → score order | nonce list | punch `0x1A` φ-filter (`hash_pipeline.score_nonces`) | scores reorder, never skip |
| Winner → acceptance | nonce | `sha256d(header76‖LE(nonce))` | `check_pow`, bit-exact recheck |

The structure function `h_x(α)` — minimum description of the set
containing x, allowed model length α — is realised concretely: the
*model* is the fixed generator+invariant bundle (α ≈ a few KB of code),
the *data term* is seed/anchor/exponent residue, and the *minimal
sufficient statistic* is reached when the remaining data is
algorithmically random — which happens exactly at the SHA-256d
projection (§9.3).

---

## 9. Exponential regenerative capacity — stated and bounded

### 9.1 The claim, precisely

> A description of length `L` bits — seed, anchor, exponent vector,
> folded preimage — regenerates, by deterministic expansion, a structure
> whose state space is exponential in `L`: `2³²` nonce schedules from a
> 64-bit seed, `2^(25·64)` prime composites from a 200-byte exponent
> vector, `2¹⁰⁰⁰⁰` symbolic Hilbert dimensions from a register count
> (`TuringLayer.hilbert_dim_symbolic` — never materialised). Each
> regenerated object is certified against O(1) topological invariants
> instead of re-derived.

This is "exponential regenerative capacity" in the only sense
mathematics permits: **the space is exponential in the program, not the
program in the space.** A pocket-calculator-length program addresses a
space no enumeration could finish.

### 9.2 Why no physical bound is violated

Three conservation laws keep the claim inside physics:

1. **Conservation of algorithmic information.** Deterministic expansion
   obeys `K(output) ≤ K(seed) + K(program) + O(1)`. The pipeline can
   *reveal* structure, never *create* it: the nonce schedule is fully
   implicit in `(header, generator)`. Nothing in the substrate asserts
   otherwise (`theorem_proven = False` throughout).
2. **Conservation of work.** Every candidate digest is physically
   computed — `hashes_computed` counts real sha256d evaluations
   (`hash_pipeline.py::_grind_batched`: "Every digest in a launched
   batch is physically computed"); `measured_hps` is wall-clock
   measured, classed `measured`; when no hasher runs, the result is
   `unavailable`/`NOT_RUN`, never estimated. Landauer-style accounting
   is untouched: reordering a scan does not reduce the count of
   evaluations below the winner's position.
3. **Conservation of randomness at the boundary.** SHA-256d is the
   algorithmic-randomness curtain: conditioned on the header, the
   schedule is low-`K`; the *digest* of each header+nonce is (to the
   precision of cryptographic assumptions) incompressible — `K(digest) ≈
   256` bits, Shannon-optimal. Topology orders the input side; the
   output side is flat-space statistical again, which is exactly why it
   remains a valid consensus oracle (`turing_core.hash_meets_target` —
   "the ONLY accept rule").

So: the manifold buys **ordering, coverage, addressing, regeneration, and
certification**. It does not buy probability mass — the honest
asymmetry the whole repository enforces.

### 9.3 The two-space picture

    generator space (low K, structured, certified)  ──►  digest space (high K, flat, consensus)
    seeds, anchors, exponents, masks, foldings           sha256d outputs, measured hash counts

Shannon is the correct model on the right; Kolmogorov is the correct
model on the left; the architecture is the bridge that keeps the two
ledger-books reconciled without confusing them. The earlier drafts'
error (corrected in `docs/UNIFIED_HYBA_MANIFOLD_DEVICE.md`) was to read
left-side structure as right-side advantage; the AIT reading removes the
temptation by making the conservation law explicit.

---

## 10. Module map — every claim pinned to code

| Manifest concept | Implementation | Key symbols |
|---|---|---|
| Canonical substrate | `turing_core.py` | `fibonacci`, `lucas`, `binet_*`, `cassini_check`, `q_matrix_power`, `zeckendorf_*`, `FAMILY_*`, `t_phi_fold`, `extended_nonce_schedule`, `PythiaMiningEngine`, `hash_meets_target`, `run_self_verification` |
| 11D golden manifold | `Intelligence/poincare_golden_11d.py` | `PHI_POWERS`, `compute_poincare_norm_sq`, `poincare_golden_distance`, `fold/unfold_poincare_11d_vector`, `PoincareFoldedArray`, `compute_zeckendorf_certificate`, `resolve_zeckendorf_slot` |
| Manifold↔standard-ball isometry | `pythagoras/asi/manifold_bridge.py` | `standardize`, `mobius_add`, `exp_map`, `log_map`, `geodesic_descent` |
| 32-face compass + geodesic search | `Intelligence/poincare_cassini_search.py` | `DodecaIcosahedron32`, `PoincareCassiniSearch`, `anchor_of`, `_segment_anchor_crossings`, `_repair_node` |
| Coverage-complete nonce order | `Intelligence/search_crystal.py` | `partition_interval`, `cassini_permutation`, `PoincareCassiniSearchEngine` |
| Unified device (composes all) | `Intelligence/unified_manifold_device.py` | `UnifiedManifoldHashingDevice`, `CLAIM_BOUNDARY`, `ManifoldFoldRecord`, `ManifoldShardOrder` |
| Zeckendorf storage codec | `Intelligence/hardened_unified_substrate.py` | `HardenedZeckendorfCodec`, `SparseTopology`, `apply_zeckendorf_compression`, `reverse_zeckendorf_expansion`, `CassiniVerifier` |
| Prime-exponent substrate | `Intelligence/hardened_unified_substrate.py`, `Intelligence/prime_memory.py` | `GaloisPrimeSubstrate` (`MODULUS_Q = 2⁶¹−1`), `PrimeMemory`, `ExponentialPrimeStore`, `PrimeStorageManifold`, `SelfHealingSubstrate` |
| Folded-state execution | `Intelligence/folded_state.py` | `ExactFoldedStateEngine`, `folded_modular_dot`, `iter_original_u8` |
| Lucas attractor + scales | `Intelligence/lucas_attractor.py`, `Intelligence/lucas_scales.py` | `LUCAS_SCALE_LADDER`, `drift`, `multiscale_coherence_probe` |
| Four-layer pipeline | `Intelligence/four_layer_stack.py` | `AethelStore`, `TensorFoldEngine`, `TuringLayer`, `NearStateIGpu` |
| Score→filter→grind | `mining/hash_pipeline.py` | `HashPipeline`, `score_nonces` (punch `0x1A`), `grind` |
| GPU mirror | `kernels/unified_punch_kernel.cl`, `Intelligence/unified_punch.py` | `PUNCH_IDS` (`poincare_fold 0x08` … `zeckendorf_decode 0x1C`) |
| M-theory exact layer | `mtheory/` | `KKTower`, `FIVE_LIMITS`, `QuantumRegister` (C²⁰⁴⁸ over Q(i,√2)) |
| Flat-space baseline | `mining/entropy_optimizer.py` | `EntropyOptimizer._shannon_entropy` |
| Honesty apparatus | `tests/test_folded_algebra_honesty.py`, `tests/test_povm_boundary_honesty.py`, `tests/test_lucas_exponential_scaling_honesty.py`, `tests/test_unified_manifold_device.py` | falsification tests, `truth_class`, `claim_boundary`, `faces_pruned == 0` |

---

## 11. Formal summary

**Definitions.** A *generator expansion* is a pair `(g, s)` with `g`
fixed code and `s` a seed, emitting object `x = g(s)`; a *certificate* is
a predicate `c(x)` evaluable in O(1) independent of `|x|`; a *two-part
encoding* stores `(model, residue)` with regeneration `x =
model(residue)`.

**Proposition 1 (coverage).** `cassini_permutation(width, face, seed)`
with `gcd(stride, width) = 1` is a bijection on `Z/width`; composed with
`partition_interval` and round-robin interleave, `iter_nonces()` is a
complete permutation of the interval. *Proof in code:*
`search_crystal.py:210–216`; asserted by the partition invariant at line
185 and `faces_pruned == 0`.

**Proposition 2 (reversibility).** Zeckendorf encode/decode is bijective
(Zeckendorf's theorem); `t_phi_fold` is bijective (`det M₁₅ = −1` in
GL(2, Z/256Z)); `fold_poincare_11d_vector` is bijective ℝ¹¹ → 𝔹_φ¹¹.
*Proof in code:* `turing_core.py:409–463`, `run_self_verification` §3b,
`poincare_golden_11d.py:210–265`.

**Proposition 3 (certificate asymmetry).** Cassini `det = (−1)ⁿ`,
non-adjacency `mask & (mask<<1) == 0`, and `sha256` digests verify
regenerated objects in O(1) — strictly cheaper than regeneration, which
is O(log n) (fast doubling / Binet) or O(|residue|) (exponent decode).
*Boundary:* necessary conditions only — falsification test at
`test_folded_algebra_honesty.py:107`.

**Proposition 4 (conservation).** For every pipeline stage,
`K(output) ≤ K(input) + O(1)`; in particular the digest stage is a
conjectured PRF image, so structure does not transfer to acceptance
probability. `hashes_computed` is measured, `truth_class` never exceeds
evidence, `theorem_proven = False`. *This is the physical bound, stated
inside the mathematics.*

**Corollary (the manifest's title-claim, made exact).** The substrate
achieves exponential *addressing and regeneration* — program length
logarithmic in space size, certificates constant — while conservation of
`K` and of physical work bounds every expansion to a reordering of real
computation. Shannon models the flat statistical face of the system
(the digest side); the topology is its Kolmogorov face (the generator
side); Cassini, Binet, and Lucas are the constant-length invariants that
make the generator side self-certifying.

---

*Drafted against the live tree: `turing_core.py`, `Intelligence/`,
`mining/`, `kernels/`, `mtheory/`, `lucas/`, `pythagoras/`, `tests/`.
Supersedes no prior document; consistent with
`docs/UNIFIED_HYBA_MANIFOLD_DEVICE.md` §0 claim boundary.*
