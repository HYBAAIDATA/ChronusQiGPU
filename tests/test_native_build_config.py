"""Native (Cython) build profile: module resolution and setup.py wiring, without Cython."""

import base64
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_helper():
    spec = importlib.util.spec_from_file_location(
        "hyba_native_modules_under_test", ROOT / "packaging" / "partner" / "native_modules.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


native = _load_helper()


def _raises(expected, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except expected as exc:
        return exc
    raise AssertionError(f"{expected.__name__} was not raised")


def _tree(root, *paths):
    for relative in paths:
        path = Path(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("VALUE = 1\n", encoding="utf-8")


def _resolve(root, patterns, warnings=None):
    sink = warnings if warnings is not None else []
    return native.resolve_native_modules(root, patterns, warn=sink.append)


def test_patterns_resolve_to_dotted_module_names():
    with tempfile.TemporaryDirectory() as root:
        _tree(
            root,
            "src/chronus/math/__init__.py",
            "src/chronus/math/alpha.py",
            "src/chronus/math/beta.py",
            "src/chronus/math/notes.txt",
            "packages/turing/src/turing/__init__.py",
            "packages/turing/src/turing/algebra/__init__.py",
            "packages/turing/src/turing/algebra/ring.py",
        )
        modules = _resolve(root, ["src/chronus/math/*.py", "packages/turing/src/turing/algebra/*.py"])
        assert [module.name for module in modules] == ["chronus.math.alpha", "chronus.math.beta", "turing.algebra.ring"]
        assert [module.source for module in modules] == [
            "src/chronus/math/alpha.py",
            "src/chronus/math/beta.py",
            "packages/turing/src/turing/algebra/ring.py",
        ]
        assert native.module_name("packages/turing/src/turing/algebra/ring.py") == "turing.algebra.ring"


def test_init_modules_are_never_compiled():
    with tempfile.TemporaryDirectory() as root:
        _tree(root, "src/chronus/math/__init__.py", "src/chronus/math/alpha.py", "src/chronus/other/__init__.py")
        warnings = []
        modules = _resolve(root, ["src/chronus/**/*.py", "src/chronus/other/__init__.py"], warnings)
        assert [module.name for module in modules] == ["chronus.math.alpha"]
        assert all(not module.source.endswith("__init__.py") for module in modules)
        assert len(warnings) == 1 and "src/chronus/other/__init__.py" in warnings[0]


def test_missing_patterns_are_skipped_with_a_warning():
    with tempfile.TemporaryDirectory() as root:
        _tree(root, "src/chronus/licensing/__init__.py", "src/chronus/licensing/lease.py")
        warnings = []
        modules = _resolve(root, ["src/chronus/hendrix/*.py", "src/chronus/licensing/*.py"], warnings)
        assert [module.name for module in modules] == ["chronus.licensing.lease"]
        assert warnings == ["native build: pattern 'src/chronus/hendrix/*.py' matched no compilable module; skipped"]


def test_nothing_resolved_is_an_error():
    with tempfile.TemporaryDirectory() as root:
        _tree(root, "src/chronus/math/__init__.py")
        error = _raises(native.NativeBuildConfigError, _resolve, root, ["src/chronus/math/*.py", "src/missing/*.py"])
        assert "no module resolved" in str(error)
        _raises(native.NativeBuildConfigError, _resolve, root, [])


def test_pattern_file_syntax():
    text = "# comment\n\nsrc/chronus/math/*.py  # trailing comment\nsrc/chronus/math/*.py\n  packages/turing/src/turing/x.py\n"
    assert native.parse_patterns(text) == ["src/chronus/math/*.py", "packages/turing/src/turing/x.py"]
    for unsafe in ("/etc/*.py", "../outside/*.py", "src\\chronus\\*.py", "~/x.py", "src/chronus/data/*.json"):
        _raises(native.NativeBuildConfigError, native.parse_patterns, unsafe)


def test_unmappable_matches_are_rejected():
    with tempfile.TemporaryDirectory() as root:
        _tree(root, "scripts/tool.py", "src/chronus/bad-name.py", "src/turing/x.py", "packages/turing/src/turing/x.py")
        _raises(native.NativeBuildConfigError, _resolve, root, ["scripts/*.py"])
        _raises(native.NativeBuildConfigError, _resolve, root, ["src/chronus/*.py"])
        error = _raises(native.NativeBuildConfigError, _resolve, root, ["src/turing/x.py", "packages/turing/src/turing/x.py"])
        assert "turing.x" in str(error)


def test_repository_profile_resolves_the_licensing_modules():
    warnings = []
    patterns = native.read_patterns(ROOT / native.CONFIG_PATH)
    modules = native.resolve_native_modules(ROOT, patterns, warn=warnings.append)
    names = {module.name for module in modules}
    expected = {"chronus.licensing." + stem for stem in ("canonical", "errors", "fingerprint", "lease")}
    assert expected <= names
    assert not any(name.endswith("__init__") for name in names)
    for module in modules:
        assert (ROOT / module.source).is_file()
        assert native.module_name(module.source) == module.name


def test_build_py_filters_drop_compiled_sources():
    compiled = frozenset({"chronus.licensing.lease"})
    entries = [
        ("chronus.licensing", "__init__", "src/chronus/licensing/__init__.py"),
        ("chronus.licensing", "lease", "src/chronus/licensing/lease.py"),
    ]
    assert native.filter_package_modules(entries, compiled) == [entries[0]]
    src_dir = os.path.join("src", "chronus", "licensing")
    files = [os.path.join(src_dir, name) for name in ("lease.c", "lease.pyi", "lease.html", "trust_store.json", "py.typed")]
    kept = native.filter_data_files("chronus.licensing", src_dir, files, compiled)
    assert kept == [os.path.join(src_dir, "trust_store.json"), os.path.join(src_dir, "py.typed")]
    with tempfile.TemporaryDirectory() as build_lib:
        _tree(build_lib, "chronus/licensing/lease.py", "chronus/licensing/lease.c", "chronus/licensing/canonical.py")
        removed = native.purge_build_lib(build_lib, compiled)
        assert sorted(path.name for path in removed) == ["lease.c", "lease.py"]
        assert Path(build_lib, "chronus/licensing/canonical.py").is_file()


def test_trust_store_override_is_validated():
    key = base64.b64encode(bytes(range(32))).decode("ascii")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory, "trust_store.json")
        path.write_text(json.dumps({"keys": {"hyba-lease-2026": key}, "schema": "hyba.trust-store/1"}, indent=2))
        embedded = native.load_trust_store_override(path)
        assert json.loads(embedded) == {"keys": {"hyba-lease-2026": key}, "schema": "hyba.trust-store/1"}
        assert embedded.endswith(b"\n") and b" " not in embedded
        for broken in (
            {"keys": {}, "schema": "hyba.trust-store/1"},
            {"keys": {"hyba-lease-2026": base64.b64encode(b"short").decode("ascii")}, "schema": "hyba.trust-store/1"},
            {"keys": {"bad kid": key}, "schema": "hyba.trust-store/1"},
            {"keys": {"hyba-lease-2026": key}, "schema": "hyba.trust-store/2"},
        ):
            path.write_text(json.dumps(broken))
            _raises(native.NativeBuildConfigError, native.load_trust_store_override, path)


_FAKE_SETUPTOOLS = """
import json, os

class Extension:
    def __init__(self, name, sources, **kwargs):
        self.name = name
        self.sources = sources
        self.extra_link_args = kwargs.get("extra_link_args", [])

def setup(**kwargs):
    record = {"keys": sorted(kwargs)}
    if "ext_modules" in kwargs:
        record["ext_modules"] = [[e.name, e.sources, e.extra_link_args] for e in kwargs["ext_modules"]]
    with open(os.environ["FAKE_SETUP_RECORD"], "w") as handle:
        json.dump(record, handle)
"""

_FAKE_CYTHON = """
import json, os

def cythonize(extensions, **kwargs):
    with open(os.environ["FAKE_CYTHON_RECORD"], "w") as handle:
        json.dump(kwargs, handle)
    return extensions
"""


def _run_setup(directory, flag, with_cython):
    fake = Path(directory, "fake-site")
    files = {
        "setuptools/__init__.py": _FAKE_SETUPTOOLS,
        "setuptools/command/__init__.py": "",
        "setuptools/command/build_py.py": "class build_py:\n    pass\n",
    }
    if with_cython:
        files.update({"Cython/__init__.py": "", "Cython/Build.py": _FAKE_CYTHON})
    for relative, text in files.items():
        path = fake / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if not key.startswith("HYBA_")}
    env.update(
        PYTHONPATH=str(fake),
        FAKE_SETUP_RECORD=str(Path(directory, "setup.json")),
        FAKE_CYTHON_RECORD=str(Path(directory, "cython.json")),
    )
    if flag is not None:
        env["HYBA_NATIVE_BUILD"] = flag
    return subprocess.run(
        [sys.executable, str(ROOT / "setup.py")], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120
    )


def test_setup_py_is_a_plain_setup_without_the_flag():
    for flag in (None, "", "0"):
        with tempfile.TemporaryDirectory() as directory:
            result = _run_setup(directory, flag, with_cython=True)
            assert result.returncode == 0, result.stderr
            assert json.loads(Path(directory, "setup.json").read_text()) == {"keys": []}
            assert not Path(directory, "cython.json").exists()
    with tempfile.TemporaryDirectory() as directory:
        result = _run_setup(directory, "true", with_cython=True)
        assert result.returncode != 0 and "HYBA_NATIVE_BUILD must be" in result.stderr
        assert not Path(directory, "setup.json").exists()


def test_setup_py_native_profile_wiring():
    with tempfile.TemporaryDirectory() as directory:
        result = _run_setup(directory, "1", with_cython=True)
        assert result.returncode == 0, result.stderr
        record = json.loads(Path(directory, "setup.json").read_text())
        assert record["keys"] == ["cmdclass", "ext_modules"]
        names = [entry[0] for entry in record["ext_modules"]]
        assert "chronus.licensing.lease" in names and not any(name.endswith("__init__") for name in names)
        expected_link = ["-s"] if sys.platform.startswith("linux") else []
        assert all(entry[2] == expected_link for entry in record["ext_modules"])
        assert all(len(entry[1]) == 1 and entry[1][0].endswith(".py") for entry in record["ext_modules"])
        cython = json.loads(Path(directory, "cython.json").read_text())
        assert cython["compiler_directives"] == {
            "language_level": 3,
            "binding": True,
            "embedsignature": False,
            "annotation_typing": False,
        }
        assert cython["build_dir"] == os.path.join("build", "cython")
    with tempfile.TemporaryDirectory() as directory:
        result = _run_setup(directory, "1", with_cython=False)
        assert result.returncode != 0 and "requires Cython" in result.stderr
