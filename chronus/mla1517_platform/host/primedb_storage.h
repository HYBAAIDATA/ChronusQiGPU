#ifndef MLA1517_PRIMEDB_STORAGE_H
#define MLA1517_PRIMEDB_STORAGE_H

#include <stdint.h>
#include <stdatomic.h>
#include <stddef.h>

#include "mla1517_shm.h"

#ifdef __cplusplus
extern "C" {
#endif

#define PRIMEDB_VERTEX_COUNT 20u
#define PRIMEDB_STORAGE_ABI_VERSION 1u
#define PRIMEDB_STORAGE_MAGIC UINT64_C(0x5052494D45444231) /* PRIME-DB1 */
#define PRIMEDB_STORAGE_HEADER_BYTES 64u
#define PRIMEDB_CURSOR_MAGIC UINT32_C(0x50444243) /* PDBC */
#define PRIMEDB_CURSOR_VERSION 1u
#define PRIMEDB_CURSOR_BYTES 256u

typedef struct {
    uint32_t magic;
    uint32_t version;
    _Atomic uint64_t seq;
    uint8_t reserved[48];
    _Atomic uint64_t cursors[PRIMEDB_VERTEX_COUNT];
    uint8_t reserved_tail[32];
} primedb_cursors_t;

_Static_assert(offsetof(primedb_cursors_t, cursors) == 64,
               "PRIME-DB cursor array must begin on cache line");
_Static_assert(sizeof(primedb_cursors_t) == PRIMEDB_CURSOR_BYTES,
               "PRIME-DB cursor ABI must be 256 bytes");

typedef struct primedb_storage primedb_storage_t;

typedef int (*primedb_match_callback)(
    uint32_t vertex_id,
    uint64_t slot_id,
    const MLA1517_State *state,
    void *context
);

/*
 * Open exactly twenty vertex files under data_dir:
 *   vertex_00.db ... vertex_19.db
 *
 * Each file contains a fixed-size mapped header followed by capacity 64-byte
 * states.  capacity is explicit to prevent accidental multi-gigabyte mappings.
 */
primedb_storage_t *primedb_storage_open(
    const char *data_dir,
    uint64_t capacity_per_vertex
);
primedb_storage_t *primedb_storage_open_with_cursors(
    const char *data_dir,
    uint64_t capacity_per_vertex,
    const char *cursor_path
);
void primedb_storage_close(primedb_storage_t *storage);

/*
 * Validate D10, route by D7 % 20, write one 64-byte state, then publish the
 * persistent cursor.  Returns 1 committed, 0 rejected, -1 on storage error.
 */
int primedb_storage_commit(
    primedb_storage_t *storage,
    const MLA1517_State *state,
    uint32_t *vertex_id,
    uint64_t *slot_id
);

/* Consume one shared-memory state and commit it to the geometric store. */
int primedb_storage_ingest_once(
    mla1517_shm_ring_t *ring,
    primedb_storage_t *storage,
    uint32_t *vertex_id,
    uint64_t *slot_id
);

/*
 * Scan one vertex for a D5 resonance mask.  The mapped state layout keeps
 * records contiguous and makes this loop suitable for compiler SIMD.
 */
int primedb_storage_query_d5(
    primedb_storage_t *storage,
    uint32_t vertex_id,
    uint32_t mask,
    primedb_match_callback callback,
    void *context,
    uint64_t *matches
);

/* Explicit durability barrier for one mapped vertex. */
int primedb_storage_sync(primedb_storage_t *storage, uint32_t vertex_id);

uint64_t primedb_storage_capacity(const primedb_storage_t *storage);
const char *primedb_storage_cursor_path(const primedb_storage_t *storage);

#ifdef __cplusplus
}
#endif

#endif