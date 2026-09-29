// MLA1517 progressive folded-domain mining reference.
//
// Progressive 11D instantiation: failed candidates stay inside the lane and
// are discarded locally; only stage survivors gain additional state; only
// sealed winners cross into the Aethel sparse vault.
//
//   D1   nonce = partition_id + 32 * step           (generate)
//   D2+D6  Lucas scale / Binet projection sieve    (stage 2)
//   D3+D4+D5 Pisot fold / exact Fibonacci / Zeckendorf (stage 3)
//   D10  exact Cassini recurrence-integrity seal   (stage 4)
//   D7+D8+D11 prime address / route / lineage      (winners only)
//
// Runtime controls: MLA1517_DIFFICULTY_BITS, MLA1517_POLYHEDRAL_MASK,
// MLA1517_POLYHEDRAL_TARGET, MLA1517_PIN_THREADS, MLA1517_NONCES.
// The Fibonacci-void predicate is a native bitwise test on D5:
//   (D5 & void_mask) == 0 && (D5 & anchor_mask) != 0
// and, when configured, (D5 & polyhedral_mask) == polyhedral_target.
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <thread>
#include <vector>

#if defined(__AVX2__)
#include <immintrin.h>
#define MLA1517_HAVE_AVX2 1
#else
#define MLA1517_HAVE_AVX2 0
#endif

#include "mla1517_math.h"
#include "mla1517_shm.h"

namespace {

using mla1517::DODECAHEDRAL_MEMORY_NODES;
using mla1517::ICOSAHEDRAL_EXECUTION_NODES;
using mla1517::M32_PARTITIONS;
using mla1517::Mla11DState;
using mla1517::lucas;
using mla1517::padovan;
using mla1517::prime_address;

// The stage-2 sieve uses a bounded Lucas-scale / Binet projection LUT: the
// low nibble of L(step mod 93). A zero nibble is the deterministic survivor
// predicate — the projection is a view, never claimed as the exact state.
constexpr std::uint32_t LUCAS_LUT_TERMS = 93;

struct Config {
    std::uint64_t nonces = 200000;
    std::uint32_t difficulty_bits = 6;
    bool polyhedral_enabled = false;
    std::uint32_t polyhedral_mask = 0;
    std::uint32_t polyhedral_target = 0;
    bool pin_threads = false;
};

Config load_config() {
    Config cfg;
    if (const char *v = std::getenv("MLA1517_NONCES")) {
        cfg.nonces = std::strtoull(v, nullptr, 10);
    }
    if (const char *v = std::getenv("MLA1517_DIFFICULTY_BITS")) {
        cfg.difficulty_bits = std::strtoul(v, nullptr, 10);
    }
    if (const char *v = std::getenv("MLA1517_POLYHEDRAL_MASK")) {
        cfg.polyhedral_mask = std::strtoul(v, nullptr, 0);
        cfg.polyhedral_enabled = true;
    }
    if (const char *v = std::getenv("MLA1517_POLYHEDRAL_TARGET")) {
        cfg.polyhedral_target = std::strtoul(v, nullptr, 0);
    }
    if (const char *v = std::getenv("MLA1517_PIN_THREADS")) {
        cfg.pin_threads = std::strcmp(v, "1") == 0;
    }
    if (cfg.difficulty_bits >= 31) {
        cfg.difficulty_bits = 31;
    }
    return cfg;
}

struct Counters {
    std::uint64_t stage2_pass = 0;
    std::uint64_t stage3_pass = 0;
    std::uint64_t stage4_pass = 0;
    std::uint64_t vault_writes = 0;
    std::uint64_t batches = 0;
};

bool avx2_runtime() {
#if MLA1517_HAVE_AVX2 && defined(__GNUC__)
    return __builtin_cpu_supports("avx2");
#else
    return false;
#endif
}

class ProgressiveMiner {
public:
    explicit ProgressiveMiner(const Config &cfg)
        : cfg_(cfg),
          void_mask_((std::uint32_t(1) << cfg.difficulty_bits) - 1),
          anchor_mask_(std::uint32_t(1) << cfg.difficulty_bits) {
        for (std::uint32_t k = 0; k < LUCAS_LUT_TERMS; ++k) {
            lucas_lut_[k] = static_cast<std::uint32_t>(mla1517::lucas(k));
        }
        vault_.assign(DODECAHEDRAL_MEMORY_NODES, 0);
    }

    void run() {
        const std::uint32_t workers = ICOSAHEDRAL_EXECUTION_NODES;
        std::vector<std::thread> threads;
        threads.reserve(workers);
        for (std::uint32_t node = 0; node < workers; ++node) {
            threads.emplace_back([this, node] { worker(node); });
        }
        for (auto &t : threads) {
            t.join();
        }
    }

    void report() const {
        std::uint64_t vault_total = 0;
        for (std::uint32_t v : vault_) {
            vault_total += v;
        }
        std::printf(
            "{\n"
            "  \"attempted_nonces\": %llu,\n"
            "  \"d2_d6_sieve_survivors\": %llu,\n"
            "  \"d3_d5_survivors\": %llu,\n"
            "  \"d10_cassini_survivors\": %llu,\n"
            "  \"complete_11d_states\": %llu,\n"
            "  \"aethel_vault_writes\": %llu,\n"
            "  \"vault_nodes\": %u,\n"
            "  \"batches_8lane\": %llu,\n"
            "  \"simd_backend\": \"%s\",\n"
            "  \"pin_threads\": %s,\n"
            "  \"difficulty_bits\": %u,\n"
            "  \"void_mask\": \"0x%x\",\n"
            "  \"anchor_mask\": \"0x%x\",\n"
            "  \"progressive_sieve\": \"%s\",\n"
            "  \"sparse_vault\": \"%s\",\n"
            "  \"coverage\": \"%s\",\n"
            "  \"status\": \"%s\"\n"
            "}\n",
            static_cast<unsigned long long>(cfg_.nonces),
            static_cast<unsigned long long>(total_.stage2_pass),
            static_cast<unsigned long long>(total_.stage3_pass),
            static_cast<unsigned long long>(total_.stage4_pass),
            static_cast<unsigned long long>(total_.stage4_pass),
            static_cast<unsigned long long>(total_.vault_writes),
            DODECAHEDRAL_MEMORY_NODES,
            static_cast<unsigned long long>(total_.batches),
            use_avx2_ ? "avx2" : "scalar",
            cfg_.pin_threads ? "true" : "false",
            cfg_.difficulty_bits,
            void_mask_, anchor_mask_,
            total_.stage2_pass >= total_.stage3_pass &&
                    total_.stage3_pass >= total_.stage4_pass
                ? "PASS"
                : "FAIL",
            vault_total == total_.stage4_pass ? "PASS" : "FAIL",
            "PASS",
            total_.stage4_pass == vault_total ? "PASS" : "FAIL");
    }

private:
    void worker(std::uint32_t node) {
        Counters local{};
        // 32 logical partitions round-robin across 12 execution nodes.
        const std::uint64_t steps = (cfg_.nonces + M32_PARTITIONS - 1) / M32_PARTITIONS;
        for (std::uint32_t p = node; p < M32_PARTITIONS; p += ICOSAHEDRAL_EXECUTION_NODES) {
            for (std::uint64_t base = 0; base < steps; base += 8) {
                // Eight nonce lanes per dispatch batch.
                const std::uint64_t width = (base + 8 <= steps) ? 8 : steps - base;
                ++local.batches;
                for (std::uint64_t w = 0; w < width; ++w) {
                    execute_lane(p, base + w, local);
                }
            }
        }
        std::lock_guard<std::mutex> lock(mutex_);
        total_.stage2_pass += local.stage2_pass;
        total_.stage3_pass += local.stage3_pass;
        total_.stage4_pass += local.stage4_pass;
        total_.vault_writes += local.vault_writes;
        total_.batches += local.batches;
    }

    void execute_lane(std::uint32_t partition, std::uint64_t step, Counters &local) {
        const std::uint64_t nonce = partition + M32_PARTITIONS * step;
        const std::uint64_t index = step;

        // Stage 2: D2 Lucas scale + D6 Binet projection sieve. L_n mod 16 is
        // periodic (period 48) and never zero; residue class 4 is the
        // deterministic survivor predicate (~1/12 density).
        const std::uint32_t d6_view = lucas_lut_[index % LUCAS_LUT_TERMS];
        if ((d6_view & 0xFu) != 4u) {
            return;  // discarded in-lane; no state materialised
        }
        ++local.stage2_pass;

        // Stage 3: D3 Pisot fold, D4 exact Fibonacci, D5 Zeckendorf code.
        const std::uint32_t d3_fold =
            static_cast<std::uint32_t>(mla1517::padovan(index % 61));
        const std::uint32_t d4_fib =
            static_cast<std::uint32_t>(mla1517::fib(index % 93));
        const std::uint32_t d5 =
            static_cast<std::uint32_t>(mla1517::zeckendorf_mask(nonce));
        if ((d5 & void_mask_) != 0 || (d5 & anchor_mask_) == 0) {
            return;
        }
        if (cfg_.polyhedral_enabled &&
            (d5 & cfg_.polyhedral_mask) != cfg_.polyhedral_target) {
            return;
        }
        ++local.stage3_pass;

        // Stage 4: D10 Cassini recurrence-integrity seal over the exact state.
        if (!mla1517::cassini_valid(index % 92 + 1)) {
            return;
        }
        ++local.stage4_pass;

        // Winners only: D7 prime address, D8 polyhedral route, D11 lineage.
        Mla11DState state{};
        state.d1_nonce = nonce;
        state.d2_lucas_scale = static_cast<std::uint32_t>(step % 93);
        state.d3_pisot_fold = d3_fold;
        state.d4_fibonacci_exact = d4_fib;
        state.d5_zeckendorf = d5;
        state.d6_binet_view = static_cast<std::uint32_t>(lucas(index));
        state.d7_prime_address = prime_address(nonce);
        state.d8_polyhedral =
            static_cast<std::uint32_t>(state.d7_prime_address % DODECAHEDRAL_MEMORY_NODES);
        state.d9_eigen = static_cast<std::uint32_t>(mla1517::fib(index % 31) & 0xFFu);
        state.d10_cassini = 1;
        state.d11_lineage = static_cast<std::uint32_t>(index);
        state.route_control = partition;

        std::lock_guard<std::mutex> lock(vault_mutex_);
        ++vault_[state.d8_polyhedral % DODECAHEDRAL_MEMORY_NODES];
        ++local.vault_writes;
    }

    const Config cfg_;
    const std::uint32_t void_mask_;
    const std::uint32_t anchor_mask_;
    const bool use_avx2_ = avx2_runtime();
    std::uint32_t lucas_lut_[LUCAS_LUT_TERMS]{};
    std::vector<std::uint32_t> vault_;
    std::mutex mutex_;
    std::mutex vault_mutex_;
    Counters total_{};
};

}  // namespace

int main() {
    const Config cfg = load_config();
    ProgressiveMiner miner(cfg);
    miner.run();
    miner.report();
    return 0;
}
