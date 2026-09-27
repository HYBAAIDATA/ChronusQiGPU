#ifndef MLA1517_TELEMETRY_SHM_H
#define MLA1517_TELEMETRY_SHM_H

#include <stdalign.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MLA1517_TELEMETRY_MAGIC UINT64_C(0x000000005A1A1517)
#define MLA1517_TELEMETRY_VERSION 3u
#define MLA1517_TELEMETRY_PARTITIONS 32u
#define MLA1517_TELEMETRY_QUERY_FAULTS_OFFSET 768u
#define MLA1517_TELEMETRY_RING_OVERFLOWS_OFFSET 832u
#define MLA1517_TELEMETRY_CATASTROPHIC_OVERFLOWS_OFFSET 896u

typedef struct mla1517_telemetry mla1517_telemetry_t;

mla1517_telemetry_t *mla1517_telemetry_open(const char *path);
void mla1517_telemetry_close(mla1517_telemetry_t *telemetry);
void mla1517_telemetry_add_partition(
    mla1517_telemetry_t *telemetry,
    uint32_t partition,
    uint64_t amount
);
void mla1517_telemetry_add_voids(
    mla1517_telemetry_t *telemetry,
    uint64_t amount
);
void mla1517_telemetry_add_accepted(
    mla1517_telemetry_t *telemetry,
    uint64_t amount
);
void mla1517_telemetry_add_fault(
    mla1517_telemetry_t *telemetry,
    uint32_t lane,
    uint64_t amount
);
void mla1517_telemetry_add_drop(
    mla1517_telemetry_t *telemetry,
    uint64_t amount
);
void mla1517_telemetry_add_query_fault(
    mla1517_telemetry_t *telemetry,
    uint64_t amount
);
void mla1517_telemetry_add_ring_overflow(
    mla1517_telemetry_t *telemetry,
    uint64_t amount
);
void mla1517_telemetry_add_catastrophic_overflow(
    mla1517_telemetry_t *telemetry,
    uint64_t amount
);

/*
 * Safe reader/ABI introspection boundary.  The reader performs the seqlock
 * copy in C; Python never reads a live mmap directly.
 */
size_t mla1517_telemetry_size(void);
int mla1517_telemetry_snapshot(
    const char *path,
    void *out,
    size_t out_bytes
);
size_t mla1517_telemetry_offset(uint32_t field_id);

#ifdef __cplusplus
}
#endif

#endif