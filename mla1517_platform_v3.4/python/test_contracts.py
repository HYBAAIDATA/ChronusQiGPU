"""Contract-coverage tests: FoldContract, OperatorContract, retrieval modes,
PairingTest records, workload manifest/envelope, deployment manifest, and
the canonical MLAObject fields."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from mla1517.contracts import (
    FOLD_CONTRACTS,
    OPERATOR_CONTRACTS,
    FoldContractViolation,
    OperatorMode,
    OperatorRejected,
    PairingStatus,
    PairingTest,
    RetrievalMode,
    check_operator,
    fold_contract,
    operator_contract,
    retrieve,
)
from mla1517.deployment import ManifestRejected, compile_manifest, load_manifest
from mla1517.objects import MLAObject
from mla1517.prime import main as prime_main
from mla1517.workload import WorkloadManifest, run_workload


class ContractRegistryTests(unittest.TestCase):
    def test_native_families_declared(self):
        self.assertIn("pisot_binet", FOLD_CONTRACTS)
        self.assertIn("fibonacci_zeckendorf", FOLD_CONTRACTS)
        self.assertIn("exact_state_vector", FOLD_CONTRACTS)
        for contract in FOLD_CONTRACTS.values():
            self.assertTrue(contract.canonical_hash_rule)
            self.assertTrue(contract.invariant_set)
            self.assertTrue(contract.backend_requirements)

    def test_native_operators_declared(self):
        for name in ("fold", "unfold", "scale", "seal", "verify", "resonance_scan"):
            self.assertIn(name, OPERATOR_CONTRACTS)
            self.assertTrue(OPERATOR_CONTRACTS[name].deterministic)

    def test_unknown_family_fails_closed(self):
        with self.assertRaises(FoldContractViolation):
            fold_contract("tribonacci_state")
        with self.assertRaises(OperatorRejected):
            operator_contract("teleport")
        with self.assertRaises(OperatorRejected):
            check_operator("unfold", "exact_state_vector")

    def test_operator_modes_declared(self):
        self.assertEqual(OPERATOR_CONTRACTS["unfold"].mode, OperatorMode.REHYDRATE)
        self.assertEqual(OPERATOR_CONTRACTS["verify"].mode, OperatorMode.PRESERVE)
        self.assertEqual(OPERATOR_CONTRACTS["fold"].mode, OperatorMode.TRANSFORM)


class RetrievalModeTests(unittest.TestCase):
    def setUp(self):
        self.obj = MLAObject.create({"v": 1}, sequence_index=15)

    def test_get_exact_returns_authoritative_state(self):
        result = retrieve(self.obj, RetrievalMode.GET_EXACT)
        self.assertEqual(result.payload["exact_state"], [610, 987])
        self.assertFalse(result.rehydrated_internally)
        self.assertTrue(result.proof["object_valid"])

    def test_get_folded_returns_reconstruction_contract(self):
        result = retrieve(self.obj, "GET_FOLDED")
        self.assertIn("reconstruction_contract", result.payload)
        self.assertTrue(result.payload["folded"]["lossless"])

    def test_get_projection_is_declared_view(self):
        result = retrieve(self.obj, "GET_PROJECTION")
        self.assertIn("projection", result.payload["declared"])
        # The view reports its residual honestly rather than claiming exactness.
        self.assertIn("residual", result.payload)
        self.assertEqual(result.payload["view"], "binet")

    def test_get_proof_returns_lineage(self):
        result = retrieve(self.obj, "GET_PROOF")
        self.assertTrue(result.payload["invariants"])
        self.assertEqual(result.payload["lineage"]["created_at_index"], 15)

    def test_get_executable_package(self):
        result = retrieve(self.obj, "GET_EXECUTABLE")
        self.assertTrue(result.payload["certified"])
        self.assertTrue(result.payload["operators"])

    def test_unknown_mode_fails_closed(self):
        with self.assertRaises(ValueError):
            retrieve(self.obj, "GET_EVERYTHING")


class PairingTestRecordTests(unittest.TestCase):
    def test_record_shape_and_status(self):
        record = PairingTest(
            pairing_name="fibonacci_cassini",
            source_components=("fibonacci", "cassini"),
            combined_operator_or_transform="seal",
            input_domain="index 1..1000",
            exact_expected_result="(-1)^n",
            invariants=("cassini_seal",),
            baseline="integer identity",
            measured_result="(-1)^n verified",
            residual_or_error=0,
            performance={"wall_ms": 1.0},
            reproducibility_command="python -m unittest test_contracts",
            status=PairingStatus.VERIFIED,
        )
        body = record.as_dict()
        self.assertEqual(body["status"], "VERIFIED")
        self.assertEqual(body["pairing_name"], "fibonacci_cassini")


class MLAObjectCanonicalTests(unittest.TestCase):
    def test_canonical_fields_present_and_consistent(self):
        obj = MLAObject.create({"v": 1}, sequence_index=15, scale=15)
        for field_name in (
            "payload_type",
            "exact_state",
            "scale_index",
            "lucas_state",
            "pisot_fold",
            "binet_view",
            "fibonacci_pair",
            "zeckendorf_code",
            "prime_address",
            "polyhedral_location",
            "transform_state",
            "cassini_seal",
            "residual_boundary",
            "lineage",
            "version",
        ):
            self.assertIn(field_name, obj.to_dict())
        self.assertEqual(obj.exact_state, obj.fibonacci_pair)
        self.assertEqual(obj.scale_index, obj.sequence_index)
        self.assertEqual(obj.zeckendorf_code, obj.zeckendorf_mask)
        obj.validate()

    def test_store_roundtrip_preserves_canonical_fields(self):
        from mla1517.store import PrimeDB

        with tempfile.TemporaryDirectory() as td:
            db = PrimeDB(Path(td) / "t.db")
            obj = db.put({"v": 7}, 15)
            back = db.get(obj.object_id)
            self.assertEqual(back.exact_state, obj.fibonacci_pair)
            self.assertEqual(back.lineage, obj.lineage)
            back.validate()
            db.close()


class WorkloadEnvelopeTests(unittest.TestCase):
    def test_manifest_rejects_undeclared_backend(self):
        with self.assertRaises(ValueError):
            WorkloadManifest(
                workload="w",
                mathematical_model="classical",
                scale=15,
                fold_family="pisot_binet",
                encoding="fibonacci_zeckendorf",
                backend="magic_box",
            )

    def test_required_result_envelope(self):
        manifest = WorkloadManifest(
            workload="fibonacci_seal",
            mathematical_model="classical",
            scale=15,
            fold_family="pisot_binet",
            encoding="fibonacci_zeckendorf",
            backend="cpu",
        )
        result = run_workload(manifest).as_dict()
        for key in (
            "workload",
            "backend",
            "scale",
            "lucas_operator",
            "pisot_fold",
            "cassini_valid",
            "zeckendorf_valid",
            "baseline_result",
            "scaled_result",
            "fidelity_or_error",
            "runtime_seconds",
            "memory_bytes",
            "bytes_moved",
            "proof_checks",
            "theorem_proven",
            "interpretation",
        ):
            self.assertIn(key, result)
        self.assertTrue(result["cassini_valid"])
        self.assertEqual(result["scaled_result"], "1364")
        self.assertFalse(result["theorem_proven"])
        self.assertEqual(result["interpretation"], "measured result only")


class DeploymentManifestTests(unittest.TestCase):
    _BASE = {
        "product": "prime-db-mla1517",
        "profile": "developer",
        "mode": "cpu_reference",
        "security": "standard",
        "storage": "embedded",
        "ai": {"training": False, "inference": False, "vector": False, "graph": False},
    }

    def test_developer_profile_compiles(self):
        plan = compile_manifest(load_manifest(self._BASE))
        self.assertIn("prime-db", plan.services)
        self.assertEqual(plan.policies["proof_policy"], "required")
        self.assertFalse(plan.evidence_manifest["signed"])

    def test_every_profile_compiles(self):
        for profile in ("edge", "enterprise", "sovereign", "hyperscaler"):
            doc = dict(self._BASE, profile=profile)
            plan = compile_manifest(load_manifest(doc))
            self.assertEqual(plan.profile, profile)
            self.assertTrue(plan.services)

    def test_host_overlay_mode_maps_devices(self):
        plan = compile_manifest(load_manifest(dict(self._BASE, mode="host_gpu_overlay")))
        self.assertIn("/dev/dri", plan.device_mappings)
        self.assertIn("host-overlay", plan.services)

    def test_fail_closed_rejections(self):
        for key, value in (
            ("profile", "planet9"),
            ("mode", "quantum"),
            ("security", "yolo"),
            ("storage", "volatile"),
        ):
            with self.assertRaises(ManifestRejected):
                load_manifest(dict(self._BASE, **{key: value}))
        with self.assertRaises(ManifestRejected):
            load_manifest(dict(self._BASE, performance_claim_policy="guaranteed"))
        with self.assertRaises(ManifestRejected):
            load_manifest(dict(self._BASE, proof_policy="optional"))


class PairingSuiteTests(unittest.TestCase):
    def test_p1_p10_all_verified(self):
        from mla1517.pairing_tests import run_pairing_tests

        results = run_pairing_tests()
        self.assertEqual(len(results), 10)
        for record in results:
            self.assertEqual(
                record.status,
                PairingStatus.VERIFIED,
                f"{record.pairing_name}: {record.as_dict()}",
            )
        self.assertEqual(
            [r.pairing_name for r in results],
            [f"P{i}" for i in range(1, 11)],
        )


class PrimeCliTests(unittest.TestCase):
    def _run(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = prime_main(list(argv))
        return code, json.loads(buf.getvalue())

    def test_deploy_returns_stable_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = Path(td) / "manifest.yaml"
            manifest.write_text(
                "product: prime-db-mla1517\nprofile: developer\n"
                "mode: cpu_reference\nsecurity: standard\nstorage: embedded\n"
                "proof_policy: required\nperformance_claim_policy: measured_only\n"
            )
            code, env = self._run("deploy", str(manifest))
        self.assertEqual(code, 0)
        self.assertEqual(env["status"], "ok")
        self.assertTrue(env["object_id"])
        self.assertIn("runtime_seconds", env["resource_use"])

    def test_ingest_content_addresses_dataset(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "a.txt").write_text("data")
            code, env = self._run("ingest", td)
        self.assertEqual(code, 0)
        self.assertEqual(len(env["object_id"]), 64)

    def test_unimplemented_commands_fail_closed(self):
        for command, target in (
            ("feature", "build"),
            ("train", "t.yaml"),
            ("evaluate", "run1"),
            ("promote", "m1"),
            ("serve", "m1"),
        ):
            argv = (command, target) if command != "feature" else ("feature", "build", "f.yaml")
            code, env = self._run(*argv)
            self.assertEqual(code, 2)
            self.assertEqual(env["status"], "not_implemented")


if __name__ == "__main__":
    unittest.main(verbosity=2)
