GATE_TARGETS := rule7-no-float abi-check refuted-claims import-audit claim-register envelope-verify conformance-vectors resilience-suite schema-freeze promotion-manifest privileged-path-audit
.PHONY: gates release-gate $(GATE_TARGETS) publish-checks gate-rollup strict-hardware-gate gate-results-clean

# Clear old results before dispatch, including under parallel make.
gates: gate-results-clean
	+$(MAKE) --no-print-directory -k $(GATE_TARGETS)

gate-results-clean:
	mkdir -p results
	rm -f results/*.json

release-gate: gates
	python3 scripts/assert_gate_rollup.py
rule7-no-float:
	python3 scripts/rule7_no_float_gate.py
abi-check:
	python3 scripts/abi_check.py
refuted-claims:
	python3 scripts/refuted_claims_gate.py
import-audit:
	python3 scripts/import_audit.py
claim-register:
	python3 scripts/claim_register_gate.py
envelope-verify:
	python3 scripts/envelope_verify_gate.py
conformance-vectors:
	python3 scripts/conformance_vectors.py
resilience-suite:
	python3 scripts/resilience_suite.py
schema-freeze:
	python3 scripts/schema_freeze_gate.py
promotion-manifest:
	python3 scripts/promotion_manifest.py
privileged-path-audit:
	python3 scripts/privileged_path_audit.py
publish-checks:
	python3 scripts/publish_check_runs.py
gate-rollup:
	python3 scripts/assert_gate_rollup.py
strict-hardware-gate:
	@if [ "$${MLA1517_STRICT_HARDWARE_CI:-0}" = "1" ]; then \
		python3 chronus/mla1517_platform/scripts/strict_hardware_gate.py; \
	else echo 'SKIPPED: strict hardware CI not enabled'; fi
