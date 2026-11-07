# QiGPU, Chronus, Theseus and Ovid: unified scale–fold–store system

This document maps the four named subsystems onto the maintained source tree and records what each one executes today.

## Chronus — the QiGPU compute engine

`src/chronus/execution/` is the execution substrate. `qigpu.py` inventories execution surfaces: the CPU substrate (`python-math-reference`) is always present, and a client-provisioned accelerator surface (`opencl-pv`) registers only when `CHRONUS_ENABLE_OPENCL_PV=1` is set, an OpenCL GPU is detected, and its startup known-answer test passes. When the client prefers their own GPU, the QiGPU routes `PV_LATTICE_FOLD` onto that instance's silicon via SoA integer-lattice buffers. When no client GPU is provisioned, the QiGPU operates on the CPU — the mathematics is the substrate and the hardware is interchangeable. `QiGPUOrchestrator.resolve()` fails closed on an unknown or unsupported surface. The `/health` endpoint publishes the live surface inventory.

Lucas/PV scaling is delivered two ways:

- `LUCAS_PV_SCALING` and `PV_LATTICE_FOLD` materialize exact integer results (fast doubling; arbitrary-precision host reference).
- `TRINITY_SCALE_FOLD_STORE` advances a PV scale index over Zeckendorf-folded seeds, so successive scaling composes without expanding coefficients.

## Ovid — content-addressed storage and receipts

`src/chronus/security/ovid.py` provides the content-addressed object store: every payload's address is its SHA-256 digest, and Ed25519 receipts bind to those digests. Storage and signing keys are process-local; they are not durable across restart.

## Theseus — phyllotaxis storage and reconstruction

`src/chronus/storage/` ports the legacy Theseus role into the maintained tree:

- `phyllotaxis.py` implements golden-ratio distribution: the Knuth multiplicative constant `floor(2**64 * (phi - 1))` maps each content digest onto one of 32 storage lanes, and the Vogel golden-turn model assigns every stored record a deterministic spiral coordinate (`sequence`, exact rational golden-turn fraction, lane).
- `theseus.py` stores payloads as OVID objects, assigns phyllotaxis coordinates, supports per-tenant queries, and reconstructs payloads with fail-closed digest verification. Identical content stored twice by one tenant is deduplicated to one address.

Two native workloads expose this over the authenticated API: `PHYLOTAXIS_STORE` (`{"data": "base64:..."}`) and `THESEUS_RETRIEVE` (`{"object_id": "..."}`). `TRINITY_SCALE_FOLD_STORE` accepts `"store": true` to persist the folded state through Theseus, returning its record; the state can then be scaled further from storage.

## The closed loop

Scale (Lucas/PV index) → Fold (Zeckendorf canonical form) → Store (Ovid content address on a phyllotaxis lane) → Retrieve (Theseus digest-verified reconstruction) → Scale again. Every stage is exact integer arithmetic with no floating-point truncation anywhere in the path.

## Verified status

107 tests pass locally, including golden-lane distribution uniformity, golden-turn coordinate exactness, tenant isolation, tamper detection, and the API round trip. The QiGPU accelerator surface is exercised on a CPU OpenCL runtime only; physical client-GPU validation requires provisioned hardware.
