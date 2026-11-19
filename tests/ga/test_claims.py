import pytest

pytestmark = pytest.mark.real

def test_all_registered_claims_pass():
    from ga import claim_checks  # noqa: F401  populates the registry
    from ga.claims import run

    failures = run()
    assert not failures, "\n".join(failures)


def test_claims_manifest_is_complete(tmp_path):
    """Every documented claim has a check; every check is documented."""
    from ga import claim_checks  # noqa: F401
    from ga.claims import CHECKS, manifest_check

    manifest = tmp_path / "claims.yaml"
    manifest.write_text("\n".join(sorted(CHECKS)))
    assert manifest_check(str(manifest)) == []
