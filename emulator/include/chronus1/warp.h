#pragma once
#include <array>
#include <cstdint>
#include <vector>
namespace chronus1 {
struct DivergenceFrame { uint32_t branch_pc{}, taken_mask{}, fallthrough_mask{}; };
struct Lane {
 std::array<uint32_t,32> r{};
 uint32_t pc{};
 bool active{};
 bool retired{};
 bool waiting{};
 uint32_t barrier_pc{};
 std::array<uint32_t,3> gid{},lid{};
};
struct Warp { std::array<Lane,32> lanes{}; std::vector<DivergenceFrame> divergence; };
}
