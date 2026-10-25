"""Non-mining regressions: synthetic fixtures, not deployment qualification."""
from dataclasses import asdict
import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from hyba_services.catalogue import capture_notebook
from hyba_services.core import ProofService
from hyba_services.platform import ModelRegistry, PromotionBlocked


class EnterpriseAuditGuardrails(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.registry = ModelRegistry(self.tmp.name)
        self.evidence = {k: 'synthetic-fixture' for k in (
            'dataset_snapshot_hash', 'code_and_environment_hash',
            'backend_certificate', 'evaluation_suite', 'baselines')}
        self.sha = self.registry.register(b'fixture', {}, self.evidence, 'tenant')

    def state(self):
        return json.loads((Path(self.tmp.name)/'tenant'/self.sha/'state.json').read_text())['state']

    def test_empty_checks_cannot_promote(self):
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', self.sha, 'EVALUATED', ())
        self.assertEqual(self.state(), 'DRAFT')

    def test_empty_generator_cannot_promote(self):
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', self.sha, 'EVALUATED', iter(()))

    def test_truthy_non_boolean_check_is_not_approval(self):
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', self.sha, 'EVALUATED', [lambda *_: 'PASS'])

    def test_cannot_skip_to_deployment(self):
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', self.sha, 'DEPLOYED', [lambda *_: True])
        self.assertEqual(self.state(), 'DRAFT')

    def test_sequential_promotion(self):
        for target in ('EVALUATED', 'APPROVED', 'DEPLOYED', 'RETIRED'):
            self.registry.promote('tenant', self.sha, target, iter([lambda *_: True]))
            self.assertEqual(self.state(), target)

    def test_cannot_move_backwards(self):
        for target in ('EVALUATED', 'APPROVED'):
            self.registry.promote('tenant', self.sha, target, [lambda *_: True])
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', self.sha, 'EVALUATED', [lambda *_: True])
        self.assertEqual(self.state(), 'APPROVED')

    def test_failed_check_leaves_state_unchanged(self):
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', self.sha, 'EVALUATED', [lambda *_: False])
        self.assertEqual(self.state(), 'DRAFT')

    def test_exception_leaves_state_unchanged(self):
        def fail(*_):
            raise RuntimeError('fixture failure')
        with self.assertRaises(RuntimeError):
            self.registry.promote('tenant', self.sha, 'EVALUATED', [fail])
        self.assertEqual(self.state(), 'DRAFT')

    def test_approval_still_requires_evidence(self):
        sha = self.registry.register(b'other', {}, {}, 'tenant')
        self.registry.promote('tenant', sha, 'EVALUATED', [lambda *_: True])
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', sha, 'APPROVED', [lambda *_: True])

    def test_notebook_capture_does_not_claim_replay(self):
        result = capture_notebook({'cells': ['1+1'], 'outputs': [999]}, {'python': 'fixture'})
        self.assertFalse(result['reproducible'])
        self.assertEqual(result['replay_status'], 'NOT_RUN')

    def test_capture_preserves_provenance(self):
        session = {'cells': ['1+1'], 'outputs': [2], 'data_references': ['fixture']}
        first = capture_notebook(session, {'python': 'fixture'})
        second = capture_notebook(session, {'python': 'fixture'})
        self.assertEqual(first['session_hash'], second['session_hash'])
        self.assertEqual(first['outputs'], [2])
        self.assertEqual(first['data_refs'], ['fixture'])

    def test_empty_invariants_cannot_be_certified(self):
        obj = SimpleNamespace(object_id='fixture', residual_boundary=0)
        with self.assertRaises(ValueError):
            ProofService(b'x'*32).certify('identity', obj, obj, {}, {})

    def test_truthy_non_boolean_is_not_invariant_proof(self):
        obj = SimpleNamespace(object_id='fixture', residual_boundary=0)
        with self.assertRaises(ValueError):
            ProofService(b'x'*32).certify('identity', obj, obj, {'same': lambda *_: 'PASS'}, {})

    def test_literal_invariant_success_still_signs(self):
        obj = SimpleNamespace(object_id='fixture', residual_boundary=0)
        proof = ProofService(b'x'*32).certify('identity', obj, obj, {'same': lambda *_: True}, {})
        self.assertEqual(proof.invariant_results, (True,))
        self.assertTrue(proof.signature)


class ProofCertificationUnits(unittest.TestCase):
    def setUp(self):
        self.service = ProofService(b"p" * 32)
        self.input = SimpleNamespace(object_id="input", residual_boundary=0)
        self.output = SimpleNamespace(object_id="output", residual_boundary="1/8")

    def test_mixed_invariants_reject_nonliteral_success_without_signing(self):
        for result in (False, None, 0, 1, "PASS", [], [True], {"ok": True}):
            with self.subTest(result=result):
                checks = {
                    "accepted": Mock(return_value=True), "rejected": Mock(return_value=result),
                }
                with patch("hyba_services.core.hmac.new") as sign:
                    with self.assertRaisesRegex(ValueError, "invariant failed"):
                        self.service.certify("transform", self.input, self.output, checks, {})
                    sign.assert_not_called()

    def test_invariant_truthiness_is_never_coerced(self):
        class TruthinessTrap:
            def __bool__(self):
                raise AssertionError("invariant result must not be coerced")

        with self.assertRaisesRegex(ValueError, "invariant failed"):
            self.service.certify(
                "transform", self.input, self.output, {"trap": lambda *_: TruthinessTrap()}, {},
            )

    def test_invariant_exception_propagates_without_signing(self):
        failure = RuntimeError("check unavailable")
        with patch("hyba_services.core.hmac.new") as sign:
            with self.assertRaises(RuntimeError) as caught:
                self.service.certify(
                    "transform", self.input, self.output,
                    {"raises": Mock(side_effect=failure)}, {},
                )
            sign.assert_not_called()
        self.assertIs(caught.exception, failure)

    def test_multiple_invariants_preserve_names_inputs_and_signed_metadata(self):
        checks = {"second": Mock(return_value=True), "first": Mock(return_value=True)}
        backend = {"backend": "synthetic", "exact": True}
        proof = self.service.certify("transform", self.input, self.output, checks, backend)
        for check in checks.values():
            check.assert_called_once_with(self.input, self.output)
        self.assertEqual(proof.invariants_checked, ("second", "first"))
        self.assertEqual(proof.invariant_results, (True, True))
        self.assertEqual(proof.input_object_id, "input")
        self.assertEqual(proof.output_object_id, "output")
        self.assertEqual(proof.residual_bound, "1/8")
        self.assertEqual(proof.backend_certificate, backend)
        self.assertEqual(proof.replay_command, ("hyba-replay", "input", "transform"))
        unsigned = asdict(proof)
        signature = unsigned.pop("signature")
        expected = hmac.new(
            self.service.key,
            json.dumps(unsigned, sort_keys=True, default=str).encode(), hashlib.sha256,
        ).hexdigest()
        self.assertEqual(signature, expected)


class ModelPromotionUnits(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.registry = ModelRegistry(temporary.name)
        self.card = {"name": "synthetic-model"}
        self.evidence = {key: "synthetic" for key in (
            "dataset_snapshot_hash", "code_and_environment_hash", "backend_certificate",
            "evaluation_suite", "baselines",
        )}
        self.sha = self.registry.register(b"synthetic", self.card, self.evidence, "tenant")
        self.base = Path(temporary.name) / "tenant" / self.sha
        self.state_path = self.base / "state.json"

    def set_state(self, state):
        self.state_path.write_text(json.dumps({"state": state, "registered_at": 17}))
        return self.state_path.read_bytes()

    def test_all_invalid_lifecycle_edges_refuse_before_running_checks(self):
        states = ("DRAFT", "EVALUATED", "APPROVED", "DEPLOYED", "RETIRED")
        for index, current in enumerate(states):
            for target in states[1:]:
                if index < len(states) - 1 and target == states[index + 1]:
                    continue
                with self.subTest(current=current, target=target):
                    before = self.set_state(current)
                    check = Mock(return_value=True)
                    with self.assertRaisesRegex(PromotionBlocked, "lifecycle"):
                        self.registry.promote("tenant", self.sha, target, [check])
                    check.assert_not_called()
                    self.assertEqual(self.state_path.read_bytes(), before)

    def test_unknown_or_missing_current_state_is_blocked(self):
        for state in (None, "UNKNOWN", "evaluated"):
            with self.subTest(state=state):
                before = self.set_state(state)
                with self.assertRaisesRegex(PromotionBlocked, "lifecycle"):
                    self.registry.promote("tenant", self.sha, "EVALUATED", [lambda *_: True])
                self.assertEqual(self.state_path.read_bytes(), before)
        self.state_path.write_text("{}")
        with self.assertRaisesRegex(PromotionBlocked, "lifecycle"):
            self.registry.promote("tenant", self.sha, "EVALUATED", [lambda *_: True])
        self.assertEqual(self.state_path.read_text(), "{}")

    def test_failed_checks_preserve_each_stage_and_allow_a_valid_retry(self):
        for current, target in zip(
            ("DRAFT", "EVALUATED", "APPROVED", "DEPLOYED"),
            ("EVALUATED", "APPROVED", "DEPLOYED", "RETIRED"),
        ):
            for result in (False, None, 0, 1, "PASS", [True], {"ok": True}):
                with self.subTest(current=current, result=result):
                    before = self.set_state(current)
                    check = Mock(return_value=result)
                    with self.assertRaisesRegex(PromotionBlocked, "check failed"):
                        self.registry.promote(
                            "tenant", self.sha, target, iter([lambda *_: True, check]),
                        )
                    check.assert_called_once_with(self.card, self.evidence)
                    self.assertEqual(self.state_path.read_bytes(), before)
                    response = self.registry.promote(
                        "tenant", self.sha, target, iter([lambda *_: True]),
                    )
                    self.assertEqual(response, {
                        "sha": self.sha, "state": target, "evidence": self.evidence,
                    })
                    self.assertEqual(json.loads(self.state_path.read_text())["state"], target)

    def test_empty_checks_preserve_state_at_every_stage(self):
        for current, target in zip(
            ("DRAFT", "EVALUATED", "APPROVED", "DEPLOYED"),
            ("EVALUATED", "APPROVED", "DEPLOYED", "RETIRED"),
        ):
            with self.subTest(current=current):
                before = self.set_state(current)
                with self.assertRaisesRegex(PromotionBlocked, "explicit check"):
                    self.registry.promote("tenant", self.sha, target, iter(()))
                self.assertEqual(self.state_path.read_bytes(), before)

    def test_partial_approval_evidence_is_rejected_before_checks(self):
        for field in self.evidence:
            for value in (None, "", False, []):
                with self.subTest(field=field, value=value):
                    evidence = dict(self.evidence)
                    if value is None:
                        evidence.pop(field)
                    else:
                        evidence[field] = value
                    (self.base / "evidence.json").write_text(json.dumps(evidence))
                    before = self.set_state("EVALUATED")
                    check = Mock(return_value=True)
                    with self.assertRaisesRegex(PromotionBlocked, "evidence incomplete"):
                        self.registry.promote("tenant", self.sha, "APPROVED", [check])
                    check.assert_not_called()
                    self.assertEqual(self.state_path.read_bytes(), before)

    def test_generator_failure_preserves_state(self):
        def checks():
            yield lambda *_: True
            raise RuntimeError("check source failed")

        before = self.state_path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "check source failed"):
            self.registry.promote("tenant", self.sha, "EVALUATED", checks())
        self.assertEqual(self.state_path.read_bytes(), before)


class NotebookCaptureUnits(unittest.TestCase):
    def test_empty_or_unverified_outputs_never_claim_replay(self):
        for outputs in ([], [None], [{"error": "failed"}], [2]):
            with self.subTest(outputs=outputs):
                session = {
                    "cells": ["1 + 1"], "outputs": outputs,
                    "reproducible": True, "replay_status": "PASSED",
                }
                before = json.dumps(session, sort_keys=True)
                captured = capture_notebook(session, {})
                self.assertIs(captured["reproducible"], False)
                self.assertEqual(captured["replay_status"], "NOT_RUN")
                self.assertEqual(captured["outputs"], outputs)
                self.assertEqual(captured["data_refs"], ())
                self.assertEqual(json.dumps(session, sort_keys=True), before)

    def test_capture_retains_hashes_and_references_without_replay(self):
        session = {"outputs": [], "cells": [], "data_references": ["synthetic-snapshot"]}
        environment = {"python": "synthetic", "dependencies": ["synthetic==1"]}
        captured = capture_notebook(session, environment)
        reordered = capture_notebook(dict(reversed(list(session.items()))), environment)
        self.assertEqual(captured, reordered)
        self.assertEqual(captured["session_hash"], hashlib.sha256(
            json.dumps(session, sort_keys=True, separators=(",", ":")).encode(),
        ).hexdigest())
        self.assertEqual(captured["env_hash"], hashlib.sha256(
            json.dumps(environment, sort_keys=True).encode(),
        ).hexdigest())
        self.assertEqual(captured["data_refs"], ["synthetic-snapshot"])
        changed = capture_notebook(session, {**environment, "python": "changed"})
        self.assertEqual(changed["session_hash"], captured["session_hash"])
        self.assertNotEqual(changed["env_hash"], captured["env_hash"])
        self.assertIs(changed["reproducible"], False)


if __name__ == '__main__':
    unittest.main()
