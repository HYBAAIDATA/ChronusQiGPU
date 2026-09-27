#ifndef MLA1517_SHM_H
#define MLA1517_SHM_H

#include <stdalign.h>
#include <stdint.h>

#include "mla1517_mmio.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MLA1517_SHM_ABI_VERSION 1u
#define MLA1517_SHM_MAGIC UINT64_C(0x4D4C413135313752) /* MLA1517R */
#define MLA1517_SHM_CAPACITY 1024u
#define MLA1517_SHM_HEADER_BYTES 192u

/*
 * The hardware hot descriptor is exactly one cache line.  The D10 field is
 * an int32 gate; the remaining packed fields are uint32 values.
 */
typedef struct {
    uint64_t d1_nonce;
    uint32_t d2_lucas;
    uint32_t d3_pisot;
    uint32_t d4_fib;
    uint32_t d5_zeckendorf;
    uint32_t d6_binet;
    uint32_t d7_prime_addr;
    uint32_t d8_route;
    uint32_t d9_eigen;
    int32_t d10_cassini;
    uint32_t d11_time_state;
    uint32_t d12_gauge;
    uint32_t reserved1;
    uint32_t reserved2;
    uint32_t reserved3;
} MLA1517_State;

_Static_assert(sizeof(MLA1517_State) == 64, "MLA1517 state must be 64 bytes");

typedef struct mla1517_shm_ring mla1517_shm_ring_t;

mla1517_shm_ring_t *mla1517_shm_open(const char *path, uint32_t capacity);
void mla1517_shm_close(mla1517_shm_ring_t *ring);
uint64_t mla1517_shm_space(const mla1517_shm_ring_t *ring);

/* Single-producer/single-consumer operations. */
int mla1517_shm_push(mla1517_shm_ring_t *ring, const MLA1517_State *state);
int mla1517_shm_pop(mla1517_shm_ring_t *ring, MLA1517_State *state);

/* Path B: MMIO vault -> shared ring without Python serialization. */
int mla1517_drain_vault_to_shm(
    mla1517_device_t *device,
    mla1517_shm_ring_t *ring,
    int timeout_ms,
    uint32_t max_records
);

/*
 * Dual-output poll: the caller receives Path A while the same committed
 * 64-byte state is published to Path B.  When the ring is full, no vault
 * record is consumed, providing backpressure instead of silent loss.
 */
int mla1517_poll_vault_to_shm(
    mla1517_device_t *device,
    mla1517_shm_ring_t *ring,
    int timeout_ms,
    mla1517_vault_record_t *record
);

#ifdef __cplusplus
}
#endif

#endif