#define _GNU_SOURCE

#include "primedb_storage.h"

#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static volatile sig_atomic_t keep_running = 1;

static void stop_daemon(int signal_number) {
    (void)signal_number;
    keep_running = 0;
}

static uint64_t env_u64(const char *name, uint64_t fallback) {
    const char *value = getenv(name);
    if (!value || !*value) return fallback;
    char *end = NULL;
    unsigned long long parsed = strtoull(value, &end, 0);
    return end && *end == '\0' ? (uint64_t)parsed : fallback;
}

int main(void) {
    const char *ring_path = getenv("MLA1517_PRIME_DB_RING");
    const char *overflow_path = getenv("MLA1517_PRIME_DB_OVERFLOW");
    const char *data_dir = getenv("MLA1517_PRIME_DB_DIR");
    if (!ring_path || !data_dir) {
        fprintf(stderr, "Set MLA1517_PRIME_DB_RING and MLA1517_PRIME_DB_DIR\n");
        return 2;
    }
    uint64_t capacity = env_u64("MLA1517_PRIME_DB_CAPACITY", 4096);
    uint64_t sync_every = env_u64("MLA1517_PRIME_DB_SYNC_EVERY", 0);
    mla1517_shm_ring_t *ring = mla1517_shm_open(
        ring_path, MLA1517_SHM_CAPACITY
    );
    mla1517_shm_ring_t *overflow = mla1517_shm_open(
        overflow_path && *overflow_path ? overflow_path : "/dev/shm/mla1517_overflow",
        1u << 20
    );
    primedb_storage_t *storage = primedb_storage_open(data_dir, capacity);
    if (!ring || !overflow || !storage) {
        fprintf(stderr, "Unable to open Aethel ring or PRIME-DB storage\n");
        mla1517_shm_close(ring);
        mla1517_shm_close(overflow);
        primedb_storage_close(storage);
        return 1;
    }
    signal(SIGINT, stop_daemon);
    signal(SIGTERM, stop_daemon);
    uint64_t committed = 0;
    while (keep_running) {
        uint32_t vertex = 0;
        uint64_t slot = 0;
        int result = primedb_storage_ingest_once(overflow, storage, &vertex, &slot);
        if (result == 0) result = primedb_storage_ingest_once(ring, storage, &vertex, &slot);
        if (result == 1) {
            ++committed;
            if (sync_every > 0 && committed % sync_every == 0 &&
                primedb_storage_sync(storage, vertex) != 0) {
                fprintf(stderr, "PRIME-DB durability barrier failed for vertex %u\n", vertex);
                break;
            }
        } else if (result == -1) {
            fprintf(stderr, "PRIME-DB storage failure\n");
            break;
        } else if (result == -2) {
            fprintf(stderr, "PRIME-DB rejected state: invalid Cassini seal or full vertex\n");
        } else {
            struct timespec delay = {.tv_sec = 0, .tv_nsec = 1000000L};
            nanosleep(&delay, NULL);
        }
    }
    if (committed > 0 && sync_every == 0) {
        for (uint32_t vertex = 0; vertex < PRIMEDB_VERTEX_COUNT; ++vertex)
            (void)primedb_storage_sync(storage, vertex);
    }
    printf("{\"status\":\"STOPPED\",\"committed\":%llu}\n",
           (unsigned long long)committed);
    primedb_storage_close(storage);
    mla1517_shm_close(ring);
    mla1517_shm_close(overflow);
    return 0;
}