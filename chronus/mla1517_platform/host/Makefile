# Host driver: the MMIO bridge and PRIME-DB storage libraries loaded by
# chronus/mla1517 via ctypes, their C contract tests, and the two daemons.

CC ?= cc
CFLAGS ?= -O2
CFLAGS += -std=c11 -Wall -Wextra -fPIC
LDLIBS += -pthread

CORE := mla1517_mmio.c mla1517_shm.c telemetry_shm.c
STORAGE := primedb_storage.c $(CORE)
HEADERS := $(wildcard *.h)

LIBS := libmla1517_mmio.so libprimedb_storage.so
DAEMONS := primedb_ingest_daemon mla1517_producer
TESTS := aethel_contract_test primedb_storage_test primedb_boundary_test behavioral_gap_test

.PHONY: all aethel-test primedb-storage-test primedb-boundary-test behavioral-gap-test \
	primedb-ingest-daemon mla1517-producer clean

all: $(LIBS)

libmla1517_mmio.so: $(CORE) $(HEADERS)
	$(CC) $(CFLAGS) -shared -o $@ $(CORE) $(LDLIBS)

libprimedb_storage.so: $(STORAGE) $(HEADERS)
	$(CC) $(CFLAGS) -shared -o $@ $(STORAGE) $(LDLIBS)

primedb_ingest_daemon: primedb_ingest_daemon.c $(STORAGE) $(HEADERS)
	$(CC) $(CFLAGS) -o $@ primedb_ingest_daemon.c $(STORAGE) $(LDLIBS)

mla1517_producer: mla1517_producer_daemon.c $(CORE) $(HEADERS)
	$(CC) $(CFLAGS) -o $@ mla1517_producer_daemon.c $(CORE) $(LDLIBS)

aethel_contract_test: aethel_contract_test.c mla1517_aethel.c $(CORE) $(HEADERS)
	$(CC) $(CFLAGS) -o $@ aethel_contract_test.c mla1517_aethel.c $(CORE) $(LDLIBS)

primedb_storage_test primedb_boundary_test behavioral_gap_test: %: %.c $(STORAGE) $(HEADERS)
	$(CC) $(CFLAGS) -o $@ $< $(STORAGE) $(LDLIBS)

primedb-ingest-daemon: primedb_ingest_daemon
mla1517-producer: mla1517_producer

aethel-test: aethel_contract_test
	./aethel_contract_test

primedb-storage-test: primedb_storage_test
	./primedb_storage_test

primedb-boundary-test: primedb_boundary_test
	./primedb_boundary_test

behavioral-gap-test: behavioral_gap_test
	./behavioral_gap_test

clean:
	rm -f $(LIBS) $(DAEMONS) $(TESTS)
