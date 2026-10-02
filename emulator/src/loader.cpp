#include "chronus1/loader.h"
#include "chronus1/trap.h"
#include <fstream>
namespace chronus1 {
static uint32_t crc32(const uint8_t* p,size_t n){uint32_t c=~0u;for(size_t i=0;i<n;i++){c^=p[i];for(int k=0;k<8;k++)c=(c>>1)^(0xedb88320u&uint32_t(-int(c&1)));}return~c;}
static uint16_t u16(const std::vector<uint8_t>&b,size_t o){return uint16_t(b[o])|uint16_t(b[o+1])<<8;}static uint32_t u32(const std::vector<uint8_t>&b,size_t o){return uint32_t(b[o])|uint32_t(b[o+1])<<8|uint32_t(b[o+2])<<16|uint32_t(b[o+3])<<24;}
Binary load_binary(const std::filesystem::path&p){std::ifstream f(p,std::ios::binary);std::vector<uint8_t>b((std::istreambuf_iterator<char>(f)),{});if(b.size()<32||std::string((char*)b.data(),4)!="CHRN")trap(TrapCode::BinaryFormat,"bad CHRN header");Binary x;x.major=u16(b,4);x.minor=u16(b,6);x.flags=u32(b,8);x.entry=u32(b,12);auto words=u32(b,16);x.global_bytes=u32(b,20);auto checksum=u32(b,24);auto meta=u32(b,28);if(x.major!=1||meta||b.size()!=32+size_t(words)*4||x.entry%4)trap(TrapCode::BinaryFormat,"unsupported binary layout");if(crc32(b.data()+32,b.size()-32)!=checksum)trap(TrapCode::BinaryFormat,"binary checksum mismatch");for(size_t o=32;o<b.size();o+=4)x.code.push_back(u32(b,o));return x;}
void write_binary(const std::filesystem::path&p,const Binary&x){std::vector<uint8_t>b(32+x.code.size()*4);b[0]='C';b[1]='H';b[2]='R';b[3]='N';auto w16=[&](size_t o,uint16_t v){b[o]=v;b[o+1]=v>>8;};auto w32=[&](size_t o,uint32_t v){for(int i=0;i<4;i++)b[o+i]=v>>(8*i);};w16(4,x.major);w16(6,x.minor);w32(8,x.flags);w32(12,x.entry);w32(16,x.code.size());w32(20,x.global_bytes);w32(28,0);for(size_t i=0;i<x.code.size();i++)w32(32+4*i,x.code[i]);w32(24,crc32(b.data()+32,b.size()-32));std::ofstream f(p,std::ios::binary);f.write((char*)b.data(),b.size());}
}
