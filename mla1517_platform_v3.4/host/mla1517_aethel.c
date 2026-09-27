#define _GNU_SOURCE

#include "mla1517_aethel.h"

#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

struct aethel_header {
    uint64_t magic;
    uint32_t version;
    uint32_t slot_count;
    uint64_t reserved[6];
};

struct mla1517_aethel_queue {
    int fd;
    uint8_t *mapping;
    size_t bytes;
    struct aethel_header *header;
};

static size_t region_bytes(uint32_t slot_count) {
    return MLA1517_AETHEL_HEADER_BYTES +
           (size_t)slot_count * MLA1517_AETHEL_SLOT_STRIDE;
}

static uint8_t *slot_base(
    const mla1517_aethel_queue_t *queue,
    uint32_t slot_id
) {
    return queue->mapping + MLA1517_AETHEL_HEADER_BYTES +
           (size_t)slot_id * MLA1517_AETHEL_SLOT_STRIDE;
}

static int cassini_valid(const uint8_t state[MLA1517_STATE_BYTES]) {
    int32_t seal = 0;
    memcpy(&seal, state + MLA1517_AETHEL_D10_OFFSET, sizeof(seal));
    return seal == 1 || seal == -1;
}

mla1517_aethel_queue_t *mla1517_aethel_open(
    const char *path,
    uint32_t slot_count
) {
    if (!path || slot_count == 0) return NULL;
    size_t bytes = region_bytes(slot_count);
    int fd = open(path, O_RDWR | O_CREAT | O_CLOEXEC, 0600);
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
    mla1517_aethel_queue_t *queue = calloc(1, sizeof(*queue));
    if (!queue) {
        munmap(mapped, bytes);
        close(fd);
        return NULL;
    }
    queue->fd = fd;
    queue->mapping = mapped;
    queue->bytes = bytes;
    queue->header = (struct aethel_header *)mapped;

    if (queue->header->magic == 0) {
        queue->header->magic = MLA1517_AETHEL_MAGIC;
        queue->header->version = MLA1517_AETHEL_ABI_VERSION;
        queue->header->slot_count = slot_count;
        (void)msync(queue->mapping, MLA1517_AETHEL_HEADER_BYTES, MS_SYNC);
    } else if (queue->header->magic != MLA1517_AETHEL_MAGIC ||
               queue->header->version != MLA1517_AETHEL_ABI_VERSION ||
               queue->header->slot_count != slot_count) {
        munmap(queue->mapping, queue->bytes);
        close(queue->fd);
        free(queue);
        return NULL;
    }
    return queue;
}

void mla1517_aethel_close(mla1517_aethel_queue_t *queue) {
    if (!queue) return;
    if (queue->mapping) munmap(queue->mapping, queue->bytes);
    if (queue->fd >= 0) close(queue->fd);
    free(queue);
}

int mla1517_aethel_commit(
    mla1517_aethel_queue_t *queue,
    const uint8_t state[MLA1517_STATE_BYTES]
) {
    if (!queue || !state || !cassini_valid(state)) return 0;
    uint32_t d7 = 0;
    memcpy(&d7, state + MLA1517_AETHEL_D7_OFFSET, sizeof(d7));
    uint32_t slot_id = d7 % queue->header->slot_count;
    uint8_t *base = slot_base(queue, slot_id);
    volatile uint64_t *sequence = (volatile uint64_t *)base;
    uint64_t current = __atomic_load_n(sequence, __ATOMIC_ACQUIRE);
    uint64_t next = current + 2u;
    if (next == 0) next = 2u;
    __atomic_store_n(sequence, next - 1u, __ATOMIC_RELEASE);
    memcpy(base + sizeof(uint64_t), state, MLA1517_STATE_BYTES);
    __atomic_store_n(sequence, next, __ATOMIC_RELEASE);
    return 1;
}

int mla1517_aethel_read(
    mla1517_aethel_queue_t *queue,
    uint32_t slot_id,
    mla1517_aethel_record_t *record
) {
    if (!queue || !record || slot_id >= queue->header->slot_count) return -1;
    uint8_t *base = slot_base(queue, slot_id);
    volatile uint64_t *sequence = (volatile uint64_t *)base;
    uint64_t seq1 = __atomic_load_n(sequence, __ATOMIC_ACQUIRE);
    if (seq1 == 0 || (seq1 & 1u)) return 0;
    uint8_t snapshot[MLA1517_STATE_BYTES];
    memcpy(snapshot, base + sizeof(uint64_t), MLA1517_STATE_BYTES);
    uint64_t seq2 = __atomic_load_n(sequence, __ATOMIC_ACQUIRE);
    if (seq1 != seq2 || (seq2 & 1u)) return 0;
    record->slot_id = slot_id;
    record->sequence = seq2;
    memcpy(record->state, snapshot, MLA1517_STATE_BYTES);
    return 1;
}

int mla1517_aethel_ingest_once(
    mla1517_shm_ring_t *ring,
    mla1517_aethel_queue_t *queue
) {
    if (!ring || !queue) return -1;
    MLA1517_State state;
    int popped = mla1517_shm_pop(ring, &state);
    if (popped <= 0) return popped;
    int committed = mla1517_aethel_commit(
        queue, (const uint8_t *)&state
    );
    return committed > 0 ? 1 : -2;
}

int mla1517_drain_vault_to_aethel(
    mla1517_device_t *device,
    mla1517_aethel_queue_t *queue,
    int timeout_ms,
    uint32_t max_records
) {
    if (!device || !queue || max_records == 0) return -1;
    uint32_t committed = 0;
    while (committed < max_records) {
        mla1517_vault_record_t record;
        int result = mla1517_poll_vault(
            device,
            committed == 0 ? timeout_ms : 0,
            &record
        );
        if (result <= 0) break;
        int commit_result = mla1517_aethel_commit(queue, record.state);
        if (commit_result < 0) return -1;
        if (commit_result > 0) ++committed;
    }
    return (int)committed;
}