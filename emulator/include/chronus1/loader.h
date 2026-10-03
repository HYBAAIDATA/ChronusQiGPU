#pragma once
#include <cstdint>
#include <filesystem>
#include <string>
#include <utility>
#include <vector>
namespace chronus1 {
struct Symbol { std::string name; uint32_t value{},size{}; uint8_t kind{},flags{}; };
struct Binary {
 uint16_t major{1},minor{1}; uint32_t flags{},entry{},global_bytes{};
 std::vector<uint32_t> code; std::vector<Symbol> symbols;
 std::vector<std::pair<uint32_t,uint32_t>> reconvergence;
 uint32_t reconvergence_pc(uint32_t branch_pc) const;
};
Binary load_binary(const std::filesystem::path& path);
void write_binary(const std::filesystem::path& path,const Binary& binary);
}
