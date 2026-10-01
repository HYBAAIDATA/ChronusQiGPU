// MLA1517 shared-memory transport: the 64-byte hot descriptor and the
// bounded sequence-numbered SPSC ring that carries it.
//
// The descriptor is the 11D state in transport form — D1..D11 plus one
// route/control slot — never a replacement for the full exact Aethel object.
#ifndef MLA1517_SHM_H
#define MLA1517_SHM_H

#include <atomic>
#include <cstdint>

namespace mla1517 {

// 11D axes, matching hardware/mla1517_chronus_v1.json:
//   D1 payload_nonce        D2 lucas_scale      D3 pisot_fold
//   D4 fibonacci_exact      D5 zeckendorf_code  D6 binet_projection
//   D7 prime_address        D8 polyhedral       D9 transform_eigenbasis
//   D10 cassini_integrity   D11 lineage_time
// plus the route/control slot.
struct alignas(64) Mla11DState {
    std::uint64_t d1_nonce;
    std::uint32_t d2_lucas_scale;
    std::uint32_t d3_pisot_fold;
    std::uint32_t d4_fibonacci_exact;
    std::uint32_t d5_zeckendorf;
    std::uint32_t d6_binet_view;
    std::uint32_t d7_prime_address;
    std::uint32_t d8_polyhedral;
    std::uint32_t d9_eigen;
    std::int32_t d10_cassini;
    std::uint32_t d11_lineage;
    std::uint32_t route_control;
    std::uint32_t reserved[3];
};

static_assert(sizeof(Mla11DState) == 64, "hot descriptor must stay 64 bytes");
static_assert(alignof(Mla11DState) == 64, "hot descriptor must be 64-aligned");

constexpr std::uint32_t M32_PARTITIONS = 32;
constexpr std::uint32_t ICOSAHEDRAL_EXECUTION_NODES = 12;
constexpr std::uint32_t DODECAHEDRAL_MEMORY_NODES = 20;
constexpr std::size_t MLA1517_RING_CAPACITY = 1024;

// Bounded sequence-numbered single-producer/single-consumer ring. Sequence
// positions, not process-local pointers, are published with acquire/release
// ordering; failed lanes are never materialised into a descriptor.
struct Mla1517Ring {
    std::atomic<std::uint64_t> head;  // next sequence to publish (producer)
    std::atomic<std::uint64_t> tail;  // next sequence to consume (consumer)
    Mla11DState slots[MLA1517_RING_CAPACITY];
};

inline bool ring_push(Mla1517Ring &ring, const Mla11DState &state) {
    std::uint64_t head = ring.head.load(std::memory_order_relaxed);
    if (head - ring.tail.load(std::memory_order_acquire) >= MLA1517_RING_CAPACITY) {
        return false;  // bounded: overflow is reported, never dropped silently
    }
    ring.slots[head % MLA1517_RING_CAPACITY] = state;
    ring.head.store(head + 1, std::memory_order_release);
    return true;
}

inline bool ring_pop(Mla1517Ring &ring, Mla11DState &state) {
    std::uint64_t tail = ring.tail.load(std::memory_order_relaxed);
    if (ring.head.load(std::memory_order_acquire) == tail) {
        return false;
    }
    state = ring.slots[tail % MLA1517_RING_CAPACITY];
    ring.tail.store(tail + 1, std::memory_order_release);
    return true;
}

}  // namespace mla1517

#endif  // MLA1517_SHM_H
