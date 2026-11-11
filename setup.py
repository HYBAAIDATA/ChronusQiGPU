"""Build entry point: a plain setup() unless HYBA_NATIVE_BUILD=1.

All metadata and package discovery live in pyproject.toml. When
HYBA_NATIVE_BUILD is unset (or 0) this file calls setup() with no arguments,
so every existing pip, build and CI flow behaves exactly as it would without
this file.

HYBA_NATIVE_BUILD=1 selects the native profile used inside the sealed
appliance image (defence in depth; never a participant deliverable on its
own, see packaging/partner/README.md): the modules listed in
packaging/partner/native-modules.txt are compiled with Cython, symbols are
stripped on Linux and the Python sources of compiled modules are left out of
the wheel. HYBA_LEASE_TRUST_STORE may name a public-key trust store that is
embedded as chronus/licensing/trust_store.json; otherwise the committed
(empty) store is shipped and every lease verification fails closed.
"""

import os
import sys
from pathlib import Path

from setuptools import setup

_FLAG = os.environ.get("HYBA_NATIVE_BUILD", "")


def _load_helper(root):
    import importlib.util

    path = root / "packaging" / "partner" / "native_modules.py"
    if not path.is_file():
        sys.exit(
            "HYBA_NATIVE_BUILD=1: packaging/partner/native_modules.py is missing; "
            "build the native profile from a source checkout (python -m build --wheel), not from an sdist"
        )
    spec = importlib.util.spec_from_file_location("hyba_native_modules", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _native_setup():
    root = Path(__file__).resolve().parent
    helper = _load_helper(root)
    try:
        modules = helper.resolve_native_modules(root, helper.read_patterns(root / helper.CONFIG_PATH))
        override = os.environ.get("HYBA_LEASE_TRUST_STORE")
        trust_store = helper.load_trust_store_override(override) if override else None
    except (helper.NativeBuildConfigError, OSError) as exc:
        sys.exit(f"HYBA_NATIVE_BUILD=1: {exc}")
    try:
        from Cython.Build import cythonize
    except ImportError:
        sys.exit(
            "HYBA_NATIVE_BUILD=1 requires Cython>=3.1 in the build environment: "
            "pip install 'cython>=3.1' build setuptools wheel, then python -m build --wheel --no-isolation"
        )
    from setuptools import Extension
    from setuptools.command.build_py import build_py

    compiled = frozenset(module.name for module in modules)
    link_args = ["-s"] if sys.platform.startswith("linux") else []
    extensions = cythonize(
        [Extension(module.name, [module.source], extra_link_args=list(link_args)) for module in modules],
        compiler_directives={
            "language_level": 3,
            "binding": True,
            "embedsignature": False,
            "annotation_typing": False,
        },
        build_dir=os.path.join("build", "cython"),
        quiet=True,
    )

    class NativeBuildPy(build_py):
        """Leaves compiled modules' sources out of the wheel and ships the trust store."""

        def find_package_modules(self, package, package_dir):
            return helper.filter_package_modules(super().find_package_modules(package, package_dir), compiled)

        def find_data_files(self, package, src_dir):
            files = helper.filter_data_files(package, src_dir, super().find_data_files(package, src_dir), compiled)
            committed = os.path.join(src_dir, helper.TRUST_STORE_NAME)
            if package == helper.TRUST_STORE_PACKAGE and os.path.isfile(committed) and committed not in files:
                files.append(committed)
            return files

        def run(self):
            super().run()
            helper.purge_build_lib(self.build_lib, compiled)
            if trust_store is not None:
                target = Path(self.build_lib, *helper.TRUST_STORE_PACKAGE.split("."), helper.TRUST_STORE_NAME)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(trust_store)

    print(
        f"HYBA_NATIVE_BUILD=1: compiling {len(modules)} modules: {', '.join(sorted(compiled))}; "
        f"trust store: {'embedded from HYBA_LEASE_TRUST_STORE' if trust_store else 'committed (empty)'}",
        file=sys.stderr,
    )
    setup(ext_modules=extensions, cmdclass={"build_py": NativeBuildPy})


if _FLAG in ("", "0"):
    setup()
elif _FLAG == "1":
    _native_setup()
else:
    sys.exit(f"HYBA_NATIVE_BUILD must be unset, 0 or 1 (got {_FLAG!r})")
