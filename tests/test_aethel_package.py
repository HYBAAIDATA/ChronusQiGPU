"""First-class package contract for ``aethel``.

Pins the promotion contract: canonical package location, single-source
``__version__``, packaging metadata, and the identity alias that wires
``toe.hardened_unified_substrate`` to the aethel implementation.
"""

import importlib
import sys
import tomllib
import unittest
from pathlib import Path

import aethel

_ROOT = Path(__file__).resolve().parent.parent


class AethelPackageSurfaceTests(unittest.TestCase):
    def test_aethel_is_a_package(self) -> None:
        self.assertTrue(hasattr(aethel, "__path__"))
        self.assertEqual(Path(aethel.__file__).name, "__init__.py")

    def test_public_surface_resolves(self) -> None:
        for name in aethel.__all__:
            self.assertTrue(
                hasattr(aethel, name), f"aethel.__all__ exports missing {name}"
            )

    def test_core_submodules_importable(self) -> None:
        for name in (
            "constants", "cassini", "zeckendorf", "primes", "compute",
            "gpu", "manifold", "unified", "shm", "errors", "fibonacci",
            "storage", "encoding", "geodesic", "selftest",
        ):
            with self.subTest(module=name):
                module = importlib.import_module(f"aethel.{name}")
                self.assertIs(sys.modules[f"aethel.{name}"], module)

    def test_version_single_source(self) -> None:
        """The only ``__version__`` literal in the package lives in
        ``aethel/__init__.py`` — every other module must derive from it."""
        aethel_dir = _ROOT / "aethel"
        for path in aethel_dir.glob("*.py"):
            if path.name == "__init__.py":
                continue
            src = path.read_text(encoding="utf-8")
            self.assertNotRegex(
                src,
                r'^__version__\s*=\s*["\']',
                f"{path.name} declares its own __version__",
            )
        self.assertRegex(aethel.__version__, r"^\d+\.\d+\.\d+$")


class AethelWiringTests(unittest.TestCase):
    def test_toe_path_is_identity_alias(self) -> None:
        """``toe.hardened_unified_substrate`` resolves to the exact same
        module object as ``aethel.hardened_unified_substrate``."""
        toe_module = importlib.import_module("toe.hardened_unified_substrate")
        aethel_module = importlib.import_module("aethel.hardened_unified_substrate")
        self.assertIs(toe_module, aethel_module)

    def test_consumers_reach_aethel_classes(self) -> None:
        """Symbols the toe/Intelligence consumers import come from aethel."""
        toe_module = importlib.import_module("toe.hardened_unified_substrate")
        for symbol in (
            "CassiniVerifier",
            "HardenedZeckendorfCodec",
            "GaloisPrimeSubstrate",
            "UnifiedSubstrate",
        ):
            obj = getattr(toe_module, symbol)
            self.assertTrue(
                obj.__module__.startswith("aethel."),
                f"{symbol} resolves to {obj.__module__}, not aethel",
            )


class AethelPackagingTests(unittest.TestCase):
    def test_pyproject_declares_aethel(self) -> None:
        meta = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        packages = meta["tool"]["setuptools"]["packages"]
        self.assertIn("aethel", packages)
        package_dir = meta["tool"]["setuptools"]["package-dir"]
        self.assertEqual(package_dir["aethel"], "aethel")
        data = meta["tool"]["setuptools"]["package-data"].get("aethel", [])
        self.assertIn("py.typed", data)

    def test_no_standalone_search_engine(self) -> None:
        """aethel.geodesic must import the engine, never reimplement it:
        no local nonce/enumeration/search algorithm is allowed."""
        src = (_ROOT / "aethel" / "geodesic.py").read_text(encoding="utf-8")
        self.assertIn("Intelligence.search_crystal", src)
        self.assertNotRegex(src, r"def\s+double_sha256")
        self.assertNotRegex(src, r"def\s+search\(")


if __name__ == "__main__":
    unittest.main()
