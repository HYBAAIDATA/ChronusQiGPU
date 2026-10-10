# Fixture provenance

`zeckendorf_certificate.json` — genuine producer output, bytes committed verbatim.

- **Producer**: `toe/poincare_golden_11d.py :: compute_zeckendorf_certificate`
- **Invocation**: `compute_zeckendorf_certificate(np.linspace(-0.5, 0.5, 11), context_id="pythia-consumer-e2e-v1")`
- **Serialization**: `ZeckendorfCertificate.to_dict()` → `json.dumps(indent=1, sort_keys=True)`
- **Artifact sha256**: `150ec7d58ef7c740757db58f1310f7ac0db39e59027817cda91b05a3d231716c`
- **Deterministic**: yes — fixed input vector and context bind the φ¹⁵ lattice
  quantization, Zeckendorf masks, and 64-bit canonical accumulator.

## Producer → verifier contract

Verifier checks `token_hex` form and `non_adjacent_mask` non-adjacency —
the same predicate as the producer's `ZeckendorfCertificate.is_valid`.
Fields the verifier ignores: `canonical_int`, `coordinate_masks`,
`slot_address`, `context_id`, `truth_class`, `is_valid`, `active_dimensions`.
This is structural verification only; it does not authenticate the producer.
