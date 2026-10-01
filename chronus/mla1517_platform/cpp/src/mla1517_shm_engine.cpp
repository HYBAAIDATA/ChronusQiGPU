// MLA1517 zero-copy transport test: the 64-byte hot descriptor crossing a
// bounded sequence-numbered SPSC ring between two processes.
//
// On POSIX the ring lives in /dev/shm shared memory between a forked writer
// and reader. On platforms without POSIX shm_open/mmap the identical ring
// protocol is exercised between two threads on a shared segment and the
// report states that transport honestly instead of claiming POSIX IPC.
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <thread>

#ifndef _WIN32
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

#include "mla1517_shm.h"
#include "mla1517_math.h"

namespace {

using mla1517::ICOSAHEDRAL_EXECUTION_NODES;
using mla1517::M32_PARTITIONS;
using mla1517::Mla11DState;
using mla1517::Mla1517Ring;
using mla1517::MLA1517_RING_CAPACITY;

constexpr std::uint64_t ITEMS = 100003;

Mla11DState make_state(std::uint64_t item) {
    const std::uint32_t partition = item % M32_PARTITIONS;
    const std::uint64_t step = item / M32_PARTITIONS;
    // nonce = partition_id + 32 * step — the M32 coverage rule.
    const std::uint64_t nonce = partition + M32_PARTITIONS * step;
    Mla11DState state{};
    state.d1_nonce = nonce;
    state.d2_lucas_scale = static_cast<std::uint32_t>(mla1517::lucas(step % 93));
    state.d5_zeckendorf =
        static_cast<std::uint32_t>(mla1517::zeckendorf_mask(nonce % 1000003u));
    state.d7_prime_address =
        static_cast<std::uint32_t>(mla1517::prime_address(nonce) & 0xFFFFFFFFu);
    state.d8_polyhedral = partition % ICOSAHEDRAL_EXECUTION_NODES;
    state.d11_lineage = static_cast<std::uint32_t>(step);
    state.route_control = partition;
    return state;
}

void produce(Mla1517Ring *ring, std::uint64_t items) {
    for (std::uint64_t i = 0; i < items; ++i) {
        Mla11DState state = make_state(i);
        while (!mla1517::ring_push(*ring, state)) {
#ifndef _WIN32
            sched_yield();
#else
            std::this_thread::yield();
#endif
        }
    }
}

struct ConsumeResult {
    std::uint64_t received = 0;
    std::uint64_t bad = 0;
    std::uint64_t seen[M32_PARTITIONS] = {};
};

ConsumeResult consume(Mla1517Ring *ring, std::uint64_t items) {
    ConsumeResult result;
    Mla11DState state{};
    while (result.received < items) {
        if (!mla1517::ring_pop(*ring, state)) {
#ifndef _WIN32
            sched_yield();
#else
            std::this_thread::yield();
#endif
            continue;
        }
        const std::uint32_t partition = state.route_control % M32_PARTITIONS;
        const std::uint64_t step = static_cast<std::uint64_t>(state.d11_lineage);
        const bool coverage_ok =
            state.d1_nonce == partition + M32_PARTITIONS * step;
        const bool ordering_ok =
            state.d1_nonce == result.received;
        if (!coverage_ok || !ordering_ok) {
            ++result.bad;
        }
        ++result.seen[partition];
        ++result.received;
    }
    return result;
}

void report(const char *transport, bool posix_shm, const ConsumeResult &r,
            bool coverage_pass, bool order_pass) {
    std::printf(
        "{\n"
        "  \"transport\": \"%s\",\n"
        "  \"posix_shm\": %s,\n"
        "  \"items\": %llu,\n"
        "  \"received\": %llu,\n"
        "  \"ring_capacity\": %zu,\n"
        "  \"partitions\": %u,\n"
        "  \"hot_descriptor_bytes\": %zu,\n"
        "  \"descriptor_alignment\": %zu,\n"
        "  \"partition_coverage\": \"%s\",\n"
        "  \"sequence_order\": \"%s\",\n"
        "  \"status\": \"%s\"\n"
        "}\n",
        transport, posix_shm ? "true" : "false",
        static_cast<unsigned long long>(ITEMS),
        static_cast<unsigned long long>(r.received),
        MLA1517_RING_CAPACITY, M32_PARTITIONS, sizeof(Mla11DState),
        alignof(Mla11DState), coverage_pass ? "PASS" : "FAIL",
        order_pass ? "PASS" : "FAIL",
        (coverage_pass && order_pass && r.received == ITEMS) ? "PASS" : "FAIL");
}

}  // namespace

int main() {
#ifndef _WIN32
    const char *name = "/mla1517_ring_test";
    int fd = shm_open(name, O_CREAT | O_RDWR, 0600);
    if (fd < 0 || ftruncate(fd, sizeof(Mla1517Ring)) != 0) {
        std::fprintf(stderr, "shm_open/ftruncate failed\n");
        return 1;
    }
    auto *ring = static_cast<Mla1517Ring *>(
        mmap(nullptr, sizeof(Mla1517Ring), PROT_READ | PROT_WRITE, MAP_SHARED,
             fd, 0));
    if (ring == MAP_FAILED) {
        std::fprintf(stderr, "mmap failed\n");
        return 1;
    }
    new (ring) Mla1517Ring{};

    pid_t child = fork();
    if (child < 0) {
        std::fprintf(stderr, "fork failed\n");
        return 1;
    }
    if (child == 0) {
        produce(ring, ITEMS);
        _exit(0);
    }
    ConsumeResult r = consume(ring, ITEMS);
    int status = 0;
    waitpid(child, &status, 0);

    bool coverage = r.received == ITEMS && r.bad == 0;
    for (std::uint32_t p = 0; p < M32_PARTITIONS; ++p) {
        coverage = coverage && r.seen[p] == ITEMS / M32_PARTITIONS + (p < ITEMS % M32_PARTITIONS);
    }
    report("posix_shm_cross_process", true, r, coverage, r.bad == 0);
    munmap(ring, sizeof(Mla1517Ring));
    shm_unlink(name);
    return (coverage && r.bad == 0) ? 0 : 1;
#else
    Mla1517Ring *ring = new Mla1517Ring{};
    std::atomic<ConsumeResult *> out{nullptr};
    std::thread writer([&] { produce(ring, ITEMS); });
    std::thread reader([&] {
        static ConsumeResult r;
        r = consume(ring, ITEMS);
        out.store(&r, std::memory_order_release);
    });
    writer.join();
    reader.join();
    ConsumeResult r = *out.load(std::memory_order_acquire);
    bool coverage = r.received == ITEMS && r.bad == 0;
    for (std::uint32_t p = 0; p < M32_PARTITIONS; ++p) {
        coverage = coverage && r.seen[p] == ITEMS / M32_PARTITIONS + (p < ITEMS % M32_PARTITIONS);
    }
    report("in_process_threads", false, r, coverage, r.bad == 0);
    delete ring;
    return (coverage && r.bad == 0) ? 0 : 1;
#endif
}
