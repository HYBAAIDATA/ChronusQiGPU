#pragma once
#include <deque>
#include "emulator.h"
namespace chronus1 {
struct DispatchCommand { Dispatch dispatch; };
class CommandProcessor {
 std::deque<DispatchCommand> ring_;
 public:
 void submit(DispatchCommand c){ring_.push_back(c);}
 bool empty() const{return ring_.empty();}
 ExecutionStats run_one(Emulator& e){if(ring_.empty()) trap(TrapCode::BinaryFormat,"empty command ring"); auto c=ring_.front(); ring_.pop_front(); return e.dispatch(c.dispatch);}
};
}
