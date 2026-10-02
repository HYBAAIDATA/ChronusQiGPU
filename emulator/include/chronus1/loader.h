#pragma once
#include <cstdint>
#include <filesystem>
#include <vector>
namespace chronus1 {
struct Binary { uint16_t major{},minor{}; uint32_t flags{},entry{},global_bytes{}; std::vector<uint32_t> code; };
Binary load_binary(const std::filesystem::path& path);
void write_binary(const std::filesystem::path& path,const Binary& binary);
}
