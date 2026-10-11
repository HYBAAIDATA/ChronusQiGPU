#include "chronus1/isa.h"
namespace chronus1 {
static int32_t sx(uint32_t v,unsigned bits){uint32_t m=1u<<(bits-1);return int32_t((v^m)-m);}
static Format format_for(Opcode o){switch(o){case Opcode::MOVI:case Opcode::LOAD:case Opcode::LLOAD:return Format::I;case Opcode::STORE:case Opcode::LSTORE:return Format::M;case Opcode::BRA:case Opcode::BRAZ:case Opcode::BRANZ:return Format::B;case Opcode::BARRIER:case Opcode::GET_GID:case Opcode::GET_LID:case Opcode::GET_GSIZE:case Opcode::GET_LSIZE:return Format::S;default:return Format::R;}}
Decoded decode(uint32_t raw){uint8_t value=uint8_t(raw>>26);Opcode op;
switch(value){case 0:op=Opcode::NOP;break;case 1:op=Opcode::MOV;break;case 2:op=Opcode::MOVI;break;case 3:op=Opcode::ADD;break;case 4:op=Opcode::SUB;break;case 5:op=Opcode::MUL;break;case 6:op=Opcode::FMA;break;case 8:op=Opcode::LOAD;break;case 9:op=Opcode::STORE;break;case 10:op=Opcode::LLOAD;break;case 11:op=Opcode::LSTORE;break;case 12:op=Opcode::BARRIER;break;case 16:op=Opcode::BRA;break;case 17:op=Opcode::BRAZ;break;case 18:op=Opcode::BRANZ;break;case 24:op=Opcode::GET_GID;break;case 25:op=Opcode::GET_LID;break;case 26:op=Opcode::GET_GSIZE;break;case 27:op=Opcode::GET_LSIZE;break;case 63:op=Opcode::EXIT;break;default:trap(TrapCode::IllegalOpcode,"reserved Chronus-1 opcode");}
Decoded d{};d.op=op;d.format=format_for(op);d.raw=raw;d.rd=(raw>>21)&31;d.rs1=(raw>>16)&31;d.rs2=(raw>>11)&31;d.aux=(raw>>6)&31;d.flags=raw&63;d.selector=d.rd;
if(d.format==Format::I||d.format==Format::M||d.format==Format::S)d.imm=sx(raw&0xffff,16);else if(d.format==Format::B)d.imm=sx(raw&0x1fffff,21);
if(d.format==Format::R){
 if((op==Opcode::NOP||op==Opcode::EXIT)&&(raw&0x03ffffffu))trap(TrapCode::MalformedEncoding,"non-zero reserved no-operand fields");
 if(op==Opcode::MOV&&(d.rs2||d.aux||d.flags))trap(TrapCode::MalformedEncoding,"non-zero reserved MOV fields");
 if((op==Opcode::ADD||op==Opcode::SUB||op==Opcode::MUL)&&(d.aux||d.flags))trap(TrapCode::MalformedEncoding,"non-zero reserved arithmetic fields");
 if(op==Opcode::FMA&&d.flags)trap(TrapCode::MalformedEncoding,"non-zero reserved FMA flags");
}
if(op==Opcode::MOVI&&d.rs1)trap(TrapCode::MalformedEncoding,"MOVI base field must be zero");
if(d.format==Format::B&&op==Opcode::BRA&&d.selector)trap(TrapCode::MalformedEncoding,"BRA selector must be zero");
if(d.format==Format::S){
 if(op==Opcode::BARRIER){if(d.selector>3||d.rs1||(raw&0xffffu))trap(TrapCode::InvalidSelector,"invalid barrier encoding");}
 else if(d.rs1>2||(raw&0xffffu))trap(TrapCode::InvalidSelector,"invalid builtin selector");
}
return d;}
uint32_t encode_r(Opcode o,uint8_t rd,uint8_t a,uint8_t b,uint8_t aux,uint8_t flags){return(uint32_t(o)<<26)|(uint32_t(rd&31)<<21)|(uint32_t(a&31)<<16)|(uint32_t(b&31)<<11)|(uint32_t(aux&31)<<6)|(flags&63);}
uint32_t encode_i(Opcode o,uint8_t rd,uint8_t rs,int16_t imm){return(uint32_t(o)<<26)|(uint32_t(rd&31)<<21)|(uint32_t(rs&31)<<16)|uint16_t(imm);}
uint32_t encode_b(Opcode o,uint8_t s,int32_t off){if(off<-(1<<20)||off>=(1<<20))trap(TrapCode::MalformedEncoding,"branch offset out of range");return(uint32_t(o)<<26)|(uint32_t(s&31)<<21)|(uint32_t(off)&0x1fffff);}
uint32_t encode_s(Opcode o,uint8_t rd,uint8_t selector,uint16_t imm){return(uint32_t(o)<<26)|(uint32_t(rd&31)<<21)|(uint32_t(selector&31)<<16)|imm;}
}
