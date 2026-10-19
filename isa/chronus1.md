# Chronus-1 ISA v1.0

**Status:** normative emulator/assembler contract. This is a virtual ISA; it does not claim Intel silicon implements these opcodes.

## 1. Execution model

- 32-lane warp, little-endian, fixed 32-bit instructions.
- Four implementation-default compute units; binaries do not encode a CU count.
- Per lane: `R0..R31`, each an untyped 32-bit word. `R0` reads zero and discards writes. `SP` is the architectural alias of `R31`.
- Per warp: `P0..P3` predicate masks, an implicit 32-bit `PC`, active-lane mask, and divergence stack.
- Integer arithmetic is two's-complement modulo 2^32. `FMA` reinterprets operands/results as IEEE-754 binary32 and performs one fused rounding using round-to-nearest, ties-to-even.
- Work-items outside the requested global size start inactive and never participate in barriers.

## 2. Encoding

Every instruction is one little-endian 32-bit word. Bits are numbered 31 (MSB) to 0 (LSB).

| Format | Bits 31:26 | 25:21 | 20:16 | 15:11 | 10:6 | 5:0 |
|---|---|---|---|---|---|---|
| R | opcode | rd | rs1 | rs2 | aux | flags |
| I | opcode | rd | rs1 | imm16 (15:0) |||
| M | opcode | data | base | imm16 (15:0) |||
| B | opcode | selector | signed word offset21 (20:0) ||||
| S | opcode | rd | selector | imm16 (15:0) |||

- Signed immediates are two's-complement and sign-extended.
- Branch target is `PC + 4 + (sign_extend(offset21) << 2)`.
- Reserved bits must be zero. Decoders must reject non-zero reserved bits.
- Register fields outside `0..31`, predicates outside `P0..P3`, dimensions outside `0..2`, unknown opcodes and misaligned branch targets trap.

## 3. Opcode table

| Op | Hex | Format | Assembly | Exact effect for every active lane |
|---|---:|---|---|---|
| NOP | 00 | R | `NOP` | No state change except `PC += 4`. |
| MOV | 01 | R | `MOV rd, rs1` | `rd = rs1`. |
| MOVI | 02 | I | `MOVI rd, imm16` | `rd = sign_extend(imm16)`. |
| ADD | 03 | R | `ADD rd, rs1, rs2` | `rd = (rs1 + rs2) mod 2^32`. |
| SUB | 04 | R | `SUB rd, rs1, rs2` | `rd = (rs1 - rs2) mod 2^32`. |
| MUL | 05 | R | `MUL rd, rs1, rs2` | Low 32 bits of unsigned product. |
| FMA | 06 | R | `FMA rd, rs1, rs2, rs3` | `rd = binary32_fma(rs1, rs2, rs3)`; `aux=rs3`. |
| LOAD | 08 | I | `LOAD rd, [rs1+imm16]` | Load 4 little-endian bytes from global address. Address must be 4-byte aligned and in range. |
| STORE | 09 | M | `STORE rs, [base+imm16]` | Store 4 little-endian bytes to global memory. |
| LLOAD | 0A | I | `LLOAD rd, [rs1+imm16]` | Load one aligned word from the work-group's CU-local allocation. |
| LSTORE | 0B | M | `LSTORE rs, [base+imm16]` | Store one aligned word to CU-local memory. |
| BARRIER | 0C | S | `BARRIER scope` | Arrive/wait barrier plus fence described below; `selector=scope`. |
| BRA | 10 | B | `BRA label` | All active lanes branch by `offset21`. |
| BRAZ | 11 | B | `BRAZ rs, label` | Lanes where `rs==0` take the branch; others fall through. |
| BRANZ | 12 | B | `BRANZ rs, label` | Lanes where `rs!=0` take the branch; others fall through. |
| GET_GID | 18 | S | `GET_GID rd, dim` | Global work-item ID in dimension `dim`. |
| GET_LID | 19 | S | `GET_LID rd, dim` | Local work-item ID. |
| GET_GSIZE | 1A | S | `GET_GSIZE rd, dim` | Requested, unpadded global size. |
| GET_LSIZE | 1B | S | `GET_LSIZE rd, dim` | Local work-group size. |
| EXIT | 3F | R | `EXIT` | Retire active lanes. Work-group completes when all lanes retire. |

Opcodes `07`, `0D..0F`, `13..17`, and `1C..3E` are reserved. Executing them traps; implementations must not treat them as `NOP`.

## 4. Address spaces

### Global

- Flat unsigned 32-bit byte address space: `0x00000000..0xffffffff` (4 GiB architectural maximum).
- Implementations may expose less committed memory. Access outside the committed range traps.
- Naturally aligned 32-bit loads/stores only in v1.
- Distinct work-items may race; v1 defines no atomics. A data race has unspecified winner but may not escape bounds or corrupt runtime metadata.

### Local

- Up to 65,536 bytes per CU, allocated per resident work-group and zeroed before dispatch.
- Visible only to work-items in that work-group.
- Lifetime ends when the work-group completes.
- `LLOAD/LSTORE` outside the allocated work-group region trap.

### Private

Registers are lane-private. `SP/R31` is conventional private-stack state; v1 provides no implicit stack memory operations.

## 5. Divergence and reconvergence

`BRAZ` and `BRANZ` evaluate the source register independently per active lane.

1. If all active lanes agree, update `PC` without pushing state.
2. If masks differ, push `(reconverge_pc, deferred_pc, deferred_mask)`.
3. Execute the taken mask first, then the fall-through mask.
4. Reconverge when both paths reach the immediate post-dominator selected by the assembler/compiler.

The binary v1 encoding has no reconvergence token. For structured code, the assembler emits branch metadata in the `.chronus` symbol record. A raw binary without metadata uses the conservative fall-through `PC+4` as its reconvergence point. Divergence-stack overflow traps; minimum required depth is 32.

## 6. Barrier and memory fence

`BARRIER` scope values:

| scope | Meaning |
|---:|---|
| 0 | Work-group execution barrier only. |
| 1 | Work-group barrier plus local-memory release/acquire fence. |
| 2 | Work-group barrier plus global-memory release/acquire fence. |
| 3 | Both local and global fences. |

Semantics:

- An executing warp marks its active, non-retired lanes as arrived and stalls.
- The barrier releases only when every non-retired work-item in the work-group has arrived at the same static barrier instance.
- A work-item exiting while peers can still reach a barrier is an invalid program and traps the work-group.
- Barriers across divergent paths are invalid unless every non-retired work-item reaches the same instance.
- Release completes prior stores in the named scope; acquire prevents later loads from being observed before release.
- Barriers do not synchronize different work-groups.

These rules remove ambiguity around partial final work-groups: padded inactive lanes are not participants.

## 7. Dispatch built-ins

Dimensions are `0=x`, `1=y`, `2=z`. A dispatch supplies three-component global and local sizes. Missing dimensions are encoded as size one. `GET_GID` returns `group_id[dim] * local_size[dim] + local_id[dim]`. Out-of-range padded lanes are inactive before instruction zero.

## 8. Traps and fail-closed behavior

The emulator/runtime must stop the affected dispatch and return evidence for:

- illegal or reserved opcode;
- malformed reserved fields;
- unaligned/out-of-range memory access;
- invalid dimension/predicate/scope;
- divergence-stack overflow;
- barrier deadlock or invalid early exit;
- instruction budget exhaustion;
- binary checksum/version failure.

No trap may silently fall back to host execution.

| Trap | Required condition |
|---|---|
| `IllegalOpcode` | Reserved/unknown opcode. |
| `MalformedEncoding` | Non-zero reserved instruction field. |
| `Misaligned` | Unaligned instruction or 32-bit memory access. |
| `OutOfBounds` | PC or effective address outside committed memory, including address wrap. |
| `InvalidSelector` | Invalid predicate, barrier scope, dimension, or dispatch shape. |
| `DivergenceOverflow` | More than 32 unresolved divergent branches. |
| `BarrierDeadlock` | Live work-items wait at different barrier instances or cannot progress. |
| `InvalidEarlyExit` | A work-item exits while a peer can still reach a barrier. |
| `BudgetExhausted` | Lane-instruction budget reached before completion. |
| `BinaryFormat` | Invalid magic, version, size, checksum, symbol, metadata, or reconvergence record. |

## 9. Expressibility of tiled matrix multiplication

A tiled binary uses `GET_GID/GET_LID` for coordinates, integer `MUL/ADD` for addresses and loop counters, `LOAD/LLOAD/LSTORE`, `BARRIER 1`, binary32 `FMA`, `STORE`, `SUB` and `BRANZ`. Bounds are implemented with padded-lane inactivity plus guarded zero loads generated by structured branch metadata. Therefore the canonical tiled float32 matmul kernel is expressible without an unspecified instruction.

## 10. `.chronus` binary container

The v1 header is 32 little-endian bytes: `CHRN` magic; `major:u16`; `minor:u16`; `flags:u32`; `entry:u32`; `code_words:u32`; `required_global_bytes:u32`; `code_crc32:u32`; `metadata_bytes:u32`. Raw instruction words immediately follow. Version 1 requires `metadata_bytes=0`. CRC32 uses polynomial `0xEDB88320` over code bytes only. Size, checksum, entry alignment, major version, and committed-memory requirements are validated before dispatch; violation traps.

## 11. Version and compatibility

ISA identifier: `chronus1`. Version: `1.0`. A runtime must reject a binary with a different major version. A newer minor version may run only when every used opcode/feature is declared compatible.
