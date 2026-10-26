# `l_hras`

L-HRAS (Layered Heuristic Resilient Adversarial Security) is the Guardian
security package. It owns request evaluation, threat modes, attestations,
governance, observability, self-defence and integration boundaries.

## Boundaries

- `guardian.py` is the orchestration facade.
- `types.py` defines public inputs and outputs.
- `config.py` validates runtime configuration.
- `substrates.py` is the only dependency boundary into repository-specific
  mathematical substrates.
- `attestation.py`, `store.py` and `observability.py` own evidence.
- `governance.py`, `selfdefense.py` and `integration.py` own enterprise control
  surfaces.
- `foundations/` contains the reviewed mathematical claim boundaries.

Use the public API exported from `l_hras.__init__`; consumers should not import
implementation modules unless they need a documented extension point.
