#define _GNU_SOURCE

#include "mla1517_aethel.h"

#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

static int fail(const char *message) {
    fprintf(stderr, "FAIL: %s\n", message);
    return 1;
}

int main(void) {
    char mmio_path[] = "/tmp/mla1517-mmio-XXXXXX";
    char aethel_path[] = "/tmp/mla1517-aethel-XXXXXX";
    int mmio_fd = mkstemp(mmio_path);
    int aethel_fd = mkstemp(aethel_path);
    if (mmio_fd < 0 || aethel_fd < 0) return fail("mkstemp");
    close(aethel_fd);

    mla1517_device_t *device = mla1517_open(mmio_path, 0x2000);
    mla1517_shm_ring_t *ring = mla1517_shm_open("/tmp/mla1517-ring-test", 8);
    mla1517_aethel_queue_t *queue = mla1517_aethel_open(aethel_path, 20);
    if (!device || !ring || !queue) return fail("open");

    int result = 0;
    uint8_t *mapped = mmap(NULL, 0x2000, PROT_READ | PROT_WRITE, MAP_SHARED, mmio_fd, 0);
    if (mapped == MAP_FAILED) return fail("map");
    uint8_t state[MLA1517_STATE_BYTES] = {0};
    uint32_t d7 = 14;
    int32_t cassini = -1;
    memcpy(state + MLA1517_AETHEL_D7_OFFSET, &d7, sizeof(d7));
    memcpy(state + MLA1517_AETHEL_D10_OFFSET, &cassini, sizeof(cassini));
    size_t vault = MLA1517_VAULT_BASE + 3u * MLA1517_VAULT_STRIDE;
    uint64_t sequence = 2;
    memcpy(mapped + vault + MLA1517_VAULT_SEQ_OFFSET, &sequence, sizeof(sequence));
    memcpy(mapped + vault + MLA1517_VAULT_STATE_OFFSET, state, sizeof(state));
    if (mla1517_drain_vault_to_shm(device, ring, 0, 1) != 1)
        result = fail("valid state was not committed");
    if (result == 0 && mla1517_aethel_ingest_once(ring, queue) != 1)
        result = fail("ring state was not ingested");

    mla1517_aethel_record_t record;
    if (result == 0 && mla1517_aethel_read(queue, 14, &record) != 1)
        result = fail("slot read");
    if (result == 0 && memcmp(record.state, state, sizeof(state)) != 0)
        result = fail("state mismatch");

    int32_t invalid = 0;
    memcpy(state + MLA1517_AETHEL_D10_OFFSET, &invalid, sizeof(invalid));
    if (mla1517_aethel_commit(queue, state) != 0)
        result = fail("invalid Cassini state committed");

    munmap(mapped, 0x2000);
    mla1517_aethel_close(queue);
    mla1517_shm_close(ring);
    mla1517_close(device);
    close(mmio_fd);
    unlink(mmio_path);
    unlink(aethel_path);
    unlink("/tmp/mla1517-ring-test");
    if (result == 0) {
        puts("{\"status\":\"PASS\",\"path_b\":\"C11_MMIO_TO_AETHEL\",\"d7_slot\":14,\"cassini_gate\":true}");
    }
    return result;
}