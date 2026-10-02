; Fixed 32x32 float32 tiled matmul. A=0x100000 B=0x200000 C=0x300000.
; Global=(32,32,1), local=(16,16,1), As local[0,1024), Bs local[1024,2048).
.section .text
.global matmul_tiled
.symbol matmul_tiled
.reconv k_branch, k_done
.reconv tile_branch, tile_done
matmul_tiled:
    GET_LID R1, 0
    GET_LID R2, 1
    GET_GID R3, 0
    GET_GID R4, 1
    MOVI R5, 0
    MOVI R6, 0
    MOVI R7, 4
    MOVI R9, 16
    MOVI R11, 32
    MOVI R12, 256
    MOVI R14, 4096
    MUL R14, R14, R12
    ADD R24, R14, R14
    ADD R30, R24, R14
    MOVI R16, 1024
    MOVI R22, 1
    MOVI R29, 2
tile_loop:
    MUL R8, R2, R9
    ADD R8, R8, R1
    MUL R8, R8, R7
    MUL R10, R4, R11
    MUL R12, R6, R9
    ADD R10, R10, R12
    ADD R10, R10, R1
    MUL R10, R10, R7
    ADD R10, R10, R14
    LOAD R15, [R10+0]
    LSTORE R15, [R8+0]
    MUL R10, R6, R9
    ADD R10, R10, R2
    MUL R10, R10, R11
    ADD R10, R10, R3
    MUL R10, R10, R7
    ADD R10, R10, R24
    LOAD R15, [R10+0]
    ADD R8, R8, R16
    LSTORE R15, [R8+0]
    BARRIER 1
    MOVI R17, 0
    MOVI R28, 16
k_loop:
    MUL R18, R2, R9
    ADD R18, R18, R17
    MUL R18, R18, R7
    LLOAD R19, [R18+0]
    MUL R20, R17, R9
    ADD R20, R20, R1
    MUL R20, R20, R7
    ADD R20, R20, R16
    LLOAD R21, [R20+0]
    FMA R5, R19, R21, R5
    ADD R17, R17, R22
    SUB R28, R28, R22
k_branch:
    BRANZ R28, k_loop
k_done:
    BARRIER 1
    ADD R6, R6, R22
    SUB R29, R29, R22
tile_branch:
    BRANZ R29, tile_loop
tile_done:
    MUL R25, R4, R11
    ADD R25, R25, R3
    MUL R25, R25, R7
    ADD R25, R25, R30
    STORE R5, [R25+0]
    EXIT
