# Two SKUs, one substrate

Mining GPU: `aethel.device.IGpuSku`
Hyperscaler: `aethel.hyperscaler.HyperscalerSku`

Folded form is the working form. Unfold is egress.

## Mining — M1–M4

- M1 punch set is the ISA (`0x08`–`0x1A`)
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

Aethel address space. Binet+Zeckendorf fold. Lucas/Pisot clock.
