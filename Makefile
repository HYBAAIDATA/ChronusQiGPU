include make/gates.mk

.PHONY: verify-unified test assurance-gates canonical-native clean

verify-unified:
	python3 -m pytest \
		tests/test_toe_unified_invariants.py \
		tests/test_toe_unified_adversarial.py \
		tests/test_toe_unified_property.py \
		tests/test_toe_unified_unit.py \
		tests/test_toe_unified_integration.py \
		tests/test_toe_unified_e2e.py \
		tests/test_toe_unified_benchmark.py -q

test: assurance-gates


assurance-gates:
	PYTHONPATH=.:mla1517_platform_v3.4/python python3 -m unittest discover -s tests -p 'test_guardian_gap_closure.py' -v
	PYTHONPATH=.:mla1517_platform_v3.4/python python3 -m unittest discover -s tests -p 'test_promotion_evidence.py' -v
	PYTHONPATH=.:mla1517_platform_v3.4/python python3 -m unittest discover -s tests -p 'test_enterprise_v2_tranches.py' -v
	PYTHONPATH=.:mla1517_platform_v3.4/python python3 -m unittest discover -s tests -p 'test_packs_versioning_observability.py' -v
	PYTHONPATH=.:mla1517_platform_v3.4/python python3 -m unittest discover -s tests -p 'test_fold_pipeline.py' -v
	PYTHONPATH=.:mla1517_platform_v3.4/python python3 -m al_haras.gate_cli config/al-haras-promotion-evidence.json
	python3 -m compileall -q al_haras hyba_contracts hyba_services hyba_profiles python_backend/core_modules

canonical-native:
	$(MAKE) -C mla1517_platform_v3.4/host all aethel-test primedb-storage-test primedb-boundary-test behavioral-gap-test

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf build dist *.egg-info
