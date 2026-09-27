#define _GNU_SOURCE

#include "primedb_storage.h"
#include "telemetry_shm.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <stddef.h>

static int callback_count(
    uint32_t vertex_id,
    uint64_t slot_id,
    const MLA1517_State *state,
    void *context
) {
    (void)vertex_id;
    (void)slot_id;
    if (state->d10_cassini != 1 && state->d10_cassini != -1) return 1;
    *(uint32_t *)context += 1;
    return 0;
}

static int fail(const char *message) {
    fprintf(stderr, "FAIL: %s\n", message);
    return 1;
}

int main(void) {
    char directory[] = "/tmp/mla1517-primedb-XXXXXX";
    if (!mkdtemp(directory)) return fail("mkdtemp");
    char cursor_path[] = "/tmp/mla1517-cursors-XXXXXX";
    int cursor_seed = mkstemp(cursor_path);
    if (cursor_seed < 0) return fail("cursor tempfile");
    close(cursor_seed);
    unlink(cursor_path);
    char telemetry_path[] = "/tmp/mla1517-telemetry-XXXXXX";
    int telemetry_seed = mkstemp(telemetry_path);
    if (telemetry_seed < 0) return fail("telemetry tempfile");
    close(telemetry_seed);
    unlink(telemetry_path);
    setenv("MLA1517_PRIME_DB_MAX_BYTES", "128", 1); /* two 64-byte states */
    setenv("MLA1517_TELEMETRY_PATH", telemetry_path, 1);
    mla1517_telemetry_t *telemetry = mla1517_telemetry_open(telemetry_path);
    primedb_storage_t *storage = primedb_storage_open_with_cursors(directory, 1, cursor_path);
    mla1517_shm_ring_t *ring = mla1517_shm_open("/tmp/mla1517-primedb-ring", 8);
    if (!storage || !ring) return fail("open");

    MLA1517_State state = {0};
    state.d7_prime_addr = 34; /* vertex 14 */
    state.d5_zeckendorf = 0x100;
    state.d10_cassini = -1;
    if (mla1517_shm_push(ring, &state) != 1) return fail("ring push");
    uint32_t vertex = 0;
    uint64_t slot = 0;
    if (primedb_storage_ingest_once(ring, storage, &vertex, &slot) != 1)
        return fail("ingest");
    if (vertex != 14 || slot != 0) return fail("D7 routing");

    uint64_t matches = 0;
    uint32_t callbacks = 0;
    if (primedb_storage_query_d5(
            storage, 14, 0x1, callback_count, &callbacks, &matches) != 0)
        return fail("query");
    if (matches != 1 || callbacks != 1) return fail("resonance query");

    /* The second commit forces sparse-file growth rather than dropping data. */
    state.d10_cassini = 1;
    state.d5_zeckendorf = 0;
    if (primedb_storage_commit(storage, &state, &vertex, &slot) != 1 || slot != 1)
        return fail("growth commit");
    if (primedb_storage_query_d5(storage, 14, 0, NULL, NULL, &matches) != 0 || matches != 2)
        return fail("grown query");

    state.d10_cassini = 0;
    if (primedb_storage_commit(storage, &state, NULL, NULL) != 0)
        return fail("invalid Cassini commit");

    primedb_storage_close(storage);
    storage = primedb_storage_open_with_cursors(directory, 1, cursor_path);
    if (!storage) return fail("reopen");
    if (primedb_storage_query_d5(
            storage, 14, 0x1, NULL, NULL, &matches) != 0 || matches != 2)
        return fail("reopen recovery");

    /* Corrupt one persisted slot; query-time Cassini validation must filter it. */
    char vertex_path[4096];
    snprintf(vertex_path, sizeof(vertex_path), "%s/vertex_14.db", directory);
    int vertex_fd = open(vertex_path, O_RDWR);
    int32_t invalid = 0;
    if (vertex_fd < 0 || pwrite(vertex_fd, &invalid,
            sizeof(invalid),
            (off_t)(PRIMEDB_STORAGE_HEADER_BYTES + sizeof(MLA1517_State) +
                    offsetof(MLA1517_State, d10_cassini))) != sizeof(invalid))
        return fail("corrupt persisted slot");
    close(vertex_fd);
    if (primedb_storage_query_d5(storage, 14, 0, NULL, NULL, &matches) != 0 || matches != 1)
        return fail("query Cassini recheck");
    unsigned char telemetry_snapshot[960] = {0};
    if (mla1517_telemetry_snapshot(telemetry_path, telemetry_snapshot,
                                   sizeof(telemetry_snapshot)) != 0 ||
        *(uint64_t *)(telemetry_snapshot + 768) == 0)
        return fail("query fault telemetry");
    primedb_storage_close(storage);
    mla1517_shm_close(ring);
    unlink("/tmp/mla1517-primedb-ring");
    mla1517_telemetry_close(telemetry);
    unlink(cursor_path);
    unlink(telemetry_path);
    unsetenv("MLA1517_PRIME_DB_MAX_BYTES");
    unsetenv("MLA1517_TELEMETRY_PATH");
    char path[4096];
    for (uint32_t i = 0; i < PRIMEDB_VERTEX_COUNT; ++i) {
        snprintf(path, sizeof(path), "%s/vertex_%02u.db", directory, i);
        unlink(path);
    }
    rmdir(directory);
    puts("{\"status\":\"PASS\",\"vertices\":20,\"d7_vertex\":14,\"reopen_recovery\":true,\"growth\":true,\"query_cassini_gate\":true}");
    return 0;
}