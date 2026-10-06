"""Content-based discovery of Turing structures in a repository."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .specification import canonical_bytes


SCHEMA = "turing.discovery.report.v1"
SOURCE_SUFFIXES = {".py", ".ipynb"}
IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "site-packages",
}

COMPONENT_PATTERNS = {
    "tape": (
        r"\btape\b",
        r"\bcell(?:s)?\b",
        r"\bblank_symbol\b",
        r"\bread_symbol\b",
    ),
    "head": (
        r"\bhead(?:_position)?\b",
        r"\bmove_(?:left|right)\b",
        r"\bread/write\b",
    ),
    "state": (
        r"\bstate_vector\b",
        r"\bstate_register\b",
        r"\bfinite_state\b",
        r"\bquantum_state\b",
        r"\bstabilizer\b",
    ),
    "transition": (
        r"\btransition(?:s|_function|_map|_table)?\b",
        r"\bnext_state\b",
        r"\binstruction_set\b",
        r"\bdispatch\b",
    ),
    "universal": (
        r"\buniversal_machine\b",
        r"\bmachine_description\b",
        r"\binterpreter\b",
        r"\bsimulat(?:e|es|ion)\b",
    ),
    "halt": (
        r"\bhalt(?:ed|ing|_state)?\b",
        r"\baccept_state\b",
        r"\breject_state\b",
        r"\bstep_limit\b",
    ),
    "fold": (
        r"\bfold(?:ed|ing)?\b",
        r"\bunfold\b",
        r"\btableau\b",
        r"\bwitness\b",
    ),
    "quantum": (
        r"\bhilbert\b",
        r"\bunitar(?:y|ity)\b",
        r"\bqubit\b",
        r"\bamplitude\b",
        r"\bmeasurement\b",
    ),
    "clock": (
        r"\bclock\b",
        r"\btick\b",
        r"\bcontinuous_time\b",
        r"\bquantum_phase\b",
        r"\blucas_ladder\b",
        r"\bphi_rotation\b",
    ),
    "certificate": (
        r"\bcertificate\b",
        r"\battestation\b",
        r"\bmerkle\b",
        r"\bcontent_address",
        r"\bdigest\b",
    ),
    "verifier": (
        r"\bverif(?:y|ier|ication)\b",
        r"\binvariant\b",
        r"\breplay\b",
    ),
}


def _matches(text: str, component: str) -> tuple[str, ...]:
    return tuple(pattern for pattern in COMPONENT_PATTERNS[component] if re.search(pattern, text, re.I))


def _classify_one(text: str, choices: tuple[tuple[str, tuple[str, ...]], ...], default: str) -> str:
    lowered = text.lower()
    for name, markers in choices:
        if all(marker in lowered for marker in markers):
            return name
    return default


def _tape(text: str, evidence: dict[str, tuple[str, ...]]) -> str:
    if not evidence["tape"]:
        return "missing"
    has_classical = any(word in text.lower() for word in ("byte", "bit", "symbol", "gf(2)", "gf2"))
    has_quantum = bool(evidence["quantum"])
    has_fold = bool(evidence["fold"])
    if has_classical and has_quantum:
        return "hybrid"
    if has_quantum and has_fold:
        return "quantum_folded"
    if has_quantum:
        return "quantum_amplitude"
    bit_markers = (" bit", "byte", "gf2")
    return "classical_bit" if any(word in text.lower() for word in bit_markers) else "classical_symbol"


def _head(text: str, evidence: dict[str, tuple[str, ...]]) -> str:
    if not evidence["head"]:
        return "missing"
    lower = text.lower()
    if "measurement" in lower and "unitary" in lower:
        return "hybrid"
    if "measurement" in lower:
        return "quantum_measurement"
    if "unitary" in lower:
        return "quantum_unitary"
    if "nondetermin" in lower or "branching" in lower:
        return "classical_nondeterministic"
    return "classical_deterministic"


def _state(text: str, evidence: dict[str, tuple[str, ...]]) -> str:
    if not evidence["state"]:
        return "missing"
    lower = text.lower()
    classical = any(
        word in lower for word in ("finite_state", "state set", "enum")
    )
    quantum = any(word in lower for word in ("state_vector", "quantum_state", "stabilizer"))
    if classical and quantum:
        return "hybrid"
    if quantum and evidence["fold"]:
        return "quantum_folded"
    if quantum:
        return "quantum_register"
    return "infinite_classical" if "unbounded" in lower else "finite_classical"


def _transition(text: str, evidence: dict[str, tuple[str, ...]]) -> str:
    if not evidence["transition"]:
        return "missing"
    lower = text.lower()
    unitary = any(word in lower for word in ("unitary", "hamiltonian", "time_evolution"))
    folded = "fold" in lower
    if unitary and folded:
        return "hybrid"
    if unitary:
        return "unitary_evolution"
    if folded:
        return "folded_evolution"
    if "compiler" in lower:
        return "compiler"
    if "interpreter" in lower or "dispatch" in lower:
        return "interpreter"
    return "lookup_table"


def _universal(evidence: dict[str, tuple[str, ...]]) -> str:
    if evidence["universal"] and evidence["transition"] and evidence["halt"]:
        return "present"
    if evidence["universal"]:
        return "partial"
    return "absent"


def _clock(text: str, evidence: dict[str, tuple[str, ...]]) -> str:
    if not evidence["clock"]:
        return "missing"
    lower = text.lower()
    matches = [
        name
        for name, marker in (
            ("continuous_time", "continuous_time"),
            ("lucas_ladder", "lucas_ladder"),
            ("phi_rotation", "phi_rotation"),
            ("quantum_phase", "quantum_phase"),
            ("discrete_tick", "tick"),
        )
        if marker in lower
    ]
    return "hybrid" if len(matches) > 1 else (matches[0] if matches else "discrete_tick")


def _certificate(text: str, evidence: dict[str, tuple[str, ...]]) -> str:
    if not evidence["certificate"]:
        return "missing"
    lower = text.lower()
    if "merkle" in lower:
        return "merkle_rooted"
    if "hmac" in lower:
        return "hmac"
    if "signature" in lower or "signed" in lower:
        return "signed"
    if "sha256" in lower or "content_address" in lower or "digest" in lower:
        return "content_addressed"
    return "plain"


def _field(text: str) -> str:
    lower = text.lower()
    fields = set()
    if any(marker in lower for marker in ("zeta8", "ζ₈", "cyclotomic", "q_sqrt2_i")):
        fields.add("Q_zeta8")
    elif any(marker in lower for marker in ("sqrt2", "sqrt(2)", "√2")):
        fields.add("Q_sqrt2")
    if any(marker in lower for marker in ("gaussian rational", "q_i", "complexfraction")):
        fields.add("Q_i")
    if any(marker in lower for marker in ("fraction(", "from fractions import", "rational(")):
        fields.add("Q")
    if any(marker in lower for marker in ("gf(2)", "gf2", "bitwise", " xor ", "^=")):
        fields.add("GF2")
    if any(marker in lower for marker in ("float(", "np.float", "dtype=float", "cmath.", "math.")):
        fields.add("float")
    return "missing" if not fields else (next(iter(fields)) if len(fields) == 1 else "mixed")


def _role(evidence: dict[str, tuple[str, ...]]) -> str:
    for component in (
        "verifier",
        "certificate",
        "universal",
        "transition",
        "head",
        "tape",
        "clock",
        "state",
        "fold",
    ):
        if evidence[component]:
            return component
    return "other"


def _source_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".ipynb":
        payload = json.loads(text)
        return "\n".join(
            "".join(cell.get("source", ()))
            for cell in payload.get("cells", ())
            if cell.get("cell_type") == "code"
        )
    return text


def _symbols(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return (), ()
    functions = sorted(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    classes = sorted(node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
    return tuple(functions), tuple(classes)


@dataclass(frozen=True)
class TuringModule:
    path: str
    kind: str
    lines: int
    sha256: str
    functions: tuple[str, ...]
    classes: tuple[str, ...]
    tape: str
    head: str
    state: str
    transition: str
    universal: str
    clock: str
    certificate: str
    field: str
    evidence: dict[str, tuple[str, ...]]
    gaps: tuple[str, ...]


@dataclass
class TuringDiscoveryReport:
    timestamp: str
    commit: str
    modules: list[TuringModule]
    summary: dict[str, int]
    schema: str = SCHEMA
    report_digest: str = ""

    def digest_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("timestamp")
        payload.pop("report_digest")
        return payload

    def seal(self) -> "TuringDiscoveryReport":
        self.report_digest = hashlib.sha256(
            b"turing-discovery-v1\0" + canonical_bytes(self.digest_payload())
        ).hexdigest()
        return self

    def verify(self) -> bool:
        expected = hashlib.sha256(
            b"turing-discovery-v1\0" + canonical_bytes(self.digest_payload())
        ).hexdigest()
        if self.report_digest != expected:
            raise ValueError("discovery report digest mismatch")
        return True

    def to_json(self) -> str:
        self.verify()
        return json.dumps(asdict(self), sort_keys=True, indent=2) + "\n"


def _candidate(evidence: dict[str, tuple[str, ...]]) -> bool:
    structural = sum(
        bool(evidence[name])
        for name in ("tape", "head", "transition", "universal", "halt")
    )
    quantum_machine = bool(evidence["quantum"]) and bool(evidence["state"]) and (
        bool(evidence["transition"]) or bool(evidence["fold"])
    )
    certified_runtime = bool(evidence["certificate"]) and (
        structural > 0 or bool(evidence["quantum"])
    )
    return structural >= 2 or quantum_machine or certified_runtime


def discover_repository(
    root: str | Path,
    *,
    commit: str,
    timestamp: str | None = None,
) -> TuringDiscoveryReport:
    root_path = Path(root).resolve()
    modules: list[TuringModule] = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        relative = path.relative_to(root_path)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        text = _source_text(path)
        evidence = {name: _matches(text, name) for name in COMPONENT_PATTERNS}
        if not _candidate(evidence):
            continue
        functions, classes = _symbols(text)
        classifications = {
            "tape": _tape(text, evidence),
            "head": _head(text, evidence),
            "state": _state(text, evidence),
            "transition": _transition(text, evidence),
            "universal": _universal(evidence),
            "clock": _clock(text, evidence),
            "certificate": _certificate(text, evidence),
            "field": _field(text),
        }
        gaps = tuple(
            name
            for name in ("tape", "head", "state", "transition", "clock", "certificate", "field")
            if classifications[name] == "missing"
        )
        modules.append(
            TuringModule(
                path=relative.as_posix(),
                kind=_role(evidence),
                lines=len(text.splitlines()),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                functions=functions,
                classes=classes,
                evidence=evidence,
                gaps=gaps,
                **classifications,
            )
        )
    complete = sum(
        all(getattr(module, name) != "missing" for name in ("tape", "head", "state", "transition"))
        for module in modules
    )
    certified = sum(module.certificate != "missing" for module in modules)
    exact = sum(module.field not in ("float", "mixed", "missing") for module in modules)
    summary = {
        "total_modules": len(modules),
        "complete_machines": complete,
        "partial_machines": len(modules) - complete,
        "absent_machines": 0 if modules else 1,
        "certified_modules": certified,
        "uncertified_modules": len(modules) - certified,
        "exact_modules": exact,
        "float_modules": sum(module.field in ("float", "mixed") for module in modules),
    }
    return TuringDiscoveryReport(
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        commit=commit,
        modules=modules,
        summary=summary,
    ).seal()


def git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--commit")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    root = Path(args.root)
    report = discover_repository(root, commit=args.commit or git_commit(root))
    rendered = report.to_json()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
