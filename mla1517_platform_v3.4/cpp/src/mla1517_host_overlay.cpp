// MLA1517 host-GPU overlay backend: deterministic tile planning and
// threaded lane execution over the M32 work domain.
//
// Conformance implementation: it proves the scheduling and result-merge
// contract (17 lanes, 17 tiles, complete coverage, reference-kernel
// equivalence) without pretending CPU threads are GPU throughput. The GPU
// backend adapter consumes the same tile plan.
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <thread>
#include <vector>

#include "mla1517_math.h"

namespace {

constexpr std::uint64_t ITEMS = 100003;
constexpr std::uint32_t LANES = 17;
constexpr std::uint32_t TILES = 17;

// Reference kernel: the fold each lane applies to its items. Chosen so the
// single-threaded reference and the tiled execution must agree bit-exactly.
std::uint64_t kernel_item(std::uint64_t item) {
    const std::uint64_t mask = mla1517::zeckendorf_mask(item % 1000003u);
    return mask ^ mla1517::fib(item % 31) ^ mla1517::lucas(item % 17);
}

// Tile plan: item -> (lane = item % LANES, offset = item / LANES).
struct Tile {
    std::uint32_t lane;
    std::uint64_t begin;
    std::uint64_t end;
};

std::uint64_t reference_checksum() {
    std::uint64_t acc = 0;
    for (std::uint64_t i = 0; i < ITEMS; ++i) {
        acc ^= kernel_item(i) + i;
    }
    return acc;
}

}  // namespace

int main() {
    // Deterministic tiling: each tile covers a contiguous stride-17 slice.
    std::vector<Tile> tiles(TILES);
    const std::uint64_t per_tile = (ITEMS + TILES - 1) / TILES;
    for (std::uint32_t t = 0; t < TILES; ++t) {
        tiles[t] = Tile{t % LANES, t * per_tile,
                        (t + 1 == TILES) ? ITEMS : (t + 1) * per_tile};
    }

    // Threaded lane execution; every lane consumes its tile's items.
    std::vector<std::uint64_t> counts(ITEMS, 0);
    std::atomic<std::uint64_t> checksum{0};
    std::vector<std::thread> workers;
    workers.reserve(LANES);
    for (const Tile &tile : tiles) {
        workers.emplace_back([&, tile] {
            std::uint64_t acc = 0;
            for (std::uint64_t i = tile.begin; i < tile.end; ++i) {
                ++counts[i];
                acc ^= kernel_item(i) + i;
            }
            checksum.fetch_xor(acc, std::memory_order_relaxed);
        });
    }
    for (auto &w : workers) {
        w.join();
    }

    bool coverage = true;
    for (std::uint64_t i = 0; i < ITEMS; ++i) {
        if (counts[i] != 1) {
            coverage = false;
            break;
        }
    }
    const bool kernel = checksum.load() == reference_checksum();
    const bool pass = coverage && kernel;

    std::printf(
        "{\n"
        "  \"items\": %llu,\n"
        "  \"lanes\": %u,\n"
        "  \"tiles\": %u,\n"
        "  \"coverage\": \"%s\",\n"
        "  \"kernel\": \"%s\",\n"
        "  \"status\": \"%s\"\n"
        "}\n",
        static_cast<unsigned long long>(ITEMS), LANES, TILES,
        coverage ? "PASS" : "FAIL", kernel ? "PASS" : "FAIL",
        pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}
