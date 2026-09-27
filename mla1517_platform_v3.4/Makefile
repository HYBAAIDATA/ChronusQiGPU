PYTHONPATH=python

.PHONY: test release release-gate package-release requirements-audit behavioral-audit abi-check behavioral-gap-test clean reference extended conformance production shm-test progressive-mining-test simt-test hardware-contract-test rtl-reference-test host-driver host-driver-test aethel-test primedb-storage-test primedb-ingest-daemon mla1517-producer

test: requirements-audit reference extended conformance production shm-test progressive-mining-test simt-test hardware-contract-test rtl-reference-test host-driver-test aethel-test primedb-storage-test primedb-boundary-test behavioral-gap-test primedb-ingest-daemon mla1517-producer abi-check behavioral-audit python-regression

ifeq ($(MLA1517_STRICT_HARDWARE_CI),1)
test: strict-hardware-gate
endif

release-gate:
	PYTHONPATH=$(PYTHONPATH) python scripts/release_gate.py

package-release:
	PYTHONPATH=$(PYTHONPATH) python scripts/package_release.py

release: release-gate package-release

python-regression:
	PYTHONPATH=$(PYTHONPATH) python -m unittest discover -s python -p 'test*.py'

requirements-audit:
	python scripts/session_requirements_audit.py

behavioral-audit:
	PYTHONPATH=$(PYTHONPATH) python scripts/behavioral_gap_audit.py

clean:
	rm -f results/mla1517_shm_engine results/mla1517_progressive_miner \
		results/mla1517_simt_warp
	$(MAKE) -C host clean

reference:
	PYTHONPATH=$(PYTHONPATH) python python/reference_test.py

extended:
	PYTHONPATH=$(PYTHONPATH) python python/extended_algebra.py > results/extended_algebra_results.json

conformance:
	python python/run_conformance.py

production:
	PYTHONPATH=$(PYTHONPATH) python -m unittest python/test_production.py -v

shm-test:
	mkdir -p results
	g++ -std=c++17 -O3 -pthread -Icpp/include cpp/src/mla1517_shm_engine.cpp -o results/mla1517_shm_engine
	results/mla1517_shm_engine > results/cpp_shm_ring.json

progressive-mining-test:
	mkdir -p results
	g++ -std=c++17 -O3 -pthread -Icpp/include cpp/src/mla1517_progressive_miner.cpp -o results/mla1517_progressive_miner
	results/mla1517_progressive_miner > results/cpp_progressive_mining.json

simt-test:
	mkdir -p results
	g++ -std=c++17 -O3 -pthread -Icpp/include cpp/src/mla1517_simt_warp.cpp -o results/mla1517_simt_warp
	results/mla1517_simt_warp > results/cpp_simt_warp.json

hardware-contract-test:
	PYTHONPATH=$(PYTHONPATH) python -m unittest python/test_hardware_contract.py -v

rtl-reference-test:
	PYTHONPATH=$(PYTHONPATH) python -m unittest python/test_rtl_contract.py -v

host-driver:
	$(MAKE) -C host

host-driver-test: host-driver
	PYTHONPATH=$(PYTHONPATH) python -m unittest python/test_host_hardware.py -v

abi-check: host-driver
	PYTHONPATH=$(PYTHONPATH) python scripts/abi_check.py

aethel-test: host-driver
	$(MAKE) -C host aethel-test

primedb-storage-test: host-driver
	$(MAKE) -C host primedb-storage-test

behavioral-gap-test: host-driver
	$(MAKE) -C host behavioral-gap-test

primedb-boundary-test: host-driver
	$(MAKE) -C host primedb-boundary-test

primedb-ingest-daemon: host-driver
	$(MAKE) -C host primedb-ingest-daemon

mla1517-producer: host-driver
	$(MAKE) -C host mla1517-producer

.PHONY: strict-hardware-gate
strict-hardware-gate:
	MLA1517_STRICT_HARDWARE_CI=1 MLA1517_GPU_BACKEND=opencl PYTHONPATH=$(PYTHONPATH) python scripts/strict_hardware_gate.py
