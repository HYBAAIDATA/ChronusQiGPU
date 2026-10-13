#pragma once
#include <cstdint>
#include "trap.h"
namespace chronus1 {
enum class Opcode : uint8_t { NOP=0, MOV=1, MOVI=2, ADD=3, SUB=4, MUL=5, FMA=6, LOAD=8, STORE=9, LLOAD=10, LSTORE=11, BARRIER=12, BRA=16, BRAZ=17, BRANZ=18, GET_GID=24, GET_LID=25, GET_GSIZE=26, GET_LSIZE=27, EXIT=63 };
enum class Format { R, I, M, B, S };
struct Decoded { Opcode op; Format format; uint8_t rd{}, rs1{}, rs2{}, aux{}, flags{}; int32_t imm{}; uint8_t selector{}; uint32_t raw{}; };
Decoded decode(uint32_t raw);
uint32_t encode_r(Opcode op,uint8_t rd=0,uint8_t rs1=0,uint8_t rs2=0,uint8_t aux=0,uint8_t flags=0);
uint32_t encode_i(Opcode op,uint8_t rd,uint8_t rs1,int16_t imm);
uint32_t encode_b(Opcode op,uint8_t selector,int32_t word_offset);
uint32_t encode_s(Opcode op,uint8_t rd,uint8_t selector,uint16_t imm=0);
}
