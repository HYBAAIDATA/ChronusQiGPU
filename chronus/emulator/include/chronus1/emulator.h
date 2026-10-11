#pragma once
#include <array>
#include <cstdint>
#include <vector>
#include <array>
#include "isa.h"
#include "loader.h"
#include "memory.h"
#include "warp.h"
namespace chronus1 {
struct Dispatch { std::array<uint32_t,3> global{1,1,1}; std::array<uint32_t,3> local{1,1,1}; uint64_t instruction_budget{10000000}; };
struct ExecutionStats { uint64_t lane_instructions{}; uint64_t scheduler_steps{}; uint32_t work_groups{}; uint64_t trace_hash{1469598103934665603ull}; std::array<uint64_t,64> opcode_counts{}; };
class Emulator {
 Binary binary_;
 Memory global_;
 public:
 Emulator(Binary binary,size_t committed_global_bytes);
 Memory& global_memory(){return global_;}
 const Memory& global_memory() const{return global_;}
 ExecutionStats dispatch(const Dispatch& d);
 private:
 void run_group(const Dispatch&,const std::array<uint32_t,3>& group,ExecutionStats&);
};
}
