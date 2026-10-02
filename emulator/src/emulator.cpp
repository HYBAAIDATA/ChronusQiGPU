#include "chronus1/emulator.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
namespace chronus1 {
static uint32_t fma_bits(uint32_t a,uint32_t b,uint32_t c){float x,y,z,r;std::memcpy(&x,&a,4);std::memcpy(&y,&b,4);std::memcpy(&z,&c,4);r=std::fma(x,y,z);uint32_t out;std::memcpy(&out,&r,4);return out;}
Emulator::Emulator(Binary b,size_t committed):binary_(std::move(b)),global_(committed){if(binary_.major!=1)trap(TrapCode::BinaryFormat,"unsupported ISA major");if(binary_.global_bytes&&committed<binary_.global_bytes)trap(TrapCode::BinaryFormat,"committed VRAM below binary requirement");}
ExecutionStats Emulator::dispatch(const Dispatch&d){for(int i=0;i<3;i++){if(!d.global[i]||!d.local[i])trap(TrapCode::InvalidSelector,"zero dispatch dimension");}uint64_t local_count=uint64_t(d.local[0])*d.local[1]*d.local[2];if(local_count>256)trap(TrapCode::InvalidSelector,"work-group exceeds Chronus-1 v1 limit");ExecutionStats s{};std::array<uint32_t,3> groups{};for(int i=0;i<3;i++)groups[i]=(d.global[i]+d.local[i]-1)/d.local[i];for(uint32_t z=0;z<groups[2];z++)for(uint32_t y=0;y<groups[1];y++)for(uint32_t x=0;x<groups[0];x++){run_group(d,{x,y,z},s);s.work_groups++;}return s;}
void Emulator::run_group(const Dispatch&d,const std::array<uint32_t,3>&group,ExecutionStats&s){uint32_t count=d.local[0]*d.local[1]*d.local[2];std::vector<Warp> warps((count+31)/32);Memory local(65536);
for(uint32_t linear=0;linear<count;linear++){uint32_t lx=linear%d.local[0],q=linear/d.local[0],ly=q%d.local[1],lz=q/d.local[1];auto&w=warps[linear/32];auto&lane=w.lanes[linear%32];lane.lid={lx,ly,lz};lane.gid={group[0]*d.local[0]+lx,group[1]*d.local[1]+ly,group[2]*d.local[2]+lz};lane.active=lane.gid[0]<d.global[0]&&lane.gid[1]<d.global[1]&&lane.gid[2]<d.global[2];lane.retired=!lane.active;lane.pc=binary_.entry;}
auto all_done=[&]{for(auto&w:warps)for(auto&l:w.lanes)if(l.active&&!l.retired)return false;return true;};
while(!all_done()){
 if(s.lane_instructions>=d.instruction_budget)trap(TrapCode::BudgetExhausted,"instruction budget exhausted");
 // Release a barrier only when every non-retired lane has reached the same instance.
 bool any_live=false,all_wait=true,any_wait=false,any_retired=false;uint32_t barrier_pc=0;bool have_pc=false;
 for(auto&w:warps)for(auto&l:w.lanes)if(l.active){if(l.retired){any_retired=true;continue;}any_live=true;if(!l.waiting)all_wait=false;else{any_wait=true;if(!have_pc){barrier_pc=l.barrier_pc;have_pc=true;}else if(l.barrier_pc!=barrier_pc)all_wait=false;}}
 if(any_wait&&any_retired)trap(TrapCode::InvalidEarlyExit,"work-item exited before a peer barrier");
 if(any_live&&all_wait&&have_pc){for(auto&w:warps)for(auto&l:w.lanes)if(l.active&&!l.retired){l.waiting=false;l.pc+=4;}continue;}
 Warp* selected=nullptr;uint32_t pc=std::numeric_limits<uint32_t>::max(),mask=0;
 for(auto&w:warps){uint32_t wp=std::numeric_limits<uint32_t>::max();for(auto&l:w.lanes)if(l.active&&!l.retired&&!l.waiting)wp=std::min(wp,l.pc);if(wp<pc){pc=wp;selected=&w;}}
 if(!selected){bool retired_with_waiters=false;for(auto&w:warps)for(auto&l:w.lanes)if(l.active&&l.retired)retired_with_waiters=true;trap(retired_with_waiters?TrapCode::InvalidEarlyExit:TrapCode::BarrierDeadlock,"work-group cannot make progress");}
 for(int i=0;i<32;i++){auto&l=selected->lanes[i];if(l.active&&!l.retired&&!l.waiting&&l.pc==pc)mask|=1u<<i;}
 if(pc%4||pc/4>=binary_.code.size()) trap(TrapCode::OutOfBounds,"PC outside code");
 Decoded ins=decode(binary_.code[pc/4]);
 s.scheduler_steps++;
 uint32_t taken=0,fall=0;
 for(int i=0;i<32;i++)if(mask&(1u<<i)){auto&l=selected->lanes[i];auto R=[&](uint8_t r){return r?l.r[r]:0u;};auto W=[&](uint8_t r,uint32_t v){if(r)l.r[r]=v;};uint64_t addr;switch(ins.op){
 case Opcode::NOP:l.pc+=4;break;case Opcode::MOV:W(ins.rd,R(ins.rs1));l.pc+=4;break;case Opcode::MOVI:W(ins.rd,uint32_t(ins.imm));l.pc+=4;break;case Opcode::ADD:W(ins.rd,R(ins.rs1)+R(ins.rs2));l.pc+=4;break;case Opcode::SUB:W(ins.rd,R(ins.rs1)-R(ins.rs2));l.pc+=4;break;case Opcode::MUL:W(ins.rd,uint32_t(uint64_t(R(ins.rs1))*R(ins.rs2)));l.pc+=4;break;case Opcode::FMA:W(ins.rd,fma_bits(R(ins.rs1),R(ins.rs2),R(ins.aux)));l.pc+=4;break;
 case Opcode::LOAD:addr=uint64_t(R(ins.rs1))+int64_t(ins.imm);W(ins.rd,global_.read32(addr));l.pc+=4;break;case Opcode::STORE:addr=uint64_t(R(ins.rs1))+int64_t(ins.imm);global_.write32(addr,R(ins.rd));l.pc+=4;break;case Opcode::LLOAD:addr=uint64_t(R(ins.rs1))+int64_t(ins.imm);W(ins.rd,local.read32(addr));l.pc+=4;break;case Opcode::LSTORE:addr=uint64_t(R(ins.rs1))+int64_t(ins.imm);local.write32(addr,R(ins.rd));l.pc+=4;break;
 case Opcode::BARRIER:l.waiting=true;l.barrier_pc=l.pc;break;case Opcode::BRA:l.pc=uint32_t(int64_t(l.pc)+4+(int64_t(ins.imm)<<2));taken|=1u<<i;break;
 case Opcode::BRAZ:{bool t=R(ins.rd)==0;l.pc=t?uint32_t(int64_t(l.pc)+4+(int64_t(ins.imm)<<2)):l.pc+4;(t?taken:fall)|=1u<<i;break;}
 case Opcode::BRANZ:{bool t=R(ins.rd)!=0;l.pc=t?uint32_t(int64_t(l.pc)+4+(int64_t(ins.imm)<<2)):l.pc+4;(t?taken:fall)|=1u<<i;break;}
 case Opcode::GET_GID:W(ins.rd,l.gid[ins.rs1]);l.pc+=4;break;case Opcode::GET_LID:W(ins.rd,l.lid[ins.rs1]);l.pc+=4;break;case Opcode::GET_GSIZE:W(ins.rd,d.global[ins.rs1]);l.pc+=4;break;case Opcode::GET_LSIZE:W(ins.rd,d.local[ins.rs1]);l.pc+=4;break;case Opcode::EXIT:l.retired=true;break;default:trap(TrapCode::IllegalOpcode,"unreachable opcode");}
 l.r[0]=0;s.lane_instructions++;}
 if(taken&&fall){if(selected->divergence.size()>=32)trap(TrapCode::DivergenceOverflow,"divergence stack overflow");selected->divergence.push_back({pc,taken,fall});}
 // Per-lane PCs are authoritative; pop trace frames once all live lanes reconverge.
 if(!selected->divergence.empty()){uint32_t common=0;bool set=false,same=true;for(auto&l:selected->lanes)if(l.active&&!l.retired&&!l.waiting){if(!set){common=l.pc;set=true;}else same&=l.pc==common;}if(same)selected->divergence.clear();}
 }
}
}
