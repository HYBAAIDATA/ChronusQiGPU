/*
 * Win32 port of mla1517_mmio.c — identical ABI over a file-backed mapping.
 *
 * The POSIX build maps a character device or sparse file via mmap; here the
 * same register window lives in a Win32 file mapping
 * (CreateFile + CreateFileMapping + MapViewOfFile). Interrupt wake from UIO
 * char devices has no Windows analogue; the file-backed bounded-sleep path
 * the POSIX code uses for regular files is the only path kept.
 */
#include "mla1517_mmio.h"
#include "mla1517_shm.h"

#include <errno.h>
#include <stdalign.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

struct mla1517_device {
    HANDLE file;
    HANDLE mapping;
    uint8_t *map;
    size_t map_bytes;
    uint64_t last_sequence[MLA1517_MEMORY_NODES];
    uint32_t lane_mask;
    uint32_t error_code;
    char error_text[128];
};

static void set_error(mla1517_device_t *device, uint32_t code, const char *text) {
    if (!device) return;
    device->error_code = code;
    snprintf(device->error_text, sizeof(device->error_text), "%s", text);
}

static int in_bounds(const mla1517_device_t *device, size_t offset, size_t bytes) {
    return device && offset <= device->map_bytes &&
           bytes <= device->map_bytes - offset;
}

mla1517_device_t *mla1517_open(const char *device_path, uint64_t map_bytes) {
    if (!device_path || map_bytes == 0 || map_bytes > SIZE_MAX) return NULL;

    HANDLE file = CreateFileA(
        device_path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        OPEN_ALWAYS,
        FILE_FLAG_WRITE_THROUGH | FILE_FLAG_RANDOM_ACCESS,
        NULL
    );
    if (file == INVALID_HANDLE_VALUE) return NULL;

    /* Extend regular backing files exactly like ftruncate on POSIX. */
    LARGE_INTEGER size;
    if (GetFileSizeEx(file, &size) && (uint64_t)size.QuadPart < map_bytes) {
        LARGE_INTEGER wanted;
        wanted.QuadPart = (LONGLONG)map_bytes;
        if (!SetFilePointerEx(file, wanted, NULL, FILE_BEGIN) ||
            !SetEndOfFile(file)) {
            CloseHandle(file);
            return NULL;
        }
    }

    HANDLE mapping = CreateFileMappingA(
        file, NULL, PAGE_READWRITE,
        (DWORD)(map_bytes >> 32), (DWORD)(map_bytes & 0xFFFFFFFFu),
        NULL
    );
    if (!mapping) {
        CloseHandle(file);
        return NULL;
    }

    uint8_t *mapped = (uint8_t *)MapViewOfFile(
        mapping, FILE_MAP_ALL_ACCESS, 0, 0, (SIZE_T)map_bytes
    );
    if (!mapped) {
        CloseHandle(mapping);
        CloseHandle(file);
        return NULL;
    }

    mla1517_device_t *device = (mla1517_device_t *)calloc(1, sizeof(*device));
    if (!device) {
        UnmapViewOfFile(mapped);
        CloseHandle(mapping);
        CloseHandle(file);
        return NULL;
    }
    device->file = file;
    device->mapping = mapping;
    device->map = mapped;
    device->map_bytes = (size_t)map_bytes;
    device->error_text[0] = '\0';
    device->lane_mask = UINT32_MAX;
    return device;
}

void mla1517_close(mla1517_device_t *device) {
    if (!device) return;
    if (device->map) {
        FlushViewOfFile(device->map, device->map_bytes);
        UnmapViewOfFile(device->map);
    }
    if (device->mapping) CloseHandle(device->mapping);
    if (device->file && device->file != INVALID_HANDLE_VALUE) CloseHandle(device->file);
    free(device);
}

int mla1517_set_difficulty_mask(mla1517_device_t *device, uint32_t mask) {
    if (!in_bounds(device, MLA1517_REG_DIFFICULTY, sizeof(uint32_t))) {
        set_error(device, EINVAL, "difficulty register outside mapping");
        return -1;
    }
    __atomic_store_n((volatile uint32_t *)(device->map + MLA1517_REG_DIFFICULTY),
                     mask, __ATOMIC_RELEASE);
    return 0;
}

int mla1517_set_base_step(mla1517_device_t *device, uint64_t base_step) {
    if (!in_bounds(device, MLA1517_REG_BASE_STEP, sizeof(uint64_t))) {
        set_error(device, EINVAL, "base-step register outside mapping");
        return -1;
    }
    __atomic_store_n((volatile uint64_t *)(device->map + MLA1517_REG_BASE_STEP),
                     base_step, __ATOMIC_RELEASE);
    return 0;
}

int mla1517_start(mla1517_device_t *device) {
    if (!in_bounds(device, MLA1517_REG_CONTROL, sizeof(uint32_t))) {
        set_error(device, EINVAL, "control register outside mapping");
        return -1;
    }
    __atomic_store_n((volatile uint32_t *)(device->map + MLA1517_REG_CONTROL),
                     MLA1517_CONTROL_ENABLE, __ATOMIC_RELEASE);
    return 0;
}

int mla1517_stop(mla1517_device_t *device) {
    if (!in_bounds(device, MLA1517_REG_CONTROL, sizeof(uint32_t))) {
        set_error(device, EINVAL, "control register outside mapping");
        return -1;
    }
    __atomic_store_n((volatile uint32_t *)(device->map + MLA1517_REG_CONTROL),
                     0u, __ATOMIC_RELEASE);
    return 0;
}

int mla1517_update_polyhedral_mask(
    mla1517_device_t *device,
    uint32_t mask
) {
    if (!in_bounds(device, MLA1517_REG_POLY_MASK_STAGED, sizeof(uint32_t))) {
        set_error(device, EINVAL, "polyhedral-mask register outside mapping");
        return -1;
    }
    __atomic_store_n(
        (volatile uint32_t *)(device->map + MLA1517_REG_POLY_MASK_STAGED),
        mask, __ATOMIC_RELEASE
    );
    return 0;
}

int mla1517_quarantine_lane(
    mla1517_device_t *device,
    uint32_t lane_id,
    int quarantine
) {
    if (lane_id >= 32 || !in_bounds(device, MLA1517_REG_LANE_MASK_STAGED, sizeof(uint32_t))) {
        set_error(device, EINVAL, "lane quarantine request is invalid");
        return -1;
    }
    uint32_t bit = UINT32_C(1) << lane_id;
    if (quarantine) device->lane_mask &= ~bit;
    else device->lane_mask |= bit;
    __atomic_store_n(
        (volatile uint32_t *)(device->map + MLA1517_REG_LANE_MASK_STAGED),
        device->lane_mask, __ATOMIC_RELEASE
    );
    return 0;
}

int mla1517_stage_polyhedral_mask(
    mla1517_device_t *device,
    uint32_t mask
) {
    if (!in_bounds(device, MLA1517_REG_POLY_MASK_STAGED, sizeof(uint32_t))) {
        set_error(device, EINVAL, "staged polyhedral-mask register outside mapping");
        return -1;
    }
    __atomic_store_n(
        (volatile uint32_t *)(device->map + MLA1517_REG_POLY_MASK_STAGED),
        mask, __ATOMIC_RELEASE
    );
    return 0;
}

int mla1517_stage_lane_mask(mla1517_device_t *device, uint32_t mask) {
    if (!in_bounds(device, MLA1517_REG_LANE_MASK_STAGED, sizeof(uint32_t))) {
        set_error(device, EINVAL, "staged lane-mask register outside mapping");
        return -1;
    }
    device->lane_mask = mask;
    __atomic_store_n(
        (volatile uint32_t *)(device->map + MLA1517_REG_LANE_MASK_STAGED),
        mask, __ATOMIC_RELEASE
    );
    return 0;
}

int mla1517_request_supervisor_commit(mla1517_device_t *device) {
    if (!in_bounds(device, MLA1517_REG_COMMIT_REQ, sizeof(uint32_t))) {
        set_error(device, EINVAL, "supervisor commit register outside mapping");
        return -1;
    }
    __atomic_store_n(
        (volatile uint32_t *)(device->map + MLA1517_REG_COMMIT_REQ),
        1u, __ATOMIC_RELEASE
    );
    return 0;
}

int mla1517_supervisor_commit_ack(const mla1517_device_t *device) {
    if (!in_bounds(device, MLA1517_REG_COMMIT_ACK, sizeof(uint32_t))) return 0;
    return __atomic_load_n(
        (volatile uint32_t *)(device->map + MLA1517_REG_COMMIT_ACK),
        __ATOMIC_ACQUIRE
    ) == 1u;
}

int mla1517_poll_vault(
    mla1517_device_t *device,
    int timeout_ms,
    mla1517_vault_record_t *record
) {
    if (!device || !record || timeout_ms < 0) return -1;
    size_t end = MLA1517_VAULT_BASE +
                 MLA1517_MEMORY_NODES * MLA1517_VAULT_STRIDE;
    if (!in_bounds(device, MLA1517_VAULT_BASE, end - MLA1517_VAULT_BASE)) {
        set_error(device, EINVAL, "Aethel vault outside mapping");
        return -1;
    }

    /* File-backed path: bounded sleep, same as POSIX regular-file branch. */
    if (timeout_ms > 0) Sleep((DWORD)timeout_ms);

    for (uint32_t node = 0; node < MLA1517_MEMORY_NODES; ++node) {
        uint8_t *base = device->map + MLA1517_VAULT_BASE +
                        node * MLA1517_VAULT_STRIDE;
        volatile uint64_t *sequence =
            (volatile uint64_t *)(base + MLA1517_VAULT_SEQ_OFFSET);

        uint64_t seq1 = __atomic_load_n(sequence, __ATOMIC_ACQUIRE);
        if (seq1 == 0 || (seq1 & 1u) || seq1 <= device->last_sequence[node])
            continue;

        uint8_t snapshot[MLA1517_STATE_BYTES];
        memcpy(snapshot, base + MLA1517_VAULT_STATE_OFFSET,
               MLA1517_STATE_BYTES);
        uint64_t seq2 = __atomic_load_n(sequence, __ATOMIC_ACQUIRE);
        if (seq1 != seq2 || (seq2 & 1u)) continue;

        record->node_id = node;
        record->sequence = seq2;
        memcpy(record->state, snapshot, MLA1517_STATE_BYTES);
        device->last_sequence[node] = seq2;

        if (in_bounds(device, MLA1517_REG_IRQ_ACK, sizeof(uint32_t))) {
            __atomic_store_n(
                (volatile uint32_t *)(device->map + MLA1517_REG_IRQ_ACK),
                MLA1517_IRQ_VAULT_NONEMPTY, __ATOMIC_RELEASE);
        }
        return 1;
    }
    return 0;
}

uint32_t mla1517_last_error(const mla1517_device_t *device) {
    return device ? device->error_code : EINVAL;
}

const char *mla1517_last_error_string(const mla1517_device_t *device) {
    return device ? device->error_text : "invalid device";
}

/* -------------------------------------------------------------------------
 * Shared-memory ring — same SPSC layout as mla1517_shm.c, file-backed via
 * Win32 mappings. Header layout must stay identical to the POSIX build.
 */
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
               "shared-memory header size drift");

struct mla1517_shm_ring {
    HANDLE file;
    HANDLE mapping_obj;
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

    HANDLE file = CreateFileA(
        path, GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
        OPEN_ALWAYS, FILE_FLAG_RANDOM_ACCESS, NULL
    );
    if (file == INVALID_HANDLE_VALUE) return NULL;

    LARGE_INTEGER wanted;
    wanted.QuadPart = (LONGLONG)bytes;
    if (!SetFilePointerEx(file, wanted, NULL, FILE_BEGIN) ||
        !SetEndOfFile(file)) {
        CloseHandle(file);
        return NULL;
    }

    HANDLE mapping_obj = CreateFileMappingA(
        file, NULL, PAGE_READWRITE,
        (DWORD)(bytes >> 32), (DWORD)(bytes & 0xFFFFFFFFu), NULL
    );
    if (!mapping_obj) {
        CloseHandle(file);
        return NULL;
    }
    uint8_t *mapped = (uint8_t *)MapViewOfFile(
        mapping_obj, FILE_MAP_ALL_ACCESS, 0, 0, bytes
    );
    if (!mapped) {
        CloseHandle(mapping_obj);
        CloseHandle(file);
        return NULL;
    }

    mla1517_shm_ring_t *ring = calloc(1, sizeof(*ring));
    if (!ring) {
        UnmapViewOfFile(mapped);
        CloseHandle(mapping_obj);
        CloseHandle(file);
        return NULL;
    }
    ring->file = file;
    ring->mapping_obj = mapping_obj;
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
        UnmapViewOfFile(ring->mapping);
        CloseHandle(ring->mapping_obj);
        CloseHandle(ring->file);
        free(ring);
        return NULL;
    }
    return ring;
}

void mla1517_shm_close(mla1517_shm_ring_t *ring) {
    if (!ring) return;
    if (ring->mapping) {
        FlushViewOfFile(ring->mapping, ring->bytes);
        UnmapViewOfFile(ring->mapping);
    }
    if (ring->mapping_obj) CloseHandle(ring->mapping_obj);
    if (ring->file && ring->file != INVALID_HANDLE_VALUE) CloseHandle(ring->file);
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

/* -------------------------------------------------------------------------
 * Telemetry shm — 960-byte seqlock map, identical ABI to telemetry_shm.c.
 */
#include "telemetry_shm.h"

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

_Static_assert(sizeof(struct telemetry_map) == 960, "telemetry ABI size");

struct mla1517_telemetry {
    HANDLE file;
    HANDLE mapping_obj;
    size_t bytes;
    struct telemetry_map *map;
};

mla1517_telemetry_t *mla1517_telemetry_open(const char *path) {
    if (!path) return NULL;
    HANDLE file = CreateFileA(
        path, GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
        OPEN_ALWAYS, FILE_FLAG_RANDOM_ACCESS, NULL
    );
    if (file == INVALID_HANDLE_VALUE) return NULL;
    size_t bytes = sizeof(struct telemetry_map);
    LARGE_INTEGER wanted;
    wanted.QuadPart = (LONGLONG)bytes;
    if (!SetFilePointerEx(file, wanted, NULL, FILE_BEGIN) ||
        !SetEndOfFile(file)) {
        CloseHandle(file);
        return NULL;
    }
    HANDLE mapping_obj = CreateFileMappingA(
        file, NULL, PAGE_READWRITE, 0, (DWORD)bytes, NULL
    );
    if (!mapping_obj) {
        CloseHandle(file);
        return NULL;
    }
    struct telemetry_map *mapping = (struct telemetry_map *)MapViewOfFile(
        mapping_obj, FILE_MAP_ALL_ACCESS, 0, 0, bytes
    );
    if (!mapping) {
        CloseHandle(mapping_obj);
        CloseHandle(file);
        return NULL;
    }
    mla1517_telemetry_t *telemetry = calloc(1, sizeof(*telemetry));
    if (!telemetry) {
        UnmapViewOfFile(mapping);
        CloseHandle(mapping_obj);
        CloseHandle(file);
        return NULL;
    }
    telemetry->file = file;
    telemetry->mapping_obj = mapping_obj;
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
        UnmapViewOfFile(mapping);
        CloseHandle(mapping_obj);
        CloseHandle(file);
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
    if (telemetry->map) {
        FlushViewOfFile(telemetry->map, telemetry->bytes);
        UnmapViewOfFile(telemetry->map);
    }
    if (telemetry->mapping_obj) CloseHandle(telemetry->mapping_obj);
    if (telemetry->file && telemetry->file != INVALID_HANDLE_VALUE)
        CloseHandle(telemetry->file);
    free(telemetry);
}

void mla1517_telemetry_add_partition(
    mla1517_telemetry_t *telemetry, uint32_t partition, uint64_t amount
) {
    if (!telemetry || partition >= MLA1517_TELEMETRY_PARTITIONS) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(
        &telemetry->map->partition_tests[partition], amount, memory_order_relaxed
    );
    telemetry_write_end(telemetry->map);
}

void mla1517_telemetry_add_voids(mla1517_telemetry_t *telemetry, uint64_t amount) {
    if (!telemetry) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(&telemetry->map->topological_voids, amount,
                              memory_order_relaxed);
    telemetry_write_end(telemetry->map);
}

void mla1517_telemetry_add_accepted(mla1517_telemetry_t *telemetry, uint64_t amount) {
    if (!telemetry) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(&telemetry->map->stratum_accepted, amount,
                              memory_order_relaxed);
    telemetry_write_end(telemetry->map);
}

void mla1517_telemetry_add_fault(
    mla1517_telemetry_t *telemetry, uint32_t lane, uint64_t amount
) {
    if (!telemetry || lane >= MLA1517_TELEMETRY_PARTITIONS) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(&telemetry->map->cassini_faults[lane], amount,
                              memory_order_relaxed);
    telemetry_write_end(telemetry->map);
}

void mla1517_telemetry_add_drop(mla1517_telemetry_t *telemetry, uint64_t amount) {
    if (!telemetry) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(&telemetry->map->stratum_drops, amount,
                              memory_order_relaxed);
    telemetry_write_end(telemetry->map);
}

void mla1517_telemetry_add_query_fault(mla1517_telemetry_t *telemetry, uint64_t amount) {
    if (!telemetry) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(&telemetry->map->query_cassini_faults, amount,
                              memory_order_relaxed);
    telemetry_write_end(telemetry->map);
}

void mla1517_telemetry_add_ring_overflow(mla1517_telemetry_t *telemetry, uint64_t amount) {
    if (!telemetry) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(&telemetry->map->ring_overflows, amount,
                              memory_order_relaxed);
    telemetry_write_end(telemetry->map);
}

void mla1517_telemetry_add_catastrophic_overflow(
    mla1517_telemetry_t *telemetry, uint64_t amount
) {
    if (!telemetry) return;
    telemetry_write_begin(telemetry->map);
    atomic_fetch_add_explicit(&telemetry->map->catastrophic_overflows, amount,
                              memory_order_relaxed);
    telemetry_write_end(telemetry->map);
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

int mla1517_telemetry_snapshot(const char *path, void *out, size_t out_bytes) {
    if (!path || !out || out_bytes < sizeof(struct telemetry_map)) return -1;
    HANDLE file = CreateFileA(
        path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
        OPEN_EXISTING, FILE_FLAG_RANDOM_ACCESS, NULL
    );
    if (file == INVALID_HANDLE_VALUE) return -1;
    HANDLE mapping_obj = CreateFileMappingA(file, NULL, PAGE_READONLY, 0, 0, NULL);
    if (!mapping_obj) {
        CloseHandle(file);
        return -1;
    }
    const struct telemetry_map *source = (const struct telemetry_map *)
        MapViewOfFile(mapping_obj, FILE_MAP_READ, 0, 0,
                      sizeof(struct telemetry_map));
    if (!source) {
        CloseHandle(mapping_obj);
        CloseHandle(file);
        return -1;
    }
    int result = -2;
    for (unsigned attempt = 0; attempt < 1000; ++attempt) {
        uint64_t s0 = atomic_load_explicit(&source->seq, memory_order_acquire);
        if (s0 & 1u) { Sleep(0); continue; }
        memcpy(out, source, sizeof(struct telemetry_map));
        uint64_t s1 = atomic_load_explicit(&source->seq, memory_order_acquire);
        if (s0 == s1) { result = 0; break; }
    }
    UnmapViewOfFile((void *)source);
    CloseHandle(mapping_obj);
    CloseHandle(file);
    return result;
}
