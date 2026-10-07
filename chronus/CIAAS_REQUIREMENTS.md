# HYBA | Chronus CIaaS integration requirements

Canonical shared record: [three-plane session audit](../docs/CIAAS_THREE_PLANE_SESSION_AUDIT.md).

Chronus owns the software-defined GPU execution boundary and optional host-accelerator augmentation; it is not a second Tensor or VQC engine. A physical GPU is not required for native Chronus. Implement C03/C05-C07/C11-C16 across the execution boundary: representation-native kernels, GPUDirect where supported by an attached host GPU, distributed execution, measured tiers, pre-distance ABAC, offline deployment, counters and allocations, certified precision and hardware-aware scaling. Consume logical contracts from Tensor and valid mathematical programs from Turing.

Shared responsibilities C02/C04/C08-C10/C17-C19: transport validated folded/metric/state representations, execute admitted operations, preserve generation/precision and emit evidence. C01 codecs are logically owned by Tensor/Kellogg; Chronus implements their real kernels. C20-C22 are integrated commercial/handoff/measurement requirements, not duplicated hardware features.

Priority defects: dispatch validation must precede input conversion/allocation; dimensions must reject booleans/floats. The README migration sentence contradicts its canonical namespace. Fix with regression evidence. No certified FP64 path is inferred from an extension flag.

This file records requirements and audit gaps, not implemented feature status or physical test results. Preserve one implementation and integrated delivery; keep enterprise execution independent of BTC-specific adapters.
