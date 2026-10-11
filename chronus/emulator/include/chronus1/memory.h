#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>
#include "trap.h"
namespace chronus1 {
class Memory {
 std::vector<uint8_t> bytes_;
 public:
 explicit Memory(size_t size) : bytes_(size,0) {}
 size_t size() const { return bytes_.size(); }
 uint32_t read32(uint64_t address) const;
 void write32(uint64_t address,uint32_t value);
 void write_bytes(size_t address,const void* data,size_t size);
 const std::vector<uint8_t>& bytes() const { return bytes_; }
};
}
