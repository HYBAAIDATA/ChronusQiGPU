#!/bin/sh
set -eu

: "${MLA1517_PRIME_DB_RING:?Set MLA1517_PRIME_DB_RING to the shared Aethel ring}"
: "${MLA1517_PRIME_DB_DIR:?Set MLA1517_PRIME_DB_DIR to the PRIME-DB data directory}"

exec /usr/local/bin/mla1517-primedb