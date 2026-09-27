#define _GNU_SOURCE

#include "mla1517_shm.h"

#include <fcntl.h>
#include <stdatomic.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

struct shm_header {
    uint64_t magic;
    uint32_t version;
    uint32_t capacity;
    uint8_t prepad[48];
    alignas(64) _Atomic uint64_t head;
    alignas(64) _Atomic uint64_t tail;
    uint8_t reserved[56];
};

_Static_assert(sizeof(struct shm_header) == MLA1517_SHM_HEADER_BYTES,
               "shared-memory header must be 128 bytes");

struct mla1517_shm_ring {
    int fd;
    uint8_t *mapping;
    size_t bytes;
    struct shm_header *header;
    MLA1517_State *buffer;
};

static size_t ring_bytes(uint32_t capacity) {
    return MLA1517_SHM_HEADER_BYTES + (size_t)capacity * sizeof(MLA1517_State);
}

mla1517_shm_ring_t *mla1517_shm_open(const char *path, uint32_t capacity) {
    if (!path || capacity == 0 || (capacity & (capacity - 1u)) != 0) return NULL;
    size_t bytes = ring_bytes(capacity);
    int fd = open(path, O_CREAT | O_RDWR | O_CLOEXEC, 0600);
    if (fd < 0) return NULL;
    if (ftruncate(fd, (off_t)bytes) != 0) {
        close(fd);
        return NULL;
    }
    void *mapped = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (mapped == MAP_FAILED) {
        close(fd);
        return NULL;
    }
    mla1517_shm_ring_t *ring = calloc(1, sizeof(*ring));
    if (!ring) {
        munmap(mapped, bytes);
        close(fd);
        return NULL;
    }
    ring->fd = fd;
    ring->mapping = mapped;
    ring->bytes = bytes;
    ring->header = (struct shm_header *)mapped;
    ring->buffer = (MLA1517_State *)(ring->mapping + MLA1517_SHM_HEADER_BYTES);

    if (ring->header->magic == 0) {
        ring->header->magic = MLA1517_SHM_MAGIC;
        ring->header->version = MLA1517_SHM_ABI_VERSION;
        ring->header->capacity = capacity;
        atomic_init(&ring->header->head, 0);
        atomic_init(&ring->header->tail, 0);
    } else if (ring->header->magic != MLA1517_SHM_MAGIC ||
               ring->header->version != MLA1517_SHM_ABI_VERSION ||
               ring->header->capacity != capacity) {
        munmap(ring->mapping, ring->bytes);
        close(ring->fd);
        free(ring);
        return NULL;
    }
    return ring;
}

void mla1517_shm_close(mla1517_shm_ring_t *ring) {
    if (!ring) return;
    if (ring->mapping) munmap(ring->mapping, ring->bytes);
    if (ring->fd >= 0) close(ring->fd);
    free(ring);
}

uint64_t mla1517_shm_space(const mla1517_shm_ring_t *ring) {
    if (!ring) return 0;
    uint64_t head = atomic_load_explicit(&ring->header->head, memory_order_relaxed);
    uint64_t tail = atomic_load_explicit(&ring->header->tail, memory_order_acquire);
    uint64_t used = head - tail;
    return used >= ring->header->capacity ? 0 : ring->header->capacity - used;
}

int mla1517_shm_push(mla1517_shm_ring_t *ring, const MLA1517_State *state) {
    if (!ring || !state) return -1;
    uint64_t head = atomic_load_explicit(&ring->header->head, memory_order_relaxed);
    uint64_t tail = atomic_load_explicit(&ring->header->tail, memory_order_acquire);
    if (head - tail >= ring->header->capacity) return 0;
    ring->buffer[head & (ring->header->capacity - 1u)] = *state;
    atomic_store_explicit(&ring->header->head, head + 1, memory_order_release);
    return 1;
}

int mla1517_shm_pop(mla1517_shm_ring_t *ring, MLA1517_State *state) {
    if (!ring || !state) return -1;
    uint64_t tail = atomic_load_explicit(&ring->header->tail, memory_order_relaxed);
    uint64_t head = atomic_load_explicit(&ring->header->head, memory_order_acquire);
    if (head == tail) return 0;
    *state = ring->buffer[tail & (ring->header->capacity - 1u)];
    atomic_store_explicit(&ring->header->tail, tail + 1, memory_order_release);
    return 1;
}

int mla1517_drain_vault_to_shm(
    mla1517_device_t *device,
    mla1517_shm_ring_t *ring,
    int timeout_ms,
    uint32_t max_records
) {
    if (!device || !ring || max_records == 0) return -1;
    uint32_t drained = 0;
    while (drained < max_records && mla1517_shm_space(ring) > 0) {
        mla1517_vault_record_t record;
        int result = mla1517_poll_vault(
            device, drained == 0 ? timeout_ms : 0, &record
        );
        if (result <= 0) break;
        MLA1517_State state;
        memcpy(&state, record.state, sizeof(state));
        if (mla1517_shm_push(ring, &state) != 1) break;
        ++drained;
    }
    return (int)drained;
}

int mla1517_poll_vault_to_shm(
    mla1517_device_t *device,
    mla1517_shm_ring_t *ring,
    int timeout_ms,
    mla1517_vault_record_t *record
) {
    if (!device || !ring || !record) return -1;
    if (mla1517_shm_space(ring) == 0) return 0;
    int result = mla1517_poll_vault(device, timeout_ms, record);
    if (result <= 0) return result;
    MLA1517_State state;
    memcpy(&state, record->state, sizeof(state));
    if (mla1517_shm_push(ring, &state) != 1) return -1;
    return 1;
}