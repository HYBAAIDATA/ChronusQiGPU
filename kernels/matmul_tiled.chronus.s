; Chronus-1 hand-written 2x2 local-memory tiled float32 matmul.
; A @ global 0, B @ global 64, C @ global 128. Dispatch global/local = 2,2,1.
GET_GID R1, 0       ; column
GET_GID R2, 1       ; row
GET_LID R3, 0
GET_LID R4, 1
MOVI R5, 2          ; N/K
MOVI R6, 4          ; sizeof(float)
MOVI R7, 64         ; B base
MOVI R8, 128        ; C base
MOVI R14, 1
; local flat index = local_row*2 + local_col
MUL R10, R4, R5
ADD R10, R10, R3
MUL R10, R10, R6
; A global index = row*2 + col
MUL R11, R2, R5
ADD R11, R11, R1
MUL R11, R11, R6
LOAD R12, [R11+0]
LSTORE R12, [R10+0]
; B uses same 2x2 lane coordinates
ADD R11, R11, R7
LOAD R12, [R11+0]
LSTORE R12, [R10+32] ; B tile at local offset 32
BARRIER 1
MOVI R9, 0          ; float accumulator +0
MOVI R13, 0         ; k
MOVI R15, 2         ; loop count
loop:
MUL R16, R4, R5
ADD R16, R16, R13
MUL R16, R16, R6
LLOAD R17, [R16+0]
MUL R18, R13, R5
ADD R18, R18, R3
MUL R18, R18, R6
LLOAD R19, [R18+32]
FMA R9, R17, R19, R9
ADD R13, R13, R14
SUB R15, R15, R14
BRANZ R15, loop
MUL R20, R2, R5
ADD R20, R20, R1
MUL R20, R20, R6
ADD R20, R20, R8
STORE R9, [R20+0]
EXIT
