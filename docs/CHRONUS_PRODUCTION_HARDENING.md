# Chronus production hardening

This branch hardens Chronus without redefining it as an ordinary GPU or removing
any existing execution capability. Repository execution evidence is the design
authority.

## Delivery contract

Chronus has two first-class delivery modes:

- `embedded`: Chronus runs inside the customer's/container environment.
- `cloud_instance`: a HYBA Chronus instance is deployed in the customer's
  chosen cloud and reached through the verified remote protocol.

There is no automatic cross-fallback between these modes. A placement change
must be explicit.

## Measurement changes

The existing host NumPy tensor benchmark remains intact. A separate physical
Chronus OpenCL tensor measurement now records end-to-end matmul throughput,
including buffer creation/transfers, kernel dispatch, result copy and queue
completion. A measurement is accepted only after independent NumPy numerical
verification.

Measured GFLOPS/TFLOPS are kept in the measurement evidence. Provisioning does
not manufacture or copy performance numbers into an availability record.

## Execution provenance

The baseline may contain both the logical Chronus contract identity and one or
more physical execution devices. Production evidence now binds measured work
to the matching physical device fingerprint when that identity can be proven.
The historical artifact-builder behavior is preserved for existing callers.

## Evidence integrity

Persisted evidence is replay-checked from its canonical payload rather than
being considered valid merely because a `digest` field exists.

## Hardware acceptance

The existing strict hardware gate remains required. The workflow additionally
runs the production Chronus measurement, uploads both evidence files even when
a gate fails, and fails the job at the end if either hardware gate failed.
This improves evidence retention; it does not relax acceptance.

## Current cloud protocol evidence

The existing `remote_opencl_v2` agent advertises and implements `ladder` and
`sha256d` execution. Those paths remain unchanged. General tensor execution is
not claimed as a remote protocol capability until a corresponding verified
wire surface is implemented and tested.

## Capacity-impact rule

No change in this hardening branch intentionally caps, throttles or removes
Chronus capacity. Any future change that can reduce throughput, supported
operations, execution reach or residency must carry an explicit impact note and
measured regression evidence.
