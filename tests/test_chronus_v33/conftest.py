# conftest.py -- shared fixtures and markers for the Chronos GPU test suite.
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure `src/` is importable whether pytest is invoked from the repo root
# or from tests/ itself.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


# ---------------------------------------------------------------------------
# Markers (registered so `pytest -m "not slow"` works without warnings)
# ---------------------------------------------------------------------------
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: fast, isolated unit tests")
    config.addinivalue_line("markers", "integration: multi-module pipeline tests")
    config.addinivalue_line("markers", "slow: long-running (high-res or large-n) tests")


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def smoke_scene_source() -> str:
    """Small, grammar-complete QSDL scene suitable for fast CI renders."""
    return (
        "scene smoke {\n"
        "  manifold M32\n"
        "  object sphere {\n"
        "    geometry sphere(radius=1.0, center=(0,0,0))\n"
        "    material glass {\n"
        "      dielectric = 1.5\n"
        "      absorption = 0.001\n"
        "      quantum { resonance = [0.5] }\n"
        "    }\n"
        "  }\n"
        "  light sun {\n"
        "    type = directional\n"
        "    position = (1,1,1)\n"
        "    intensity = 1.0\n"
        "    driving = zero()\n"
        "  }\n"
        "  camera {\n"
        "    resolution = (320, 180)\n"
        "    fov = 60.0\n"
        "    position = (0, 0, 5)\n"
        "    readout = { observables = [intensity, depth, normal] }\n"
        "  }\n"
        "  quality {\n"
        "    layers = 2\n"
        "    evolution_steps = 20\n"
        "    learning_rate = 0.08\n"
        "    damping = 0.01\n"
        "    seed = 0\n"
        "  }\n"
        "}\n"
    )


@pytest.fixture
def full_grammar_scene_source() -> str:
    """Exercises every major QSDL declaration form (manifold, object,
    geometry, material+quantum, transform, light, camera+readout, quality)."""
    return """
    scene grammar_probe {
        manifold M32
        object sphere_0 {
            geometry sphere(radius=1.0, center=(0,0,0))
            material glass {
                dielectric = 1.5
                absorption = 0.001
                quantum {
                    hamiltonian = diagonal(0.5)
                    coupling = uniform(0.1)
                    resonance = [0.5]
                }
            }
            transform {
                translate(0, 0, -2)
                scale(1.5, 1.5, 1.5)
                rotate((0, 1, 0), 45)
            }
        }
        light sun {
            type = directional
            position = (1, 1, 1)
            intensity = 1.0
            driving = zero()
        }
        camera {
            resolution = (160, 90)
            fov = 60.0
            position = (0, 0, 5)
            readout = {
                observables = [intensity, depth, normal]
                supersampling = 2
                tone_map = aces
            }
        }
        quality {
            layers = 2
            evolution_steps = 10
            learning_rate = 0.08
            damping = 0.01
            seed = 0
        }
    }
    """
