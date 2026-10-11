# tests/test_self_tests.py -- pytest wrappers around this codebase's real,
# already-implemented module self-tests. These are not new fake tests
# written to pad coverage; they call the exact same self_test() functions
# used throughout development and CI, so `pytest` becomes the single
# standard entry point for verifying the whole codebase.

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from chronos.manifold import _self_test as manifold_self_test
from chronos.qsdl_parser import _self_test as qsdl_parser_self_test
from chronos.qsdl_compiler import _self_test as qsdl_compiler_self_test
from chronos.test_harness import ChronosTestHarness
from chronos.theory.report import self_test_all
from chronos.phi_scaling import phi_power_exact

THEORY_DOMAINS = [
    "oscillator_array",
    "cryogenics",
    "superconductivity",
    "photonics",
    "anyons",
    "metrology",
    "qcd",
    "control",
    "error_correction",
    "chemistry",
]


def test_manifold_self_test():
    assert manifold_self_test() == "manifold._self_test: PASS"


def test_qsdl_parser_self_test():
    assert qsdl_parser_self_test().endswith("PASS")


def test_qsdl_compiler_self_test():
    assert qsdl_compiler_self_test() == "qsdl_compiler._self_test: PASS"


def test_full_pipeline_harness():
    assert ChronosTestHarness().run_all_tests() is True


@pytest.mark.parametrize("domain", THEORY_DOMAINS)
def test_theory_domain_self_test(domain):
    results = self_test_all()
    assert domain in results
    assert results[domain] == f"{domain}._self_test: PASS"


def test_phi_power_exact_matches_binet_for_small_n():
    phi = (1 + np.sqrt(5)) / 2
    for n in range(1, 30):
        assert abs(phi_power_exact(n) - phi ** n) < 1e-6
