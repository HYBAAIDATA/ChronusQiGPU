#define _GNU_SOURCE

#include "mla1517_shm.h"
#include "telemetry_shm.h"

#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
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
    const char *device_path = getenv("MLA1517_MMIO_DEVICE");
    const char *ring_path = getenv("MLA1517_PRIME_DB_RING");
    const char *overflow_path = getenv("MLA1517_PRIME_DB_OVERFLOW");
    const char *telemetry_path = getenv("MLA1517_TELEMETRY_PATH");
    if (!device_path || !ring_path) {
        fprintf(stderr, "Set MLA1517_MMIO_DEVICE and MLA1517_PRIME_DB_RING\n");
        return 2;
    }
    mla1517_device_t *device = mla1517_open(
        device_path, env_u64("MLA1517_MMIO_BYTES", 0x2000)
    );
    mla1517_shm_ring_t *ring = mla1517_shm_open(
        ring_path, MLA1517_SHM_CAPACITY
    );
    mla1517_shm_ring_t *overflow = mla1517_shm_open(
        overflow_path && *overflow_path
            ? overflow_path
            : "/dev/shm/mla1517_overflow",
        1u << 20
    );
    mla1517_telemetry_t *telemetry = telemetry_path
        ? mla1517_telemetry_open(telemetry_path)
        : NULL;
    if (!device || !ring || !overflow) {
        fprintf(stderr, "Unable to open MLA1517 MMIO device or Aethel ring\n");
        mla1517_shm_close(ring);
        mla1517_shm_close(overflow);
        mla1517_close(device);
        return 1;
    }
    if (mla1517_set_difficulty_mask(
            device, (uint32_t)env_u64("MLA1517_DIFFICULTY_MASK", 0x3f)) != 0 ||
        mla1517_set_base_step(
            device, env_u64("MLA1517_BASE_STEP", 0)) != 0 ||
        mla1517_start(device) != 0) {
        fprintf(stderr, "Unable to configure or start MLA1517 hardware\n");
        mla1517_shm_close(ring);
        mla1517_close(device);
        return 1;
    }
    signal(SIGINT, stop_daemon);
    signal(SIGTERM, stop_daemon);
    uint64_t published = 0;
    int overflow_was_full = 0;
    while (keep_running) {
        uint32_t batch = 0;
        while (batch < 64 && keep_running) {
            mla1517_shm_ring_t *target = NULL;
            int spilled = 0;
            if (mla1517_shm_space(ring) > 0) {
                target = ring;
            } else if (mla1517_shm_space(overflow) > 0) {
                target = overflow;
                spilled = 1;
            } else {
                if (!overflow_was_full) {
                    if (telemetry)
                        mla1517_telemetry_add_catastrophic_overflow(telemetry, 1);
                    overflow_was_full = 1;
                }
                struct timespec delay = {.tv_sec = 0, .tv_nsec = 1000000L};
                nanosleep(&delay, NULL);
                continue;
            }
            overflow_was_full = 0;
            mla1517_vault_record_t record;
            int polled = mla1517_poll_vault(
                device, batch == 0 ? 100 : 0, &record
            );
            if (polled < 0) {
                fprintf(stderr, "MMIO vault poll failed\n");
                keep_running = 0;
                break;
            }
            if (polled == 0) break;
            MLA1517_State state;
            memcpy(&state, record.state, sizeof(state));
            if (state.d10_cassini != 1 && state.d10_cassini != -1) {
                if (telemetry)
                    mla1517_telemetry_add_fault(
                        telemetry, state.d8_route % MLA1517_TELEMETRY_PARTITIONS, 1
                    );
            }
            if (mla1517_shm_push(target, &state) != 1) {
                if (telemetry)
                    mla1517_telemetry_add_catastrophic_overflow(telemetry, 1);
                fprintf(stderr, "Aethel publication backpressure fault\n");
                keep_running = 0;
                break;
            }
            if (spilled && telemetry)
                mla1517_telemetry_add_ring_overflow(telemetry, 1);
            ++batch;
            ++published;
        }
        if (!keep_running) break;
        if (batch == 0) {
            struct timespec delay = {.tv_sec = 0, .tv_nsec = 1000000L};
            nanosleep(&delay, NULL);
        }
        /* The no-drop policy is primary ring, spill ring, then explicit
         * catastrophic backpressure; no record is silently discarded. */
    }
    (void)mla1517_stop(device);
    printf("{\"status\":\"STOPPED\",\"published\":%llu}\n",
           (unsigned long long)published);
    mla1517_shm_close(ring);
    mla1517_shm_close(overflow);
    mla1517_telemetry_close(telemetry);
    mla1517_close(device);
    return 0;
}