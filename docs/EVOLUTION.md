# Chronus evidence-gated evolution

The evolution loop is bounded and fail closed. It may prepare a candidate change, but a candidate survives only when both its gap-specific acceptance checks and the configured evidence gate pass. Missing hardware or a missing gate is a failed gate, never a synthetic pass.

Priority: ISA → emulator → assembler/disassembler → subset compiler → conformance suite → cross-backend verification → mathematical intrinsics → production mining integration → Vulkan → certified operations → FPGA → LLVM.

The conformance suite precedes cross-verification because cross-verification consumes the suite. Production mining integration consumes the immutable #104 corpus, #105 capability states and #106 intrinsics without changing their truth boundaries.

`META_EVOLVE` may write priority recommendations to evidence history. It may not silently rewrite safety policy, verification authority, cryptographic boundaries, production keys, or approval classes. Such changes require review.

Iterations closed by repository evidence before #107: `ISA_DEFINITION` and `EMULATOR`. The reference C++17 emulator executes all 20 opcodes, the `.chronus` container, traps, divergence, barriers, partial work-groups and the hand-written local-memory tiled matmul.

#107 source inspection and implementation are complete. This environment has not executed the repository acceptance chain, focused tests, physical OpenCL, live-pool or CI gates; their machine-readable states remain `NOT_RUN`, `PHYSICAL_EVIDENCE_REQUIRED`, `NOT_RUN` and `NOT_REPORTED` respectively in `artifacts/chronus107-evidence.json`. Float64 remains unsupported, OpenCL `BINET_EXACT` remains unsupported and `FOLDED_NATIVE` remains open. No performance or profitability evidence was obtained.
