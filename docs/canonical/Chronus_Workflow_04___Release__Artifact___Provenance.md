# Chronus Workflow 04 — Release, Artifact & Provenance

## Release chain

source commit → clean build → tests/evidence gates → versioned package/container → immutable digest → SBOM/dependency manifest → benchmark exact artifact → signed provenance → approval → publish/deploy.

## Required provenance

Repository SHA/branch/dirty state; build environment; package/container version and digest; compiler/runtime dependencies; workload manifest; input hashes; backend/device certificate; test and benchmark evidence; policy/security profile; claim states; owner approvals; rollback artifact.

## Rules

No editable install as final release evidence. No re-tagging immutable releases. Do not benchmark one artifact and ship another. Preserve evidence hashes and replay commands. Failed release attempts remain traceable.

**Build once / deploy exact artifact.** The release artifact or container digest produced by the approved clean build becomes the deployment identity. Do not rebuild the release separately for M3, Azure, a GPU node, or another target. Every environment must install or deploy the exact approved artifact digest and record that digest in its evidence.

**Certification is substrate-specific and non-transferable.** An Apple M3 may be used as an independent release host for clean-build, installed-artifact, ARM64/CPU/reference, restart/recovery and genuine Metal certification. M3/Metal evidence certifies only that Apple/Metal execution path. It must never be promoted to CUDA, ROCm, OpenCL, Azure GPU, generic GPU, ASIC or QPU evidence.

**Production substrate certification occurs where production runs.** Azure staging/production must certify the same immutable artifact against the actual HYBA GPU service and physical runtime substrate, recording device identity, driver/runtime, backend dispatch, execution receipt, independent result verification, recovery and provenance. Hardware presence alone is not hardware-execution evidence.

## Owner gate

Changes to release-signing, provenance or production-promotion policy require explicit owner approval.