# Chronus GPU capability closure

This review checked the July GPU requirements against the active Chronus branch
and the Kellogg convergence work.

| Capability | Before this closure | Result |
|---|---|---|
| Geodesic scheduling | Present in `chronus.phi_gpu` | Retained and publicly exported |
| Memory hierarchy | Present in `chronus.v33.memory`; fold tiers in Aethel | Added evidence-labelled physical hierarchy profile |
| GPU topology/specs | Historical reference and basic device census present | Added runtime topology probe, links, fingerprint, and explicit unknown fields |
| Integrity gates | Fold integrity existed in Aethel | Added digest/HMAC GPU-buffer attestation with replay protection |
| Tensor-network decomposition | MPS/TEBD present in v3.3 | Added Chronus adapter to Kellogg MPS and TT |
| MPS/TT/MPO operations | MPS present; TT/MPO absent from Chronus public surface | Added public Kellogg-backed pipeline and guarded device MPO execution |
| Compression | MPS and phi-fold paths present | Added TT error-budget adapter |
| Serialization | Missing from Chronus | Added safe Kellogg persistence adapter; no pickle |
| Invariant verification | Partial MPS structure reporting | Added finite/bond/norm/canonicality/entropy verifier |

## Ownership

Chronus owns probing, scheduling, transfer, hardware execution, and execution
evidence. Kellogg owns MPS, TT, MPO, compression mathematics, and artifact
format. Aethel owns fold custody and fold-tier memory. The adapter composes these
owners instead of duplicating implementations.

## Evidence rules

- OpenCL properties are measured only when the device object reports them.
- Generic OpenCL does not expose tensor-core count, PCIe bandwidth, or NVLink;
  these remain null rather than being guessed.
- July vendor tables remain dated historical references, never Chronus
  measurements.
- Host execution is labelled `kellogg-host` and never presented as GPU work.
- Device MPO execution is fail-closed and compared against Kellogg before it is
  accepted.
- Representation ratios are not physical compression or bandwidth evidence.

## Safety corrections

The serialization example in the supplied text used `pickle`. Chronus does not
vendor that unsafe behavior. It delegates to Kellogg's checksummed, optionally
HMAC-authenticated, no-pickle `.pv` format.
