#pragma once
#include <stdexcept>
#include <string>
namespace chronus1 {
enum class TrapCode { IllegalOpcode, MalformedEncoding, Misaligned, OutOfBounds, InvalidSelector, DivergenceOverflow, BarrierDeadlock, InvalidEarlyExit, BudgetExhausted, BinaryFormat };
class Trap final : public std::runtime_error {
 public:
  TrapCode code;
  explicit Trap(TrapCode c, const std::string& what) : std::runtime_error(what), code(c) {}
};
[[noreturn]] inline void trap(TrapCode c, const std::string& what) { throw Trap(c, what); }
}
