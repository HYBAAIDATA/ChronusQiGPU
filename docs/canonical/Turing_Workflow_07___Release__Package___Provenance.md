# Turing Workflow 07 — Release, Package & Provenance

## Release chain

source → clean build → formal/unit/property/differential tests → package/wheel/container → immutable digest → exact-artifact benchmarks → SBOM/dependency manifest → provenance/evidence bundle → owner gate where required → publish/deploy.

## Required provenance

Turing SHA; build environment; exact package/container digest; compiler/runtime deps; capability/representation manifest; OVID/Theseus/Chronus versions when consumed; test results; benchmark evidence; claim states; replay command; rollback artifact.

## Rule

Do not use editable installation as final release evidence. Do not benchmark one Turing artifact and deploy another. Every integrated HYBA release records the exact Turing version/digest it consumes.