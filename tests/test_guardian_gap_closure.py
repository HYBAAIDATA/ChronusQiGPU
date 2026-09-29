import unittest

from al_haras.conjunction import INTELLIGENCE_IDS
from al_haras.conjunction import MODE_IDS
from al_haras.conjunction import TOPOLOGY_IDS
from al_haras.conjunction import AnomalyState
from al_haras.conjunction import AttestationState
from al_haras.conjunction import IntegrityState
from al_haras.conjunction import OverallStatus
from al_haras.conjunction import SurfaceStatus
from al_haras.conjunction import SurfaceVerdict
from al_haras.conjunction import guardian_conjunction
from al_haras.conjunction import verify_conjunction_signature
from al_haras.identity import UnauthenticatedPrincipal
from al_haras.identity import VerifiedIdentity
from al_haras.identity import derive_authenticated_actor
from al_haras.middleware import disposition
from al_haras.middleware import is_privileged
from al_haras.schema import HotDescriptorV1
from al_haras.schema import reject_historical_schema
from al_haras.sovereign_entitlements import ReplayCache
from al_haras.sovereign_entitlements import SovereignEntitlement
from al_haras.sovereign_entitlements import SovereignEntitlementError
from al_haras.sovereign_entitlements import verify_sovereign_entitlement
from al_haras.witness import WitnessError
from al_haras.witness import anchor_checkpoint

KEY = b"k" * 32


def passed(ids):
    return tuple(SurfaceVerdict(i, SurfaceStatus.PASS, "e", ("checked",)) for i in ids)


class Tests(unittest.TestCase):
    def test_conjunction_requires_all_surfaces(self):
        ok = guardian_conjunction(
            modes=passed(MODE_IDS),
            topologies=passed(TOPOLOGY_IDS),
            intelligences=passed(INTELLIGENCE_IDS),
            anomaly=AnomalyState(),
            attestation=AttestationState("c", "d", True, True),
            integrity=IntegrityState(True, True, True, True),
            signing_key=KEY,
        )
        self.assertEqual(ok.overall, OverallStatus.ALLOW)
        self.assertTrue(verify_conjunction_signature(ok, KEY))
        self.assertFalse(verify_conjunction_signature(ok, b"x" * 32))
        broken = list(passed(TOPOLOGY_IDS))
        broken[0] = SurfaceVerdict(TOPOLOGY_IDS[0], SurfaceStatus.FAIL)
        deny = guardian_conjunction(
            modes=passed(MODE_IDS),
            topologies=broken,
            intelligences=passed(INTELLIGENCE_IDS),
            anomaly=AnomalyState(),
            attestation=AttestationState("c", "d", True, True),
            integrity=IntegrityState(True, True, True, True),
            signing_key=KEY,
        )
        self.assertEqual(deny.overall, OverallStatus.DENY)
        quarantine = guardian_conjunction(
            modes=passed(MODE_IDS),
            topologies=passed(TOPOLOGY_IDS),
            intelligences=passed(INTELLIGENCE_IDS),
            anomaly=AnomalyState(),
            attestation=AttestationState("c", "d", True, True),
            integrity=IntegrityState(False, True, True, True),
            signing_key=KEY,
        )
        self.assertEqual(quarantine.overall, OverallStatus.QUARANTINE)

    def test_unknown_degrades(self):
        intel = list(passed(INTELLIGENCE_IDS))
        intel[-1] = SurfaceVerdict(INTELLIGENCE_IDS[-1], SurfaceStatus.UNAVAILABLE)
        v = guardian_conjunction(
            modes=passed(MODE_IDS),
            topologies=passed(TOPOLOGY_IDS),
            intelligences=intel,
            anomaly=AnomalyState(),
            attestation=AttestationState("c", "d", True, True),
            integrity=IntegrityState(True, True, True, True),
            signing_key=KEY,
        )
        self.assertEqual(v.overall, OverallStatus.DEGRADED)

    def test_actor_header_is_not_identity(self):
        with self.assertRaises(UnauthenticatedPrincipal):
            derive_authenticated_actor({}, service_audience="guardian")
        self.assertEqual(
            derive_authenticated_actor(
                {"mtls": VerifiedIdentity("mtls", "svc", True, "guardian")},
                service_audience="guardian",
            ),
            "svc",
        )

    def test_sovereign_replay_rejected(self):
        e = SovereignEntitlement(
            "issuer", "guardian", "svc", "tenant", ("hyba.security",), "jti", 1, 10, "hsm:key"
        )
        cache = ReplayCache()
        kwargs = dict(
            verifier=lambda *x: True,
            service_audience="guardian",
            required_capability="hyba.security",
            replay_cache=cache,
            active_key_refs=("hsm:key",),
            now=5,
        )
        verify_sovereign_entitlement(e, b"sig", **kwargs)
        with self.assertRaises(SovereignEntitlementError):
            verify_sovereign_entitlement(e, b"sig", **kwargs)

    def test_witness_requires_anchor(self):
        with self.assertRaises(WitnessError):
            anchor_checkpoint(
                subject_hash="h",
                chain_head=1,
                epoch=1,
                witness_identity="w",
                signer=lambda b: "sig",
                anchors=(lambda r: None,),
                now=1,
            )

    def test_schema_and_middleware(self):
        raw = HotDescriptorV1(*range(1, 13)).pack()
        self.assertEqual(len(raw), 64)
        with self.assertRaises(ValueError):
            reject_historical_schema({"d12_gauge": 1})
        self.assertTrue(is_privileged("/api/v1/mining/start"))
        self.assertEqual(disposition("DEGRADED"), (False, 503))


if __name__ == "__main__":
    unittest.main()
