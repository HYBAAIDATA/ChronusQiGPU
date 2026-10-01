#define _GNU_SOURCE

#include "telemetry_shm.h"

#include <fcntl.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

struct telemetry_map {
    uint64_t magic;
    uint32_t version;
    uint32_t reserved;
    _Atomic uint64_t seq;
    uint8_t prepad[40];
    alignas(64) _Atomic uint64_t partition_tests[MLA1517_TELEMETRY_PARTITIONS];
    alignas(64) _Atomic uint64_t topological_voids;
    alignas(64) _Atomic uint64_t stratum_accepted;
    alignas(64) _Atomic uint64_t cassini_faults[MLA1517_TELEMETRY_PARTITIONS];
    alignas(64) _Atomic uint64_t stratum_drops;
    alignas(64) _Atomic uint64_t query_cassini_faults;
    alignas(64) _Atomic uint64_t ring_overflows;
    alignas(64) _Atomic uint64_t catastrophic_overflows;
};

_Static_assert(offsetof(struct telemetry_map, partition_tests) == 64,
               "telemetry partition offset");
_Static_assert(offsetof(struct telemetry_map, topological_voids) == 320,
               "telemetry void offset");
_Static_assert(offsetof(struct telemetry_map, stratum_accepted) == 384,
               "telemetry accepted offset");
_Static_assert(offsetof(struct telemetry_map, cassini_faults) == 448,
               "telemetry fault offset");
_Static_assert(offsetof(struct telemetry_map, stratum_drops) == 704,
               "telemetry drop offset");
_Static_assert(offsetof(struct telemetry_map, query_cassini_faults) == 768,
               "telemetry query fault offset");
_Static_assert(offsetof(struct telemetry_map, ring_overflows) == 832,
               "telemetry overflow offset");
_Static_assert(offsetof(struct telemetry_map, catastrophic_overflows) == 896,
               "telemetry catastrophic overflow offset");
_Static_assert(sizeof(struct telemetry_map) == 960,
               "telemetry ABI size");

struct mla1517_telemetry {
    int fd;
    size_t bytes;
    struct telemetry_map *map;
};

mla1517_telemetry_t *mla1517_telemetry_open(const char *path) {
    if (!path) return NULL;
    int fd = open(path, O_CREAT | O_RDWR | O_CLOEXEC, 0600);
    if (fd < 0) return NULL;
    size_t bytes = sizeof(struct telemetry_map);
    if (ftruncate(fd, (off_t)bytes) != 0) {
        close(fd);
        return NULL;
    }
    void *mapping = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (mapping == MAP_FAILED) {
        close(fd);
        return NULL;
    }
    mla1517_telemetry_t *telemetry = calloc(1, sizeof(*telemetry));
    if (!telemetry) {
        munmap(mapping, bytes);
        close(fd);
        return NULL;
    }
    telemetry->fd = fd;
    telemetry->bytes = bytes;
    telemetry->map = mapping;
    if (telemetry->map->magic == 0) {
        telemetry->map->magic = MLA1517_TELEMETRY_MAGIC;
        telemetry->map->version = MLA1517_TELEMETRY_VERSION;
        atomic_init(&telemetry->map->seq, 0);
        for (uint32_t i = 0; i < MLA1517_TELEMETRY_PARTITIONS; ++i)
            atomic_init(&telemetry->map->partition_tests[i], 0);
        atomic_init(&telemetry->map->topological_voids, 0);
        atomic_init(&telemetry->map->stratum_accepted, 0);
        for (uint32_t i = 0; i < MLA1517_TELEMETRY_PARTITIONS; ++i)
            atomic_init(&telemetry->map->cassini_faults[i], 0);
        atomic_init(&telemetry->map->stratum_drops, 0);
        atomic_init(&telemetry->map->query_cassini_faults, 0);
        atomic_init(&telemetry->map->ring_overflows, 0);
        atomic_init(&telemetry->map->catastrophic_overflows, 0);
    } else if (telemetry->map->magic != MLA1517_TELEMETRY_MAGIC ||
               telemetry->map->version != MLA1517_TELEMETRY_VERSION) {
        munmap(mapping, bytes);
        close(fd);
        free(telemetry);
        return NULL;
    }
    return telemetry;
}

static void telemetry_write_begin(struct telemetry_map *map) {
    atomic_fetch_add_explicit(&map->seq, 1, memory_order_acq_rel);
}

static void telemetry_write_end(struct telemetry_map *map) {
    atomic_fetch_add_explicit(&map->seq, 1, memory_order_release);
}

void mla1517_telemetry_close(mla1517_telemetry_t *telemetry) {
    if (!telemetry) return;
    munmap(telemetry->map, telemetry->bytes);
    close(telemetry->fd);
    free(telemetry);
}

void mla1517_telemetry_add_partition(
    mla1517_telemetry_t *telemetry,
    uint32_t partition,
    uint64_t amount
) {
    if (!telemetry || partition >= MLA1517_TELEMETRY_PARTITIONS) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(
        &telemetry->map->partition_tests[partition], amount, memory_order_relaxed
    );
    telemetry_write_end(telemetry->map);
}

void mla1517_telemetry_add_voids(
    mla1517_telemetry_t *telemetry,
    uint64_t amount
) {
    if (!telemetry) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(
        &telemetry->map->topological_voids, amount, memory_order_relaxed
    );
    telemetry_write_end(telemetry->map);
}

void mla1517_telemetry_add_accepted(
    mla1517_telemetry_t *telemetry,
    uint64_t amount
) {
    if (!telemetry) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(
        &telemetry->map->stratum_accepted, amount, memory_order_relaxed
    );
    telemetry_write_end(telemetry->map);
}

void mla1517_telemetry_add_fault(
    mla1517_telemetry_t *telemetry,
    uint32_t lane,
    uint64_t amount
) {
    if (!telemetry || lane >= MLA1517_TELEMETRY_PARTITIONS) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(
        &telemetry->map->cassini_faults[lane], amount, memory_order_relaxed
    );
    telemetry_write_end(telemetry->map);
}

void mla1517_telemetry_add_drop(
    mla1517_telemetry_t *telemetry,
    uint64_t amount
) {
    if (!telemetry) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(
        &telemetry->map->stratum_drops, amount, memory_order_relaxed
    );
    telemetry_write_end(telemetry->map);
}

static void telemetry_add_counter(
    mla1517_telemetry_t *telemetry,
    _Atomic uint64_t *counter,
    uint64_t amount
) {
    if (!telemetry) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(counter, amount, memory_order_relaxed);
    telemetry_write_end(telemetry->map);
}

void mla1517_telemetry_add_query_fault(
    mla1517_telemetry_t *telemetry,
    uint64_t amount
) {
    if (!telemetry) return;
    telemetry_add_counter(telemetry, &telemetry->map->query_cassini_faults, amount);
}

void mla1517_telemetry_add_ring_overflow(
    mla1517_telemetry_t *telemetry,
    uint64_t amount
) {
    if (!telemetry) return;
    telemetry_add_counter(telemetry, &telemetry->map->ring_overflows, amount);
}

void mla1517_telemetry_add_catastrophic_overflow(
    mla1517_telemetry_t *telemetry,
    uint64_t amount
) {
    if (!telemetry) return;
    telemetry_add_counter(
        telemetry, &telemetry->map->catastrophic_overflows, amount
    );
}

size_t mla1517_telemetry_size(void) {
    return sizeof(struct telemetry_map);
}

size_t mla1517_telemetry_offset(uint32_t field_id) {
    switch (field_id) {
        case 0: return offsetof(struct telemetry_map, magic);
        case 1: return offsetof(struct telemetry_map, version);
        case 2: return offsetof(struct telemetry_map, seq);
        case 3: return offsetof(struct telemetry_map, partition_tests);
        case 4: return offsetof(struct telemetry_map, topological_voids);
        case 5: return offsetof(struct telemetry_map, stratum_accepted);
        case 6: return offsetof(struct telemetry_map, cassini_faults);
        case 7: return offsetof(struct telemetry_map, stratum_drops);
        case 8: return offsetof(struct telemetry_map, query_cassini_faults);
        case 9: return offsetof(struct telemetry_map, ring_overflows);
        case 10: return offsetof(struct telemetry_map, catastrophic_overflows);
        default: return SIZE_MAX;
    }
}

int mla1517_telemetry_snapshot(
    const char *path,
    void *out,
    size_t out_bytes
) {
    if (!path || !out || out_bytes < sizeof(struct telemetry_map)) return -1;
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return -1;
    void *mapping = mmap(
        NULL, sizeof(struct telemetry_map), PROT_READ, MAP_SHARED, fd, 0
    );
    if (mapping == MAP_FAILED) {
        close(fd);
        return -1;
    }
    const struct telemetry_map *source = mapping;
    int result = -2;
    for (unsigned attempt = 0; attempt < 1000; ++attempt) {
        uint64_t s0 = atomic_load_explicit(&source->seq, memory_order_acquire);
        if (s0 & 1u) continue;
        memcpy(out, source, sizeof(struct telemetry_map));
        uint64_t s1 = atomic_load_explicit(&source->seq, memory_order_acquire);
        if (s0 == s1) {
            result = 0;
            break;
        }
    }
    munmap(mapping, sizeof(struct telemetry_map));
    close(fd);
    return result;
}