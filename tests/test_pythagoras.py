"""Repository contracts for the wholesale PYTHAGORAS v12.2 implementation."""
import pythagoras
from pythagoras.engine.v6_5_manifold_escape import V65ManifoldEscapeEngine


def test_wholesale_version_and_engine_surface():
    assert pythagoras.__version__ == "12.2.0"
    assert hasattr(pythagoras, "PythagorasEngineAdapter")
    assert V65ManifoldEscapeEngine().meta_evolution is True
