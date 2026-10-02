# Chronus evidence-gated evolution

The evolution loop is bounded and fail closed. It may prepare a candidate change, but a candidate survives only when both its gap-specific acceptance checks and the configured evidence gate pass. Missing hardware or a missing gate is a failed gate, never a synthetic pass.

Priority: ISA → emulator → assembler/disassembler → subset compiler → conformance suite → cross-backend verification → Vulkan → certified operations → FPGA → LLVM.

The conformance suite precedes cross-verification because cross-verification consumes the suite. This is the only dependency correction to the supplied pseudocode.

`META_EVOLVE` may write priority recommendations to evidence history. It may not silently rewrite safety policy, verification authority, cryptographic boundaries, production keys, or approval classes. Such changes require review.

Iterations closed: `ISA_DEFINITION` and `EMULATOR`. The reference C++17 emulator executes all 20 opcodes, the `.chronus` container, traps, divergence, barriers, partial work-groups and the hand-written local-memory tiled matmul. The next open gap is the assembler/disassembler. The UHD 620 physical gate remains external evidence and must be rerun on the target host before this iteration may be merged as physically regression-safe.
