; Four-lane local-memory sum. All lanes deterministically store the same result.
GET_LID R1, 0
MOVI R2, 4
MUL R3, R1, R2
MOVI R4, 1
ADD R4, R4, R1
LSTORE R4, [R3+0]
BARRIER 1
LLOAD R5, [R0+0]
LLOAD R6, [R0+4]
LLOAD R7, [R0+8]
LLOAD R8, [R0+12]
ADD R9, R5, R6
ADD R9, R9, R7
ADD R9, R9, R8
STORE R9, [R0+0]
EXIT
