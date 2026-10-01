"""Tests for datasets registry."""
from quantum_compute_substrate.applications.datasets import DATASETS, by_domain, summary


class TestDatasets:
    def test_registry_populated(self):
        assert len(DATASETS) >= 4

    def test_domains_covered(self):
        s = summary()
        for d in ("particle_physics", "climate", "genomics", "quantum_chemistry"):
            assert s.get(d, 0) >= 1

    def test_by_domain_returns_list(self):
        assert isinstance(by_domain("climate"), list)
