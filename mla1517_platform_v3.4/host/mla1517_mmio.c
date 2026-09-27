#define _GNU_SOURCE

#include "mla1517_mmio.h"

#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

struct mla1517_device {
    int fd;
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

static void sleep_millis(int timeout_ms) {
    struct timespec request;
    request.tv_sec = timeout_ms / 1000;
    request.tv_nsec = (long)(timeout_ms % 1000) * 1000000L;
    nanosleep(&request, NULL);
}

mla1517_device_t *mla1517_open(const char *device_path, uint64_t map_bytes) {
    if (!device_path || map_bytes == 0 || map_bytes > SIZE_MAX) return NULL;

    int fd = open(device_path, O_RDWR | O_SYNC | O_CLOEXEC);
    if (fd < 0) return NULL;

    struct stat st;
    if (fstat(fd, &st) != 0) {
        close(fd);
        return NULL;
    }

    /*
     * For a regular file, extend it so integration tests can use a sparse
     * backing page. Character devices are already sized by the kernel.
     */
    if (S_ISREG(st.st_mode) && (uint64_t)st.st_size < map_bytes) {
        if (ftruncate(fd, (off_t)map_bytes) != 0) {
            close(fd);
            return NULL;
        }
    }

    void *mapped = mmap(NULL, (size_t)map_bytes, PROT_READ | PROT_WRITE,
                        MAP_SHARED, fd, 0);
    if (mapped == MAP_FAILED) {
        close(fd);
        return NULL;
    }

    mla1517_device_t *device = (mla1517_device_t *)calloc(1, sizeof(*device));
    if (!device) {
        munmap(mapped, (size_t)map_bytes);
        close(fd);
        return NULL;
    }
    device->fd = fd;
    device->map = (uint8_t *)mapped;
    device->map_bytes = (size_t)map_bytes;
    device->error_text[0] = '\0';
    device->lane_mask = UINT32_MAX;
    return device;
}

void mla1517_close(mla1517_device_t *device) {
    if (!device) return;
    if (device->map) munmap(device->map, device->map_bytes);
    if (device->fd >= 0) close(device->fd);
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
        mask,
        __ATOMIC_RELEASE
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
        device->lane_mask,
        __ATOMIC_RELEASE
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

static int wait_for_interrupt(mla1517_device_t *device, int timeout_ms) {
    if (timeout_ms < 0) timeout_ms = 0;

    /*
     * UIO devices can wake through poll(). Regular files are used by tests;
     * poll() on them is always ready, so use a bounded sleep in that case.
     */
    struct stat st;
    if (fstat(device->fd, &st) == 0 && S_ISCHR(st.st_mode)) {
        struct pollfd event = {.fd = device->fd, .events = POLLIN};
        int result = poll(&event, 1, timeout_ms);
        if (result < 0 && errno != EINTR) return -1;
        if (result > 0 && (event.revents & (POLLERR | POLLHUP))) return -1;
        if (result > 0) {
            /* UIO requires an event-count read to re-arm the interrupt. */
            uint32_t event_count = 0;
            (void)read(device->fd, &event_count, sizeof(event_count));
        }
        return result > 0 ? 1 : 0;
    }
    if (timeout_ms > 0) sleep_millis(timeout_ms);
    return 0;
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

    int wait_result = wait_for_interrupt(device, timeout_ms);
    if (wait_result < 0) {
        set_error(device, errno, "interrupt wait failed");
        return -1;
    }
    for (uint32_t node = 0; node < MLA1517_MEMORY_NODES; ++node) {
        uint8_t *base = device->map + MLA1517_VAULT_BASE +
                        node * MLA1517_VAULT_STRIDE;
        volatile uint64_t *sequence =
            (volatile uint64_t *)(base + MLA1517_VAULT_SEQ_OFFSET);

        /*
         * Producer protocol:
         *   odd sequence  = write in progress
         *   even sequence = committed and visible
         *
         * Double-read prevents a torn state from crossing into Python.
         */
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