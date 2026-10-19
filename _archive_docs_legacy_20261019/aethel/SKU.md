# Chronus · Theseus · Ovid — production SKUs

## Canonical triad (STABLE)

| Owner | Module | Role |
| --- | --- | --- |
| **Chronus** | `chronus` package, `aethel.chronus`, `aethel.device.ChronusSku` | iGPU offering — measured device bind, punch ISA, virtual iGPU ABI |
| **Theseus** | `aethel.theseus` | Self-healing prime-manifold storage — Galois prime keys, Cassini anchors, sunflower phyllotaxis packing, digest heal |
| **Ovid** | `aethel.ovid` | Metamorphosis — **fold = working form**; unfold is egress only |

**Façade:** `aethel.triad.open_triad(durable=True, bind_chronus=True)`

```python
from aethel import open_triad

db = open_triad(durable=True, bind_chronus=False)
rec = db.put(b"payload", durable=True)
assert db.get(rec.uuid) == b"payload"
form = db.fold(b"payload")          # working form
assert db.materialise(form) == b"payload"
print(db.health())
```

## Provisional adapters (consume the triad)

| Adapter | Module | Notes |
| --- | --- | --- |
| Mining/Chronus SKU | `aethel.device.ChronusSku` | Storage + manifold ride with Chronus |
| Hyperscaler SKU | `aethel.hyperscaler.HyperscalerSku` | Provisional; see `capabilities.json` |

## Non-claims (all SKUs)

- Not infinite capacity / zero physical footprint
- Not a hash preimage oracle or cryptographic collapse
- Not zero-energy compute
- Geodesic **search** is handoff-only — not reimplemented inside Theseus
- Chronus does not bypass untuned double-SHA256 targets

## Readiness

`capabilities.json` marks the **software storage triad** production-ready.
Hardware soak, discrete-GPU fleet, and full hyperscaler deploy remain separately gated.

## Enterprise migration (HYBA Intelligence)

Mining is the first proof ground. Capabilities required by the enterprise brief
are catalogued under Rule 7 in:

- `docs/ENTERPRISE_CAPABILITY_BRIDGE.md`
- `aethel.enterprise_bridge.report()` / `python -m aethel enterprise-report`

**Migrate now (READY):** fold working form, prime/phyllotaxis store, self-heal,
Chronus software bind, geodesic handoff, claim boundaries.

**Do not claim from this repo:** Solutions API 18 endpoints, clinical MRI,
Clay conjecture resolutions, 10-service commercial latency tables, near-state
10k-qubit rooflines.
