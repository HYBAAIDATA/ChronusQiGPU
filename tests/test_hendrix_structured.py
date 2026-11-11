"""Hendrix facade: identity with the legacy sources, oracle cross-checks, package hygiene."""

import ast
import importlib
import importlib.util
import inspect
import json
from pathlib import Path

from chronus.hendrix import GF257, DiscreteLogOracle, QuadraticResidueOracle
from chronus.hendrix import structured

ROOT = Path(__file__).resolve().parents[1]
HENDRIX_DIR = ROOT / "src" / "chronus" / "hendrix"
HENDRIX_SOURCES = sorted(HENDRIX_DIR.glob("*.py"))
HENDRIX_DOC = ROOT / "docs" / "hendrix.md"
HENDRIX_TESTS = sorted((ROOT / "tests").glob("test_hendrix_*.py"))
LEGACY_MODULES = (
    "chronus.math.f257_search",
    "chronus.quantum.grover",
    "chronus.quantum.metallic_search",
    "chronus.quantum.extension_search",
    "chronus.quantum.subspace",
)
INTEGER_MATH_HELPERS = {"comb", "factorial", "gcd", "isqrt", "lcm", "perm"}
FORBIDDEN_IMPORTS = {"cmath", "decimal", "numpy", "random", "statistics", "turing"}


def _load_purity_gate():
    spec = importlib.util.spec_from_file_location(
        "hendrix_purity_gate", ROOT / "scripts" / "ci" / "purity_gate.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _support(state):
    return frozenset(index for index, amplitude in enumerate(state.amplitudes) if amplitude)


def test_catalog_describes_every_export_exactly_once():
    exported = [name for name in structured.__all__ if name != "CATALOG"]
    assert "CATALOG" in structured.__all__
    assert len(exported) == len(set(exported))
    assert set(exported) == set(structured.CATALOG)


def test_facade_exports_are_the_source_objects():
    for name, entry in structured.CATALOG.items():
        source = importlib.import_module(entry[0])
        assert getattr(structured, name) is getattr(source, name), name


def test_facade_covers_every_public_routine_of_the_legacy_modules():
    for module_name in LEGACY_MODULES:
        module = importlib.import_module(module_name)
        public = {
            name
            for name, obj in vars(module).items()
            if not name.startswith("_")
            and (inspect.isfunction(obj) or inspect.isclass(obj))
            and obj.__module__ == module_name
        }
        assert public, module_name
        assert public <= set(structured.CATALOG), sorted(public - set(structured.CATALOG))
        assert all(structured.CATALOG[name][0] == module_name for name in public)
    assert {"f257_phases", "f257_phases_multi", "mod_inv"} <= set(structured.__all__)


def test_descriptions_are_single_lines_that_do_not_repeat_overclaims():
    for name, (module_name, description) in structured.CATALOG.items():
        assert module_name.startswith(("chronus.math.", "chronus.quantum.")), name
        assert description.strip() == description and description.endswith("."), name
        assert "\n" not in description, name
    for name in ("f257_phases", "f257_phases_multi"):
        assert "does not locate" in structured.CATALOG[name][1]
    for name in ("oracle_flip", "phase_iterate", "exact_search", "generalized_iterate"):
        assert "caller-supplied" in structured.CATALOG[name][1]
    for name in ("exact_subspace_search", "exact_extension_search", "exact_jform_subspace_search"):
        assert "does not identify" in structured.CATALOG[name][1]
    assert "not a validation" in structured.__doc__


def test_table_inverse_agrees_with_the_fermat_inverse():
    for x in range(1, 257):
        assert GF257.inverse(x) == structured.mod_inv(x)
        assert GF257.inverse(x + 257) == structured.mod_inv(x + 257)


def test_closed_form_phases_satisfy_their_identities_in_table_arithmetic():
    size, marked = 100, 1
    for u in range(1, 257):
        if (size * u + marked) % 257 == 0:
            continue
        alpha, mu, beta = structured.f257_phases(u, size, marked)
        assert GF257.mul(alpha, u) == (1 + u) % 257
        assert GF257.mul(mu, size) == (size * u + marked) % 257
        assert GF257.mul(beta, mu) == (-u) % 257
    for count in range(1, 6):
        for u in range(1, 257):
            alpha, mu, beta = structured.f257_phases_multi(u, size, count)
            marked_amplitude = GF257.mul(alpha, u)
            assert marked_amplitude in ((u + 1) % 257, (u - 1) % 257)
            sign = 1 if marked_amplitude == (u + 1) % 257 else -1
            assert GF257.mul(beta, size * u + sign * count) == (-size * u) % 257
            unmarked_total = GF257.mul(size - count, u)
            assert GF257.mul(mu, size) == (GF257.mul(count, marked_amplitude) + unmarked_total) % 257


def test_oracle_marked_sets_cross_check_the_dense_iterates():
    for y in (1, 2, 3, 128, 256):
        oracle = DiscreteLogOracle(GF257, y)
        num_qubits = oracle.domain_size.bit_length() - 1
        assert 1 << num_qubits == oracle.domain_size
        queried = frozenset(x for x in range(oracle.domain_size) if oracle(x))
        (index,) = queried
        assert _support(structured.exact_search(num_qubits, index)) == queried == oracle.marked()

    residues = QuadraticResidueOracle(GF257)
    queried = frozenset(k for k in range(residues.domain_size) if residues(k))
    state = structured.exact_search_multi(8, set(queried))
    assert _support(state) == queried == residues.marked()
    pair = structured.exact_subspace_search(8, residues.marked_count)
    assert pair.unmarked_amplitude == 0
    assert pair.marked_amplitude in (1, 256)


def test_hendrix_sources_pass_the_purity_gate_rules():
    gate = _load_purity_gate()
    assert {"__init__.py", "galois.py", "oracles.py", "structured.py"} <= {p.name for p in HENDRIX_SOURCES}
    for path in HENDRIX_SOURCES:
        assert gate.scan_file(path) == [], path
    doc = HENDRIX_DOC.read_text(encoding="utf-8")
    assert not [token for token in gate.THEATRE_TOKENS if token in doc]


def test_hendrix_sources_use_exact_integer_arithmetic_only():
    for path in HENDRIX_SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            where = (path.name, getattr(node, "lineno", None))
            if isinstance(node, ast.Constant):
                assert not isinstance(node.value, (float, complex)), where
            if isinstance(node, (ast.BinOp, ast.AugAssign)):
                assert not isinstance(node.op, ast.Div), where
            if isinstance(node, ast.Name):
                assert node.id not in {"float", "complex"}, where
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "math":
                    assert node.attr in INTEGER_MATH_HELPERS, where
            if isinstance(node, ast.Import):
                assert not {alias.name.split(".")[0] for alias in node.names} & FORBIDDEN_IMPORTS, where
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in FORBIDDEN_IMPORTS, where
                if node.module == "math":
                    assert {alias.name for alias in node.names} <= INTEGER_MATH_HELPERS, where


def test_core_modules_do_not_import_the_legacy_namespace():
    allowed = {"__future__", "array", "math", "chronus.hendrix.galois", "chronus.hendrix.oracles"}
    for name in ("__init__.py", "galois.py", "oracles.py"):
        tree = ast.parse((HENDRIX_DIR / name).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        assert imported <= allowed, (name, sorted(imported - allowed))


def test_hendrix_files_carry_no_claim_tokens():
    raw = json.loads((ROOT / "scripts" / "ci" / "claim_token_bytes.json").read_text())
    tokens = [bytes(item).lower() for item in raw]
    assert tokens
    for path in (*HENDRIX_SOURCES, HENDRIX_DOC, *HENDRIX_TESTS):
        data = path.read_bytes().lower()
        assert not [token for token in tokens if token in data], path.name
