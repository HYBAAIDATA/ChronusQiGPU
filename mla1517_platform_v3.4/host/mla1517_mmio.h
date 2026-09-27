#ifndef MLA1517_MMIO_H
#define MLA1517_MMIO_H

/*
 * MLA1517 Host-to-Silicon ABI v1
 *
 * The FPGA vendor integration must bind these offsets to the final PCIe BAR,
 * UIO mapping, or DMA-coherent control page. The driver deliberately accepts
 * an explicit device path and never opens /dev/mem implicitly.
 */

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MLA1517_ABI_VERSION 1u
#define MLA1517_STATE_BYTES 64u
#define MLA1517_MEMORY_NODES 20u

/* Control/status register offsets in the mapped BAR/control page. */
#define MLA1517_REG_MAGIC          0x000u
#define MLA1517_REG_VERSION        0x004u
#define MLA1517_REG_CONTROL        0x008u
#define MLA1517_REG_STATUS         0x00cu
#define MLA1517_REG_DIFFICULTY     0x010u
#define MLA1517_REG_BASE_STEP      0x018u
#define MLA1517_REG_IRQ_STATUS     0x020u
#define MLA1517_REG_IRQ_ACK        0x024u
#define MLA1517_REG_POLY_MASK_STAGED 0x028u
#define MLA1517_REG_LANE_MASK_STAGED 0x02cu
#define MLA1517_REG_COMMIT_REQ     0x030u
#define MLA1517_REG_COMMIT_ACK     0x034u

/* Aethel node layout: sequence word followed by one 64-byte hot state. */
#define MLA1517_VAULT_BASE         0x1000u
#define MLA1517_VAULT_STRIDE       0x0080u
#define MLA1517_VAULT_SEQ_OFFSET   0x0000u
#define MLA1517_VAULT_STATE_OFFSET 0x0008u

#define MLA1517_CONTROL_ENABLE     0x00000001u
#define MLA1517_STATUS_READY       0x00000001u
#define MLA1517_IRQ_VAULT_NONEMPTY 0x00000001u

typedef struct mla1517_device mla1517_device_t;

typedef struct {
    uint32_t node_id;
    uint64_t sequence;
    uint8_t state[MLA1517_STATE_BYTES];
} mla1517_vault_record_t;

/*
 * Open an explicitly supplied MMIO/PCIe/UiO mapping.
 *
 * The mapped object must be at least MLA1517_VAULT_BASE +
 * MLA1517_MEMORY_NODES * MLA1517_VAULT_STRIDE bytes. A regular file is
 * supported for deterministic integration tests.
 */
mla1517_device_t *mla1517_open(const char *device_path, uint64_t map_bytes);
void mla1517_close(mla1517_device_t *device);

int mla1517_set_difficulty_mask(mla1517_device_t *device, uint32_t mask);
int mla1517_set_base_step(mla1517_device_t *device, uint64_t base_step);
int mla1517_start(mla1517_device_t *device);
int mla1517_stop(mla1517_device_t *device);
int mla1517_update_polyhedral_mask(mla1517_device_t *device, uint32_t mask);
int mla1517_quarantine_lane(
    mla1517_device_t *device,
    uint32_t lane_id,
    int quarantine
);
int mla1517_stage_polyhedral_mask(mla1517_device_t *device, uint32_t mask);
int mla1517_stage_lane_mask(mla1517_device_t *device, uint32_t mask);
int mla1517_request_supervisor_commit(mla1517_device_t *device);
int mla1517_supervisor_commit_ack(const mla1517_device_t *device);

/*
 * Poll the interrupt/UMA area and return one newly committed Aethel record.
 * Returns:
 *   1  record returned
 *   0  timeout/no new record
 *  -1  invalid argument or I/O failure
 */
int mla1517_poll_vault(
    mla1517_device_t *device,
    int timeout_ms,
    mla1517_vault_record_t *record
);

/* Exposed for diagnostics and integration tests. */
uint32_t mla1517_last_error(const mla1517_device_t *device);
const char *mla1517_last_error_string(const mla1517_device_t *device);

#ifdef __cplusplus
}
#endif

#endif