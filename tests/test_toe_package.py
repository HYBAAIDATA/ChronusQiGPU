"""First-class package contract for ``toe``.

TOE ships as a top-level distribution package alongside ``kellogg`` and
``mla1517`` — not an ``Intelligence`` submodule and not a repo-root-only
monolith. These tests pin the promotion contract: public surface,
submodule importability, the *absence* of compatibility-alias modules
(the canonical implementation is the only implementation), and the
packaging metadata that puts ``toe`` into built distributions.
"""

import importlib
import sys
import tomllib
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import toe  # noqa: E402

_SUBMODULES = (
    "engine",
    "bridge",
    "expansion",
    "system",
    "operator_compilers",
    "causal_ladder",
    "manifold_bridge",
    "poincare_golden_11d",
    "hardened_unified_substrate",
    "strict_quantum",
)

# Pre-consolidation paths that must NOT resolve: there is exactly one
# implementation per concept, at the canonical location. Alias modules
# were deliberately removed; importing a stale path must fail loudly.
_RETIRED_PATHS = (
    "toe.quantum_tensor",
    "toe.exact_tensor",
    "toe.exact_field",
    "toe.tensor_ml",
    "Intelligence.toe_bridge",
    "Intelligence.toe_expansion",
    "Intelligence.toe_operator_compilers",
    "Intelligence.toe_system",
    "Intelligence.causal_ladder",
    "Intelligence.poincare_golden_11d",
    "Intelligence.manifold_bridge",
    "Intelligence.hardened_unified_substrate",
    "Intelligence.strict_quantum",
    "Intelligence.quantum_tensor",
    "Intelligence.exact_tensor",
    "Intelligence.intelligences",
    "Intelligence.intelligences.causal",
    "Intelligence.intelligences.quantum",
)


class ToePackageSurfaceTests(unittest.TestCase):
    def test_toe_is_a_package_not_a_module(self) -> None:
        self.assertTrue(hasattr(toe, "__path__"))
        self.assertEqual(Path(toe.__file__).name, "__init__.py")

    def test_public_surface_resolves(self) -> None:
        for name in toe.__all__:
            self.assertTrue(hasattr(toe, name), f"toe.__all__ exports missing {name}")

    def test_core_import_needs_only_numpy(self) -> None:
        # Optional surfaces (turing_core, mtheory, Intelligence.*,
        # mla1517.scale, nltk) are lazy: ``import toe`` must already have
        # succeeded for this test to run.
        self.assertIsNotNone(toe.TOEBridge)
        self.assertIsNotNone(toe.PredictiveEngine)

    def test_documented_submodules_importable(self) -> None:
        for name in _SUBMODULES:
            with self.subTest(module=name):
                module = importlib.import_module(f"toe.{name}")
                self.assertIs(sys.modules[f"toe.{name}"], module)

    def test_intelligences_subpackage(self) -> None:
        pkg = importlib.import_module("toe.intelligences")
        for name in pkg.__all__:
            self.assertTrue(hasattr(pkg, name), f"toe.intelligences missing {name}")


class ToeNoShimsTests(unittest.TestCase):
    def test_retired_paths_do_not_resolve(self) -> None:
        for retired in _RETIRED_PATHS:
            with self.subTest(module=retired):
                sys.modules.pop(retired, None)
                with self.assertRaises(ModuleNotFoundError):
                    importlib.import_module(retired)


class ToePackagingTests(unittest.TestCase):
    """``toe`` must be in the built distribution, not just the checkout."""

    def test_pyproject_declares_toe_packages(self) -> None:
        meta = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        packages = meta["tool"]["setuptools"]["packages"]
        self.assertIn("toe", packages)
        self.assertIn("toe.intelligences", packages)
        package_dir = meta["tool"]["setuptools"]["package-dir"]
        self.assertEqual(package_dir["toe"], "toe")
        self.assertEqual(package_dir["kellogg"], "kellogg")


if __name__ == "__main__":
    unittest.main()
