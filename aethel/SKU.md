# Two provisional adapters, one canonical substrate

Mining/Chronus adapter: `aethel.device.ChronusSku`
Hyperscaler adapter: `aethel.hyperscaler.HyperscalerSku`

These SKUs consume Aethel storage/encoding. They do not own it. Hardware
availability and observed performance are environment-specific and are not
established by SKU construction or CPU-side unit tests.

Folded form is the working form. Unfold is egress.

## Mining — M1–M4

- M1 supported punch calls are opcodes, not proof that every device implements
  the full `0x08`–`0x1A` range
- M2 batch size is a Lucas/Pisot ladder stop
- M3 every ingest writes Aethel (Fibonacci + Cassini)
- M4 standalone or nested in a host GPU

## Hyperscaler — H1–H5

- H1 `put` stores a `ZeckendorfVector`, not raw bytes
- H2 `working` returns that vector
- H3 every mask is non-adjacent
- H4 unit count snaps on the same ladder
- H5 `egress` unfolds byte-identically

## Shared

Aethel address space. Binet+Zeckendorf fold. Lucas/Pisot scale policy; not a
throughput or acceleration claim.
