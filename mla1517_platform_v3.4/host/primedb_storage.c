#define _GNU_SOURCE

#include "primedb_storage.h"
#include "telemetry_shm.h"

#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

struct vertex_header {
    uint64_t magic;
    uint32_t version;
    uint32_t vertex_id;
    uint64_t capacity;
    uint64_t head_cursor;
    uint8_t reserved[32];
};

_Static_assert(sizeof(struct vertex_header) == PRIMEDB_STORAGE_HEADER_BYTES,
               "PRIME-DB vertex header must be 64 bytes");

struct vertex {
    int fd;
    size_t bytes;
    uint64_t capacity;
    uint8_t *mapping;
    struct vertex_header *header;
    MLA1517_State *states;
};

struct primedb_storage {
    uint64_t capacity;
    int cursor_fd;
    char *cursor_path;
    primedb_cursors_t *cursors;
    char *data_dir;
    mla1517_telemetry_t *telemetry;
    struct vertex vertices[PRIMEDB_VERTEX_COUNT];
};

#define PRIMEDB_DEFAULT_CURSOR_PATH "/dev/shm/primedb_cursors"
#define PRIMEDB_DEFAULT_MAX_BYTES (UINT64_C(256) * 1024u * 1024u * 1024u)

static int cassini_valid(const MLA1517_State *state) {
    return state && (state->d10_cassini == 1 || state->d10_cassini == -1);
}

static size_t vertex_bytes(uint64_t capacity) {
    return PRIMEDB_STORAGE_HEADER_BYTES + capacity * sizeof(MLA1517_State);
}

static uint64_t max_capacity(void) {
    const char *value = getenv("MLA1517_PRIME_DB_MAX_BYTES");
    if (!value || !*value) return PRIMEDB_DEFAULT_MAX_BYTES / sizeof(MLA1517_State);
    char *end = NULL;
    unsigned long long parsed = strtoull(value, &end, 0);
    if (!end || *end != '\0' || parsed < sizeof(MLA1517_State))
        return PRIMEDB_DEFAULT_MAX_BYTES / sizeof(MLA1517_State);
    return parsed / sizeof(MLA1517_State);
}

static int init_cursors(
    primedb_storage_t *storage,
    const char *cursor_path
) {
    storage->cursor_fd = open(
        cursor_path, O_CREAT | O_RDWR | O_CLOEXEC, 0600
    );
    if (storage->cursor_fd < 0) return -1;
    if (ftruncate(storage->cursor_fd, PRIMEDB_CURSOR_BYTES) != 0) return -1;
    void *mapping = mmap(
        NULL, PRIMEDB_CURSOR_BYTES, PROT_READ | PROT_WRITE,
        MAP_SHARED, storage->cursor_fd, 0
    );
    if (mapping == MAP_FAILED) return -1;
    storage->cursors = mapping;
    if (storage->cursors->magic == 0) {
        storage->cursors->magic = PRIMEDB_CURSOR_MAGIC;
        storage->cursors->version = PRIMEDB_CURSOR_VERSION;
        atomic_init(&storage->cursors->seq, 0);
        for (uint32_t i = 0; i < PRIMEDB_VERTEX_COUNT; ++i)
            atomic_init(&storage->cursors->cursors[i], 0);
        if (msync(mapping, PRIMEDB_CURSOR_BYTES, MS_SYNC) != 0) return -1;
    } else if (storage->cursors->magic != PRIMEDB_CURSOR_MAGIC ||
               storage->cursors->version != PRIMEDB_CURSOR_VERSION) {
        return -1;
    }
    storage->cursor_path = strdup(cursor_path);
    return storage->cursor_path ? 0 : -1;
}

static uint64_t recover_head_cursor(const struct vertex *vertex) {
    uint64_t count = vertex->header->head_cursor;
    if (count > vertex->capacity) count = vertex->capacity;
    while (count > 0 && !cassini_valid(&vertex->states[count - 1]))
        --count;
    return count;
}

static int grow_vertex(struct vertex *vertex, uint64_t new_capacity) {
    if (!vertex || new_capacity <= vertex->capacity) return -1;
    size_t new_bytes = vertex_bytes(new_capacity);
    if (ftruncate(vertex->fd, (off_t)new_bytes) != 0) return -1;
    uint8_t *new_mapping = mmap(
        NULL, new_bytes, PROT_READ | PROT_WRITE, MAP_SHARED, vertex->fd, 0
    );
    if (new_mapping == MAP_FAILED) return -1;
    munmap(vertex->mapping, vertex->bytes);
    vertex->mapping = new_mapping;
    vertex->bytes = new_bytes;
    vertex->capacity = new_capacity;
    vertex->header = (struct vertex_header *)new_mapping;
    vertex->states = (MLA1517_State *)(
        new_mapping + PRIMEDB_STORAGE_HEADER_BYTES
    );
    vertex->header->capacity = new_capacity;
    return 0;
}

static int ensure_directory(const char *path) {
    struct stat st;
    if (stat(path, &st) == 0) return S_ISDIR(st.st_mode) ? 0 : -1;
    return mkdir(path, 0700);
}

static void close_vertex(struct vertex *vertex) {
    if (!vertex) return;
    if (vertex->mapping) munmap(vertex->mapping, vertex->bytes);
    if (vertex->fd >= 0) close(vertex->fd);
    memset(vertex, 0, sizeof(*vertex));
    vertex->fd = -1;
}

primedb_storage_t *primedb_storage_open(
    const char *data_dir,
    uint64_t capacity_per_vertex
) {
    const char *cursor_path = getenv("MLA1517_PRIME_DB_CURSORS");
    return primedb_storage_open_with_cursors(
        data_dir, capacity_per_vertex,
        cursor_path && *cursor_path ? cursor_path : PRIMEDB_DEFAULT_CURSOR_PATH
    );
}

primedb_storage_t *primedb_storage_open_with_cursors(
    const char *data_dir,
    uint64_t capacity_per_vertex,
    const char *cursor_path
) {
    if (!data_dir || capacity_per_vertex == 0 ||
        capacity_per_vertex > (SIZE_MAX - PRIMEDB_STORAGE_HEADER_BYTES) /
                                  sizeof(MLA1517_State)) {
        return NULL;
    }
    if (ensure_directory(data_dir) != 0) return NULL;
    primedb_storage_t *storage = calloc(1, sizeof(*storage));
    if (!storage) return NULL;
    storage->cursor_fd = -1;
    for (uint32_t i = 0; i < PRIMEDB_VERTEX_COUNT; ++i)
        storage->vertices[i].fd = -1;
    storage->capacity = capacity_per_vertex;
    storage->data_dir = strdup(data_dir);
    if (!storage->data_dir) {
        free(storage);
        return NULL;
    }
    if (init_cursors(storage, cursor_path) != 0) goto fail;
    const char *telemetry_path = getenv("MLA1517_TELEMETRY_PATH");
    if (telemetry_path && *telemetry_path)
        storage->telemetry = mla1517_telemetry_open(telemetry_path);
    for (uint32_t vertex_id = 0; vertex_id < PRIMEDB_VERTEX_COUNT; ++vertex_id) {
        char path[4096];
        int written = snprintf(
            path, sizeof(path), "%s/vertex_%02u.db", data_dir, vertex_id
        );
        if (written < 0 || (size_t)written >= sizeof(path)) goto fail;
        struct vertex *vertex = &storage->vertices[vertex_id];
        vertex->fd = open(path, O_CREAT | O_RDWR | O_CLOEXEC, 0600);
        if (vertex->fd < 0) goto fail;
        uint64_t file_capacity = capacity_per_vertex;
        struct vertex_header existing = {0};
        ssize_t header_read = pread(
            vertex->fd, &existing, sizeof(existing), 0
        );
        if (header_read == (ssize_t)sizeof(existing) &&
            existing.magic == PRIMEDB_STORAGE_MAGIC &&
            existing.version == PRIMEDB_STORAGE_ABI_VERSION &&
            existing.vertex_id == vertex_id &&
            existing.capacity >= capacity_per_vertex) {
            file_capacity = existing.capacity;
        }
        vertex->bytes = vertex_bytes(file_capacity);
        vertex->capacity = file_capacity;
        if (ftruncate(vertex->fd, (off_t)vertex->bytes) != 0) goto fail;
        vertex->mapping = mmap(
            NULL, vertex->bytes, PROT_READ | PROT_WRITE, MAP_SHARED, vertex->fd, 0
        );
        if (vertex->mapping == MAP_FAILED) {
            vertex->mapping = NULL;
            goto fail;
        }
        vertex->header = (struct vertex_header *)vertex->mapping;
        vertex->states = (MLA1517_State *)(
            vertex->mapping + PRIMEDB_STORAGE_HEADER_BYTES
        );
        if (vertex->header->magic == 0) {
            vertex->header->magic = PRIMEDB_STORAGE_MAGIC;
            vertex->header->version = PRIMEDB_STORAGE_ABI_VERSION;
            vertex->header->vertex_id = vertex_id;
            vertex->header->capacity = file_capacity;
            __atomic_store_n(&vertex->header->head_cursor, 0, __ATOMIC_RELEASE);
            if (msync(vertex->mapping, PRIMEDB_STORAGE_HEADER_BYTES, MS_SYNC) != 0)
                goto fail;
        } else if (vertex->header->magic != PRIMEDB_STORAGE_MAGIC ||
                   vertex->header->version != PRIMEDB_STORAGE_ABI_VERSION ||
                   vertex->header->vertex_id != vertex_id ||
                   vertex->header->capacity != file_capacity ||
                   vertex->header->head_cursor > file_capacity) {
            goto fail;
        }
        uint64_t recovered = recover_head_cursor(vertex);
        __atomic_store_n(
            &storage->cursors->cursors[vertex_id], recovered, __ATOMIC_RELEASE
        );
    }
    return storage;

fail:
    for (uint32_t i = 0; i < PRIMEDB_VERTEX_COUNT; ++i)
        close_vertex(&storage->vertices[i]);
    if (storage->cursors) munmap(storage->cursors, PRIMEDB_CURSOR_BYTES);
    if (storage->cursor_fd >= 0) close(storage->cursor_fd);
    mla1517_telemetry_close(storage->telemetry);
    free(storage->cursor_path);
    free(storage->data_dir);
    free(storage);
    return NULL;
}

void primedb_storage_close(primedb_storage_t *storage) {
    if (!storage) return;
    for (uint32_t i = 0; i < PRIMEDB_VERTEX_COUNT; ++i)
        close_vertex(&storage->vertices[i]);
    if (storage->cursors) munmap(storage->cursors, PRIMEDB_CURSOR_BYTES);
    if (storage->cursor_fd >= 0) close(storage->cursor_fd);
    mla1517_telemetry_close(storage->telemetry);
    free(storage->cursor_path);
    free(storage->data_dir);
    free(storage);
}

int primedb_storage_commit(
    primedb_storage_t *storage,
    const MLA1517_State *state,
    uint32_t *vertex_id,
    uint64_t *slot_id
) {
    if (!storage || !cassini_valid(state)) return 0;
    uint32_t vertex = state->d7_prime_addr % PRIMEDB_VERTEX_COUNT;
    struct vertex *target = &storage->vertices[vertex];
    uint64_t slot = __atomic_load_n(
        &storage->cursors->cursors[vertex], __ATOMIC_ACQUIRE
    );
    if (slot >= target->capacity) {
        uint64_t limit = max_capacity();
        uint64_t next = target->capacity > limit / 2
            ? limit
            : target->capacity * 2;
        if (next <= target->capacity || grow_vertex(target, next) != 0)
            return -1;
    }
    __atomic_fetch_add(&storage->cursors->seq, 1, __ATOMIC_ACQ_REL);
    target->states[slot] = *state;
    /*
     * The single PRIME-DB ingestion consumer publishes the cursor only after
     * the 64-byte state is written.  Readers therefore never scan an
     * uncommitted slot.  msync is intentionally explicit and configurable at
     * the service layer; mmap visibility is not the same as NVMe durability.
     */
    __atomic_store_n(&target->header->head_cursor, slot + 1, __ATOMIC_RELEASE);
    __atomic_store_n(
        &storage->cursors->cursors[vertex], slot + 1, __ATOMIC_RELEASE
    );
    __atomic_fetch_add(&storage->cursors->seq, 1, __ATOMIC_RELEASE);
    if (vertex_id) *vertex_id = vertex;
    if (slot_id) *slot_id = slot;
    return 1;
}

int primedb_storage_ingest_once(
    mla1517_shm_ring_t *ring,
    primedb_storage_t *storage,
    uint32_t *vertex_id,
    uint64_t *slot_id
) {
    if (!ring || !storage) return -1;
    MLA1517_State state;
    int popped = mla1517_shm_pop(ring, &state);
    if (popped <= 0) return popped;
    int committed = primedb_storage_commit(storage, &state, vertex_id, slot_id);
    if (committed == 1) return 1;
    if (committed == 0) return -2;
    return -1;
}

int primedb_storage_query_d5(
    primedb_storage_t *storage,
    uint32_t vertex_id,
    uint32_t mask,
    primedb_match_callback callback,
    void *context,
    uint64_t *matches
) {
    if (!storage || vertex_id >= PRIMEDB_VERTEX_COUNT) return -1;
    struct vertex *vertex = &storage->vertices[vertex_id];
    uint64_t count = 0;
    for (unsigned attempt = 0; attempt < 1000; ++attempt) {
        uint64_t seq1 = __atomic_load_n(
            &storage->cursors->seq, __ATOMIC_ACQUIRE
        );
        if (seq1 & 1u) continue;
        count = __atomic_load_n(
            &storage->cursors->cursors[vertex_id], __ATOMIC_ACQUIRE
        );
        uint64_t seq2 = __atomic_load_n(
            &storage->cursors->seq, __ATOMIC_ACQUIRE
        );
        if (seq1 == seq2) break;
    }
    if (count > vertex->capacity) count = vertex->capacity;
    uint64_t found = 0;
    for (uint64_t slot = 0; slot < count; ++slot) {
        const MLA1517_State *state = &vertex->states[slot];
        if (!cassini_valid(state)) {
            mla1517_telemetry_add_query_fault(storage->telemetry, 1);
            continue;
        }
        if ((state->d5_zeckendorf & mask) != 0) continue;
        ++found;
        if (callback && callback(vertex_id, slot, state, context) != 0) break;
    }
    if (matches) *matches = found;
    return 0;
}

int primedb_storage_sync(primedb_storage_t *storage, uint32_t vertex_id) {
    if (!storage || vertex_id >= PRIMEDB_VERTEX_COUNT) return -1;
    if (msync(
        storage->vertices[vertex_id].mapping,
        storage->vertices[vertex_id].bytes,
        MS_SYNC
    ) != 0) return -1;
    return fsync(storage->vertices[vertex_id].fd) == 0 ? 0 : -1;
}

uint64_t primedb_storage_capacity(const primedb_storage_t *storage) {
    return storage ? storage->capacity : 0;
}

const char *primedb_storage_cursor_path(const primedb_storage_t *storage) {
    return storage ? storage->cursor_path : NULL;
}