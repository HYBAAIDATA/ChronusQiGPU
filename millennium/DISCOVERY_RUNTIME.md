# Millennium Discovery Runtime

`millennium.discovery_runtime` connects the deterministic Millennium probe suite
to the previously disconnected `MathematicalDiscoveryEngine`.

## Run the first Riemann campaign

```bash
python -m millennium.discovery_runtime \
  --problem riemann \
  --scale standard \
  --depth 3 \
  --json artifacts/millennium/riemann_discovery_campaign.json
```

The runtime executes only the selected governed probe, calls
`MillenniumSuite.assert_no_established()`, translates the measured series into
the explorer input schema, runs `deep_mathematical_exploration()`, and emits a
SHA-256-addressed evidence envelope.

## Claim boundary

Every output is **candidate generation only**. The runtime fails closed if a
downstream component sets `proof_claim`, `theorem_proven`, or
`mathematically_complete` to `true`.

A candidate can be promoted only after all of the following exist:

1. An explicit theorem with assumptions, domain, boundary conditions and
   quantifiers.
2. A complete derivation closing the accepted statement—not a bounded numerical
   observation.
3. Formal verification where feasible.
4. Negative controls and reproducible, versioned artifacts.
5. Independent expert review.

## Architecture

```text
MillenniumSuite.run(only=[problem])
        |
        v
MillenniumSuite.assert_no_established()
        |
        v
MathematicalDiscoveryEngine.deep_mathematical_exploration()
        |
        v
CANDIDATE_GENERATION_ONLY evidence envelope
```

The active Bayesian `Intelligence/asi/discovery_engine.py` remains a separate,
test-backed engine for replicated black-box rule-composition experiments. It can
be integrated later as an adversarial replication stage once mathematical
candidate schemas and falsifiers are explicit.
