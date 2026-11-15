"""Training curriculum leakage, adversarial and end-to-end evaluation gates."""
import hashlib
import unittest
from dataclasses import replace

from euclid.swarm_curriculum import LeaderCurriculum, SkillCase, train_leadership
from euclid.swarm_evolution import LEADER_SKILLS, SwarmRefused


def curriculum():
    def partition(label):
        return tuple(
            SkillCase(
                f"{label}-{i}", f"lineage-{label}-{i}", skill,
                {"scenario": f"{label}-{i}", "skill": skill},
                {"verdict": "safe"},
            )
            for i, skill in enumerate(sorted(LEADER_SKILLS))
        )
    return LeaderCurriculum(
        "lead", "mission", "a" * 40,
        partition("train"), partition("validation"),
        partition("adversarial"), partition("final"),
    )


class LeadershipTrainingTests(unittest.TestCase):
    def test_train_real_callbacks_and_attestation_boundary(self):
        observed = {"trained_on": [], "evaluated_on": []}

        def train(cases):
            observed["trained_on"] = [c.case_id for c in cases]
            return {"checkpoint_id": "checkpoint-1", "sha256": hashlib.sha256(b"candidate").hexdigest()}

        def evaluate(checkpoint, case):
            self.assertEqual(checkpoint, "checkpoint-1")
            observed["evaluated_on"].append(case.case_id)
            return {"verdict": "safe"}
        report = train_leadership(curriculum(), train=train, evaluate=evaluate,
                                  accept=lambda c, result: dict(c.expected) == dict(result))
        self.assertEqual(report["outcome"], "READY_FOR_INDEPENDENT_ATTESTATION")
        self.assertEqual(len(observed["trained_on"]), 5)
        self.assertEqual(len(observed["evaluated_on"]), 15)
        self.assertFalse(set(observed["trained_on"]) & set(observed["evaluated_on"]))
        self.assertFalse(report["authority_granted"])
        self.assertFalse(report["checkpoint"]["bytes_independently_verified"])

    def test_training_does_not_acquire_authority_or_fake_training_success(self):
        report = train_leadership(
            curriculum(),
            train=lambda cases: {"checkpoint_id": "candidate", "sha256": "f" * 64},
            evaluate=lambda _, case: {"verdict": "unsafe" if case.case_id.startswith("adversarial") else "safe"},
            accept=lambda c, result: result["verdict"] == c.expected["verdict"],
        )
        self.assertEqual(report["outcome"], "FAILED")
        self.assertEqual(report["evaluation"]["adversarial"]["passed"], 0)
        self.assertFalse(report["authority_granted"])

    def test_cross_partition_duplicate_lineage_rejected(self):
        valid = curriculum()
        first = valid.training[0]
        duplicate = replace(valid.validation[0], lineage=first.lineage)
        with self.assertRaisesRegex(SwarmRefused, "leakage"):
            replace(valid, validation=(duplicate,) + valid.validation[1:])

    def test_content_overlap_rejected_even_when_id_differs(self):
        valid = curriculum()
        first = valid.training[0]
        duplicate = replace(valid.validation[0], inputs=first.inputs, expected=first.expected,
                            skill=first.skill)
        with self.assertRaisesRegex(SwarmRefused, "leakage"):
            replace(valid, validation=(duplicate,) + valid.validation[1:])

    def test_missing_leader_skill_partition_rejected(self):
        valid = curriculum()
        with self.assertRaisesRegex(SwarmRefused, "leadership skill"):
            replace(valid, adversarial=valid.adversarial[:-1])

    def test_missing_checkpoint_digest_rejected(self):
        with self.assertRaises(SwarmRefused):
            train_leadership(
                curriculum(), train=lambda _: {"checkpoint_id": "not-real"},
                evaluate=lambda _, __: {"verdict": "safe"},
                accept=lambda *_: True,
            )

    def test_test_data_never_sent_to_training_callback(self):
        valid = curriculum()

        def hostile(cases):
            assert set(c.case_id for c in cases) == set(c.case_id for c in valid.training)
            return {"checkpoint_id": "candidate", "sha256": "a" * 64}
        report = train_leadership(
            valid, train=hostile,
            evaluate=lambda _, __: {"verdict": "safe"},
            accept=lambda *_: True,
        )
        self.assertEqual(report["evaluation"]["final_test"]["total"], len(LEADER_SKILLS))

    def test_assessor_requires_literal_boolean(self):
        with self.assertRaises(SwarmRefused):
            train_leadership(
                curriculum(), train=lambda _: {"checkpoint_id": "candidate", "sha256": "b" * 64},
                evaluate=lambda _, __: {"verdict": "safe"},
                accept=lambda *_: 1,
            )

    def test_nonfinite_training_input_refused(self):
        case = SkillCase("x", "lineage", "swarm.plan", {"value": 1}, {"result": "pass"})
        with self.assertRaises(SwarmRefused):
            replace(case, inputs={"value": float("nan")})

    def test_no_callbacks_refused_before_training(self):
        with self.assertRaises(SwarmRefused):
            train_leadership(curriculum(), train=None, evaluate=None, accept=None)


if __name__ == "__main__":
    unittest.main()
