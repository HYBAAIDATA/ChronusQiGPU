# Fixture provenance

`zeckendorf_certificate.json` — genuine producer output, bytes committed verbatim.

- **Producer**: `toe/poincare_golden_11d.py :: compute_zeckendorf_certificate`
- **Invocation**: `compute_zeckendorf_certificate(np.linspace(-0.5, 0.5, 11), context_id="pythia-consumer-e2e-v1")`
- **Serialization**: `ZeckendorfCertificate.to_dict()` → `json.dumps(indent=1, sort_keys=True)`
- **Artifact sha256**: `150ec7d58ef7c740757db58f1310f7ac0db39e59027817cda91b05a3d231716c`
- **Deterministic**: yes — fixed input vector and context bind the φ¹⁵ lattice
  quantization, Zeckendorf masks, and 64-bit canonical accumulator.

## Producer → verifier contract (v2)

Required: `token_hex`, `non_adjacent_mask`, `canonical_int`,
`coordinate_masks` (11 producible masks), `context_id`.
The verifier independently re-derives the canonical accumulator —
`acc = fold((mask_i ^ PRIME_BUCKETS[max_k_i]), *31, mod 2^64)` over 11
coordinates, then a `SHA256(context_id)[:8]` mix when non-empty — and
binds `token_hex == ZECK-{acc:016X}`. Passing proves internal
consistency under the published algorithm.

Ignored fields: `canonical_int` extras, `slot_address`, `truth_class`,
`is_valid`, `active_dimensions`, `max_k`, `prime_mod`, `mask_int`,
`decoupling_mask*`, `token` (checked only for consistency with
`token_hex`), unknown fields.

Canonical binding is not provenance: the fold is public and recomputable
by anyone. Authenticated provenance remains unsupported pending an
asymmetric signature or documented key-distribution trust model.
