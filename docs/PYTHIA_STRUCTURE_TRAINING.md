# PYTHIA Structural Training — Real Bitcoin Nonce Corpus

## Authority and purpose

PYTHIA owns mining intelligence. This import teaches PYTHIA from observed
Bitcoin mining data; it does not replace the canonical mining executor,
Chronus topology, Stratum path, or SHA256d proof boundary.

The imported workbench bundle contains 200 mainnet winning nonces and reports
that all 200 were locally verified by rebuilding the 80-byte block header,
matching the reported block id, and checking double-SHA256 against the compact
target. The exact imported CSV and analysis report are digest-bound by
`real_nonces_200.manifest.json`.

Independent public-chain spot checks were also performed during import and are
recorded in the manifest. They match the bundle at sampled heights across the
range. This is not described as a second full 200-row re-verification because
the packaged CSV does not contain the headers/hashes needed to reproduce that
entire check offline.

## What PYTHIA learns

The corpus is used as **unlabelled structural evidence**.

Each observed nonce becomes a 32-channel structural pattern containing:

- normalized nonce position;
- production `phi_resonance`;
- production `cheap_resonance`;
- phi phase;
- phi^15 proximity;
- bit density and bit-transition density;
- neighbor delta/XOR structure;
- byte-scale position;
- 19 Weyl/Pisot phase channels.

The newest 20% of block-height observations are held out and never inserted
into PYTHIA memory. Training therefore uses 160 rows and retains 40 rows for a
blind structural generalization check.

A deterministic uniform-uint32 null set of the same holdout size is evaluated
through the same feature map. The resulting similarity delta is descriptive;
it is not a PoW advantage claim.

## Why this is not discrimination

The imported analysis records 122/200 observations with `R_phi >= 0.5`, while
its uniform-uint32 baseline is about 61.8%. The point of this integration is
not to train a winner/non-winner classifier. The structure corpus is
positive-only and therefore no mining-success/failure label is manufactured.

This matters because the historical `PythiaLearning.learning_step()` defaults
an omitted outcome to `False`. The structure-training adapter does not call
that supervised outcome path. It uses PYTHIA's existing synaptic plasticity,
short-term memory, golden folding, Zeckendorf storage and consolidation
machinery while leaving `_evidence` and `_totals` unchanged.

Real pool outcomes remain a separate feedback channel.

## Truth boundary

Training may influence learned representation and search ordering only.

It must never:

- bypass or weaken SHA256d;
- mark a nonce valid because of resonance;
- convert `R_phi >= 0.5` into a proof predicate;
- fabricate accepted shares;
- claim measured hashrate from a structural score;
- treat a synthetic/null record as a real observation.

The production proof chain remains:

`candidate ordering -> construct header -> SHA256d -> target check -> submit -> pool acknowledgement`

## Files

- `artifacts/pythia_training/real_nonces_200.csv`
- `artifacts/pythia_training/real_nonce_analysis_200_fresh.json`
- `artifacts/pythia_training/real_nonces_200.manifest.json`
- `Intelligence/mining_structure_training.py`
- `scripts/train_pythia_structure.py`
- `tests/test_pythia_structure_training.py`

## Execute

```bash
python scripts/train_pythia_structure.py
```

Use an isolated store in tests or experiments:

```bash
python scripts/train_pythia_structure.py --store-dir /tmp/pythia-structure-store
```

The command journals the training event and persists through the existing
`PythiaStore`. Re-running the same corpus is idempotent: stable corpus/height/
nonce pattern IDs prevent duplicate long-term insertion.

## Evidence still separate

This change proves a source-level and executable training path. It does not,
by itself, prove a mining advantage, live-pool acceptance, hardware hashrate,
or physical-QPU behavior. Those claims require their own runtime evidence.
