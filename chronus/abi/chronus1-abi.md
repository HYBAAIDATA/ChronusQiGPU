# Chronus-1 kernel ABI v1

## Invocation

A kernel symbol has `kind=1`. `value` is its entry PC and `size` is its code extent. The host supplies three-component global/local sizes and a committed global-memory image. Arguments are placed in global memory by descriptors; v1 has no hidden host pointers.

## Register state

At entry all writable registers are zero. `R0` is immutable zero. `R31` is the `SP` alias and is initialized to the top of the lane-private stack reservation, aligned to 16 bytes. `PC` is the selected kernel symbol value. Built-ins are read only through `GET_*`.

## Argument descriptors

Each descriptor is 16 bytes: `kind:u8`, `flags:u8`, `reserved:u16=0`, `address:u32`, `size:u32`, `alignment:u32`. Kinds: `0=buffer`, `1=scalar`, `2=local`. Addresses are 32-bit virtual addresses. Invalid bounds/alignment trap before execution.

## Versioning

The ABI major equals the executable major. Unknown major versions fail closed. Minor additions are accepted only when all used flags and record kinds are understood.

## Reconvergence — Option A

Reconvergence is executable-container metadata, not an inferred emulator feature. Every dynamically divergent conditional branch is keyed by branch PC to its immediate post-dominator. Missing, duplicate, unaligned or out-of-code metadata fails closed. The same metadata is consumed by emulator, future FPGA, compiler and differential tools.

## Scheduling

Work-groups are assigned round-robin to four logical CUs. Each CU selects the lowest-index runnable resident warp. Within a warp, the lowest runnable PC is executed first; lane order is ascending for deterministic conflicting stores. This ordering is normative for reference replay but programs with data races remain invalid for conformance.

## Barriers and completion

Barrier participation and traps are defined by `isa/chronus1.md`. Output becomes visible only after all work-groups complete without a trap. A trapped dispatch commits no success evidence.
