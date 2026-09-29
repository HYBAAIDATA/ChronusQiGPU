import unittest
from hyba_profiles import (
    AssemblyIntent,
    GateStatus,
    ModuleEvidence,
    PROFILES,
    Tier,
    authorize_placement,
    compile_assembly,
    verify_lock,
)
from hyba_profiles.tiers import ProofRequired

KEY = b"k" * 32


def intent(profile, missing=()):
    spec = PROFILES[profile]
    modules = tuple(sorted(spec.required_modules - set(missing)))
    evidence = tuple(ModuleEvidence(m, "1.0", True, True, False, False, ("test",)) for m in modules)
    return AssemblyIntent(
        "test",
        profile,
        "seed",
        "generic",
        ("workload",),
        "regulated" if profile not in {"developer", "edge"} else "standard",
        "air_gapped" if profile == "sovereign" else "private",
        "exact",
        "continuous",
        ("cost",),
        modules,
        evidence,
        spec.dominant_tiers,
        profile != "developer",
        profile in {"edge", "sovereign"},
        profile == "sovereign",
        profile in {"enterprise", "sovereign", "hyperscaler"},
        profile in {"enterprise", "sovereign", "hyperscaler"},
        False,
    )


class ProfileTests(unittest.TestCase):
    def test_tier_enforcement(self):
        with self.assertRaises(ProofRequired):
            authorize_placement(tier=Tier.T0, cassini_valid=False, lineage_present=True)
        self.assertTrue(
            authorize_placement(
                tier=Tier.T4, cassini_valid=True, lineage_present=True
            ).lineage_required
        )

    def test_all_profiles_compile_and_lock_verifies(self):
        for profile in ("developer", "edge", "enterprise", "sovereign", "hyperscaler"):
            result = compile_assembly(intent(profile), signing_key=KEY)
            self.assertTrue(verify_lock(result, KEY))
            self.assertFalse(result.gate.blockers)
            self.assertIn(
                result.gate.status, {GateStatus.ACCEPTED, GateStatus.EXTERNAL_ASSESSMENT_REQUIRED}
            )

    def test_missing_required_module_rejects(self):
        result = compile_assembly(intent("enterprise", ("vault",)), signing_key=KEY)
        self.assertEqual(result.gate.status, GateStatus.REJECTED)
        self.assertIn("module:vault", result.gate.blockers)

    def test_profile_name_does_not_bypass_sovereign_controls(self):
        value = intent("sovereign")
        value = AssemblyIntent(**{**value.__dict__, "air_gapped": False})
        self.assertEqual(compile_assembly(value, signing_key=KEY).gate.status, GateStatus.REJECTED)


if __name__ == "__main__":
    unittest.main()
