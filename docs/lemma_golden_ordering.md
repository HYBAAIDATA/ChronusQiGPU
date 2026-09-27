# Ordering lemmas — golden stride and φ-resonance probe order

Two bound lemmas govern how the mining substrate orders its nonce
search. The accept predicate is unchanged: sha256d(header|nonce) ≤ target
is the sole authority. Ordering is coverage and sequencing; it asserts
nothing about the hash output.

## Lemma G — golden_stride_bijection

For stride s = floor(2³²/φ) = 2654435769 and modulus m = 2³²:

1. s is odd (s ≡ 1 mod 2).
2. Therefore gcd(s, m) = 1 (m is a power of two; oddness implies
   coprimality).
3. Therefore i ↦ seed + i·s (mod m) is a bijection of Z/mZ: over a full
   2³² cycle every nonce is probed exactly once.

Scope: the nonce domain Z/2³²Z; the device kernel `bitcoin_sha256d_gold`
and the host oracle `emit_sha256d_gold`/`grind_target_gold`.

Not a proof of: any prediction about sha256d output, any speedup beyond
coverage and sequencing, quantum advantage, any Millennium problem.

## Lemma R — phi_resonance_ordering

For a header H and target T, the 12-tier φ-resonance ordering with
Wilson-seeded intra-tier permutation produces a header-dependent
permutation of the nonce window. Header-dependence is verified
empirically on a fixed header set by `verify_resonance_ordering`. The
seed is 64 bits of SHA-256, so distinct orders for arbitrary header
pairs are not guaranteed: headers that share a seed share an order.

Scope: search ordering only (`order_nonce_window_probe_schedules`,
`order_device_probe_walk`).

Not a proof of: any prediction about sha256d output, any speedup beyond
coverage and sequencing, quantum advantage, any Millennium problem.

## Verification record

- The gcd proof is executed in `verify_golden_stride` (two assertions:
  oddness, gcd == 1); the 200k-step uniqueness sweep in
  `tests/test_golden_stride.py` is a cross-check, not the proof.
- The header-dependence check is executed in `verify_resonance_ordering`
  over deterministic vectors: every emitted order is a permutation of
  the window, and distinct headers yield distinct probe orders.
- `use_ordering_lemma(usage, stride)` is the runtime scope guard; a
  non-φ stride or unauthorized usage is a ScopeViolation.

## Signoff (executed checks, not names)

- mathematician — stride bijection: gcd(s, 2³²) = 1
- systems — ordering is a header-dependent permutation of the window
- qi_physicist — no quantum claim is made anywhere in scope

theorem_proven: False — these are verified bounds under the stated
scope, signed off as proof sketches, not proven theorems.
