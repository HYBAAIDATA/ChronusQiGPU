# hyba-pythia-consumer

Consumer surface for the PYTHIA substrate — one installable package exposing
three tabs of the product:

- **Node** — honest hardware/platform census (chip, GPU backends, optional
  dependencies) plus control-API reachability.
- **Verify** — structural verification of substrate receipts: Zeckendorf
  certificates, non-adjacency masks, Cassini ledger rows, Lucas ladder anchors.
- **Intelligence** — pass-through status for a configured CIaaS endpoint
  (`PYTHIA_CIAAS_URL`); reports unavailable honestly when unconfigured.

## Install

```bash
pip install hyba-pythia-consumer          # when published
python build_bundle.py && pip install dist/*.whl   # local build
```

The wheel is a **self-contained bundle**: `build_bundle.py` vendors the
sibling substrate sources (`aethel`/THESEUS, `hyba_db`/OVID,
`chronos_one_igpu`/iGPU) into the wheel because they are not yet published
distributions. Do not co-install this wheel with the singular sibling
wheels — the top-level namespaces would collide.

## Use

```bash
pythia census            # local hardware census (JSON)
pythia verify r.json     # structurally verify a receipt file
pythia console           # serve the three-tab console on http://127.0.0.1:8777
```

## Honest boundaries

- Verification is **structural**: it proves a receipt's internal invariants
  (non-adjacency, Cassini identities, certificate token form). It is not a
  custody or provenance proof.
- The node census reports detected facts only; unavailable hardware and
  backends are reported as such, never stubbed.
- No mining is performed by this package.
