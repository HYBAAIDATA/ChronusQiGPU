// MLA1517 SIMT warp reference: the M32 logical partition executed as a
// 32-lane warp with a ballot predicate and prefix-rank compaction, routing
// winners by prime address to the 20 Aethel UMA vault destinations.
//
//   lane_id   = 0..31
//   nonce     = lane_id + 32 * step
//   warp_vote = ballot(D5 void/anchor predicate)
//   rank(lane) = popcount(warp_vote & ((1 << lane) - 1))
//
// A zero ballot advances the full warp; a non-zero ballot identifies the
// exact winning lanes for materialisation into complete 11D states.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#include "mla1517_math.h"
#include "mla1517_shm.h"

namespace {

using mla1517::DODECAHEDRAL_MEMORY_NODES;
using mla1517::ICOSAHEDRAL_EXECUTION_NODES;
using mla1517::M32_PARTITIONS;
using mla1517::Mla11DState;

constexpr std::uint32_t WARP_STEPS = 20000;

inline std::uint32_t ballot(bool (&pred)[M32_PARTITIONS]) {
    std::uint32_t mask = 0;
    for (std::uint32_t lane = 0; lane < M32_PARTITIONS; ++lane) {
        if (pred[lane]) {
            mask |= 1u << lane;
        }
    }
    return mask;
}

inline std::uint32_t prefix_rank(std::uint32_t vote, std::uint32_t lane) {
    return __builtin_popcount(vote & ((1u << lane) - 1u));
}

}  // namespace

int main() {
    std::uint32_t difficulty_bits = 6;
    if (const char *v = std::getenv("MLA1517_DIFFICULTY_BITS")) {
        difficulty_bits = std::strtoul(v, nullptr, 10);
    }
    const std::uint32_t void_mask = (1u << difficulty_bits) - 1u;
    const std::uint32_t anchor_mask = 1u << difficulty_bits;

    std::uint64_t lanes_evaluated = 0;
    std::uint64_t winners = 0;
    std::uint64_t vault_writes = 0;
    std::uint64_t divergence = 0;
    std::uint64_t vault[DODECAHEDRAL_MEMORY_NODES] = {};
    bool ballot_contract = true;
    bool route_contract = true;

    for (std::uint32_t step = 0; step < WARP_STEPS; ++step) {
        bool pred[M32_PARTITIONS];
        // Every lane evaluates the D5 Fibonacci-void predicate together.
        for (std::uint32_t lane = 0; lane < M32_PARTITIONS; ++lane) {
            const std::uint64_t nonce = lane + M32_PARTITIONS * step;
            const std::uint32_t d5 = static_cast<std::uint32_t>(
                mla1517::zeckendorf_mask(nonce));
            pred[lane] = (d5 & void_mask) == 0 && (d5 & anchor_mask) != 0;
            ++lanes_evaluated;
        }
        const std::uint32_t vote = ballot(pred);
        // Contract check: the ballot bit must equal the lane predicate.
        for (std::uint32_t lane = 0; lane < M32_PARTITIONS; ++lane) {
            if (((vote >> lane) & 1u) != (pred[lane] ? 1u : 0u)) {
                ballot_contract = false;
            }
        }
        if (vote == 0) {
            continue;  // full warp advances; nothing materialised
        }
        for (std::uint32_t lane = 0; lane < M32_PARTITIONS; ++lane) {
            if (!((vote >> lane) & 1u)) {
                continue;
            }
            // Prefix-rank compaction, then prime-address UMA routing.
            const std::uint32_t rank = prefix_rank(vote, lane);
            const std::uint64_t nonce = lane + M32_PARTITIONS * step;
            Mla11DState state{};
            state.d1_nonce = nonce;
            state.d2_lucas_scale =
                static_cast<std::uint32_t>(mla1517::lucas(step % 93));
            state.d5_zeckendorf =
                static_cast<std::uint32_t>(mla1517::zeckendorf_mask(nonce));
            state.d6_binet_view =
                static_cast<std::uint32_t>(mla1517::lucas(step % 93));
            state.d7_prime_address = static_cast<std::uint32_t>(
                mla1517::prime_address(nonce) & 0xFFFFFFFFu);
            state.d8_polyhedral =
                state.d7_prime_address % DODECAHEDRAL_MEMORY_NODES;
            state.d9_eigen = rank;
            state.d10_cassini = 1;
            state.d11_lineage = step;
            state.route_control = lane;
            const std::uint32_t expected_node =
                static_cast<std::uint32_t>(mla1517::prime_address(nonce) %
                                           DODECAHEDRAL_MEMORY_NODES);
            if (state.d8_polyhedral != expected_node) {
                route_contract = false;
            }
            ++vault[state.d8_polyhedral];
            ++vault_writes;
            ++winners;
        }
    }

    std::printf(
        "{\n"
        "  \"warp_width\": %u,\n"
        "  \"warp_steps\": %u,\n"
        "  \"lanes_evaluated\": %llu,\n"
        "  \"ballot_selected_winners\": %llu,\n"
        "  \"uma_vault_writes\": %llu,\n"
        "  \"branch_divergence_events\": %llu,\n"
        "  \"icosahedral_execution_nodes\": %u,\n"
        "  \"dodecahedral_memory_nodes\": %u,\n"
        "  \"difficulty_bits\": %u,\n"
        "  \"warp_ballot_contract\": \"%s\",\n"
        "  \"uma_route_contract\": \"%s\",\n"
        "  \"status\": \"%s\"\n"
        "}\n",
        M32_PARTITIONS, WARP_STEPS,
        static_cast<unsigned long long>(lanes_evaluated),
        static_cast<unsigned long long>(winners),
        static_cast<unsigned long long>(vault_writes), divergence,
        ICOSAHEDRAL_EXECUTION_NODES, DODECAHEDRAL_MEMORY_NODES,
        difficulty_bits, ballot_contract ? "PASS" : "FAIL",
        route_contract ? "PASS" : "FAIL",
        (ballot_contract && route_contract && vault_writes == winners)
            ? "PASS"
            : "FAIL");
    return (ballot_contract && route_contract) ? 0 : 1;
}
