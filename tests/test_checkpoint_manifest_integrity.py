"""Integrity regression tests; no model, pool or deployment claims."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

# The validator is dependency-free; do not boot a runtime to test an envelope.
_SPEC = importlib.util.spec_from_file_location(
    "manifest_integrity_under_test",
    Path(__file__).resolve().parents[1] / "euclid" / "manifest_integrity.py",
)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def sealed(body):
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        **body,
        "seal": hashlib.sha256(
            b"euclid.checkpoint-manifest.seal.v1\0" + canonical
        ).hexdigest(),
    }


class ManifestEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.body = {
            "schema": "euclid.checkpoint-manifest/1",
            "source_revision": "revision-for-test",
            "policy_version": "euclid.experience-policy/1",
            "task": {"task_id": "dispatch", "actions": ["hold", "reduce", "restore"]},
            "learner": {"checkpoint_path": "learner.json", "state_hash": "a" * 64},
            "dataset": {}, "dedup": {}, "evidence": {},
        }

    def test_valid_manifest_returns_independent_snapshot(self):
        manifest = sealed(self.body)
        result = _MODULE.validate_manifest_envelope(manifest)
        result["task"]["actions"].append("other")
        self.assertEqual(len(manifest["task"]["actions"]), 3)

    def test_tampered_direct_mapping_is_rejected(self):
        manifest = sealed(self.body)
        manifest["learner"]["checkpoint_path"] = "substituted.json"
        with self.assertRaisesRegex(ValueError, "seal mismatch"):
            _MODULE.validate_manifest_envelope(manifest)

    def test_missing_seal_rejected(self):
        with self.assertRaisesRegex(ValueError, "seal mismatch"):
            _MODULE.validate_manifest_envelope(self.body)

    def test_nonstring_seal_rejected(self):
        manifest = sealed(self.body)
        manifest["seal"] = 42
        with self.assertRaisesRegex(ValueError, "seal mismatch"):
            _MODULE.validate_manifest_envelope(manifest)

    def test_schema_rejected_even_with_consistent_seal(self):
        body = {**self.body, "schema": "future-schema"}
        with self.assertRaisesRegex(ValueError, "unsupported"):
            _MODULE.validate_manifest_envelope(sealed(body))

    def test_required_sections_checked_after_seal(self):
        for section in ("task", "learner", "dataset", "dedup", "evidence"):
            with self.subTest(section=section):
                body = copy.deepcopy(self.body)
                body[section] = []
                with self.assertRaisesRegex(ValueError, "section"):
                    _MODULE.validate_manifest_envelope(sealed(body))

    def test_revision_and_policy_are_required(self):
        for field in ("source_revision", "policy_version"):
            with self.subTest(field=field):
                body = {**self.body, field: " "}
                with self.assertRaisesRegex(ValueError, "required"):
                    _MODULE.validate_manifest_envelope(sealed(body))

    def test_nonfinite_values_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                manifest = sealed(self.body)
                manifest["created_at"] = value
                with self.assertRaisesRegex(ValueError, "finite"):
                    _MODULE.validate_manifest_envelope(manifest)

    def test_non_json_values_rejected(self):
        manifest = sealed(self.body)
        manifest["task"]["callback"] = object()
        with self.assertRaisesRegex(ValueError, "finite JSON"):
            _MODULE.validate_manifest_envelope(manifest)

    def test_non_mapping_rejected(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            _MODULE.validate_manifest_envelope([])

    def test_valid_artifact_digest(self):
        digest = hashlib.sha256(b"artifact").hexdigest()
        self.assertEqual(_MODULE.require_sha256(digest, field="artifact"), digest)

    def test_missing_or_malformed_artifact_hash_rejected(self):
        for value in (None, "", "a" * 63, "A" * 64, "g" * 64, 12):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    _MODULE.require_sha256(value, field="artifact")


if __name__ == "__main__":
    unittest.main()
