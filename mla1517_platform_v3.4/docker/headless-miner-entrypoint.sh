#!/bin/sh
set -eu

: "${MLA1517_MMIO_DEVICE:?Set MLA1517_MMIO_DEVICE to the mapped FPGA/UIO device}"
: "${MLA1517_STRATUM_USER:?Set MLA1517_STRATUM_USER to the pool worker identity}"

exec python /app/python/headless_miner.py "$@"