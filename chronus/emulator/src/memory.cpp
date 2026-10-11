#include "chronus1/memory.h"
#include <cstring>
namespace chronus1 {
static void check(uint64_t a,size_t size,size_t cap){if(a%4)trap(TrapCode::Misaligned,"unaligned 32-bit memory access");if(a+size<a||a+size>cap)trap(TrapCode::OutOfBounds,"memory access outside committed range");}
uint32_t Memory::read32(uint64_t a)const{check(a,4,bytes_.size());return uint32_t(bytes_[a])|(uint32_t(bytes_[a+1])<<8)|(uint32_t(bytes_[a+2])<<16)|(uint32_t(bytes_[a+3])<<24);}
void Memory::write32(uint64_t a,uint32_t v){check(a,4,bytes_.size());for(int i=0;i<4;i++)bytes_[a+i]=uint8_t(v>>(8*i));}
void Memory::write_bytes(size_t a,const void* p,size_t n){if(a+n<a||a+n>bytes_.size())trap(TrapCode::OutOfBounds,"host upload outside committed range");std::memcpy(bytes_.data()+a,p,n);}
}
