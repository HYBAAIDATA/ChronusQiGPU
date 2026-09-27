#ifndef MLA1517_AETHEL_H
#define MLA1517_AETHEL_H

/*
 * Aethel shared-memory ingestion ABI v1.
 *
 * This is the native C boundary between the MMIO driver and PRIME-DB.  It
 * removes Python/JSON/IPC from the hot ingestion path while retaining an
 * explicit sequence publication protocol for readers.
 */

#include <stdint.h>

#include "mla1517_mmio.h"
#include "mla1517_shm.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MLA1517_AETHEL_ABI_VERSION 1u
#define MLA1517_AETHEL_MAGIC UINT64_C(0x4D4C413135313741) /* MLA1517A */
#define MLA1517_AETHEL_HEADER_BYTES 0x40u
#define MLA1517_AETHEL_SLOT_STRIDE 0x80u
#define MLA1517_AETHEL_D7_OFFSET 28u
#define MLA1517_AETHEL_D10_OFFSET 40u

typedef struct mla1517_aethel_queue mla1517_aethel_queue_t;

typedef struct {
    uint32_t slot_id;
    uint64_t sequence;
    uint8_t state[MLA1517_STATE_BYTES];
} mla1517_aethel_record_t;

/*
 * Open or create an explicitly named mmap-backed Aethel region.  The path
 * should normally be under /dev/shm or a controlled persistent data volume.
 */
mla1517_aethel_queue_t *mla1517_aethel_open(
    const char *path,
    uint32_t slot_count
);
void mla1517_aethel_close(mla1517_aethel_queue_t *queue);

/*
 * Commit one state to the D7-selected slot.  Returns:
 *   1 committed
 *   0 rejected by Cassini or invalid slot
 *  -1 I/O/argument failure
 */
int mla1517_aethel_commit(
    mla1517_aethel_queue_t *queue,
    const uint8_t state[MLA1517_STATE_BYTES]
);

/*
 * Read a stable snapshot from one slot.  Returns 1 when a committed record
 * exists, 0 when empty/unstable, and -1 for invalid arguments.
 */
int mla1517_aethel_read(
    mla1517_aethel_queue_t *queue,
    uint32_t slot_id,
    mla1517_aethel_record_t *record
);

/* PRIME-DB consumer: pop one shared state, apply Cassini, route by D7. */
int mla1517_aethel_ingest_once(
    mla1517_shm_ring_t *ring,
    mla1517_aethel_queue_t *queue
);

/*
 * Path B: drain committed hardware winners directly into Aethel.  Path A
 * remains available through mla1517_poll_vault() for the Python/Stratum
 * control path.  No Python serialization occurs here.
 */
int mla1517_drain_vault_to_aethel(
    mla1517_device_t *device,
    mla1517_aethel_queue_t *queue,
    int timeout_ms,
    uint32_t max_records
);

#ifdef __cplusplus
}
#endif

#endif