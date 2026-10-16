"""Ephemeral local test issuance, never an independent governance authority."""
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from euclid.emergence.trusted_core.access_control import GovernanceToken, QualificationAuthorization
from euclid.emergence.trusted_core.qualification_service import EmergentQualificationService


@pytest.fixture
def authorize_candidate(tmp_path):
    sequence = 0
    def configure(candidate, **service_options):
        nonlocal sequence
        sequence += 1
        key = Ed25519PrivateKey.generate()
        authorization = QualificationAuthorization(
            trusted_signers={("pytest-local-issuer", "test-officer"): key.public_key()},
            audience="pytest-philos", replay_path=tmp_path/f"replay-{sequence}.sqlite")
        service = EmergentQualificationService(authorization=authorization, **service_options)
        token = GovernanceToken.issue("test-officer",key,issuer="pytest-local-issuer",
            audience="pytest-philos",candidate_fingerprint=candidate.compute_fingerprint())
        return service, token
    return configure
