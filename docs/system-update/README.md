# Chronus System Update Pack

**v36.0.0 · implementation-grounded product and engineering brief**

## Executive position

Chronus is a mathematics-first, representation-aware computational substrate. Its distinctive premise is to act on mathematical structure—particularly Lucas/Pisot–Vijayaraghavan and exact \(Q(\sqrt5)\) representations—and to make execution independent of any single accelerator vendor. QiGPU is intended to run workloads on Chronus itself or extend them into client- and fleet-side accelerators.

The current checkout now provides a working, tested native mathematical reference path, an execution-backend contract, a tenant-aware HTTP service, a Python SDK, and single-node persistent workload records. It does **not** yet contain a registered physical GPU adapter or a distributed deployment platform. This distinction preserves the product thesis while making the external claims match the code.

The commercial intent is Dubai/DIFC headquarters, London go-to-market, and a global customer base that includes sovereign clients in the GCC. These are the stated operating and market ambitions; they are not evidence of deployed offices, signed clients, certifications, or customer-specific hardware integrations.

## Pack contents

- [Architecture and market model](architecture-and-market.md) — product premise, execution model, commercial footprint, and capability boundaries.
- [Current-state assessment](current-state-assessment.md) — implementation status and material gaps, based on the code and tests.
- [Test evidence](test-evidence.md) — commands, observed outcomes, and explicit limits of the current validation.
- [Azure deployment foundation](azure-deployment.md) — provisioning template, CI checks, and operational limits.
- [Native search and accelerator integrity](mining-and-accelerators.md) — 32-lane software search and exact accelerator-boundary semantics.
- [Governance and acceptance](governance-and-acceptance.md) — evidence and release controls for further market-readiness work.

The former roadmap-first document has been removed. This pack documents the system that is implemented, its market intent, and the next proof required to expand the system safely; it is not a substitute for shipping the remaining accelerator and production-platform capabilities.
