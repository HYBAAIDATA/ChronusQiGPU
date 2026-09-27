#!/bin/sh
set -eu

case "${MLA1517_WORKLOAD:-mathematical}" in
  mathematical)
    exec /usr/local/bin/mla1517-shm-engine
    ;;
  structured_mining)
    exec /usr/local/bin/mla1517-progressive-miner
    ;;
  simt_warp)
    exec /usr/local/bin/mla1517-simt-warp
    ;;
  *)
    echo "unsupported MLA1517_WORKLOAD: ${MLA1517_WORKLOAD}" >&2
    exit 2
    ;;
esac