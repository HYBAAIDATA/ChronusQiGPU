"""Generate the typed facade reference from the actual importable implementation."""

import argparse
from dataclasses import fields, is_dataclass
import inspect
from pathlib import Path
from turing_universal_quantum_computer import TuringPipeline
from turing_universal_quantum_computer import contracts, config, exceptions, interfaces

PROJECT = Path(__file__).resolve().parents[1]


def render():
    lines = [
        "# Generated typed API reference",
        "",
        "Generated from the actual public contracts and facade. Do not edit signatures manually.",
        "",
        "Read [mathematical contracts](mathematical-contracts.md) and [migration](compatibility.md) for semantics.",
        "",
        "## Facade",
        "",
        "The exported `TuringPipeline` name aliases `QuantumPipeline`; `VQCPipeline` remains distinct.",
        "",
    ]
    for name in (
        "__init__",
        "capabilities",
        "compile",
        "submit",
        "run",
        "estimate",
        "run_vqe",
        "get_job",
        "cancel_job",
        "close",
    ):
        method = getattr(TuringPipeline, name)
        lines += [
            f"### `{name}`",
            "",
            "```python",
            name + str(inspect.signature(method)),
            "```",
            "",
        ]
        if method.__doc__:
            lines += [inspect.cleandoc(method.__doc__), ""]
    lines += ["## Typed values", ""]
    for cls in (
        config.PipelineConfig,
        contracts.ParameterSpec,
        contracts.ParameterBindings,
        contracts.CircuitIR,
        contracts.FiniteAnsatz,
        contracts.BackendCapabilities,
        contracts.CompiledArtifact,
        contracts.ExecutionRequest,
        contracts.PauliZ,
        contracts.JobResult,
        contracts.Estimate,
        contracts.OptimizationResult,
    ):
        lines += [
            f"### `{cls.__name__}`",
            "",
            "```python",
            cls.__name__ + str(inspect.signature(cls)),
            "```",
            "",
        ]
        if is_dataclass(cls):
            lines += [
                "Fields: " + ", ".join("`" + field.name + "`" for field in fields(cls)) + ".",
                "",
            ]
    lines += ["## Extension protocols", ""]
    for name in ("Compiler", "ExecutionJob", "Backend", "Estimator", "Optimizer", "ErrorManager"):
        cls = getattr(interfaces, name)
        lines += [f"### `{name}`", ""]
        for method_name, member in cls.__dict__.items():
            if not method_name.startswith("_") and inspect.isfunction(member):
                lines += ["```python", method_name + str(inspect.signature(member)), "```", ""]
            elif isinstance(member, property):
                lines += [f"`{method_name}`: read-only property.", ""]
    lines += ["## Exceptions", ""]
    for name, cls in vars(exceptions).items():
        if inspect.isclass(cls) and cls.__module__ == exceptions.__name__:
            bases = ", ".join(base.__name__ for base in cls.__bases__)
            lines += [f"- `{name}` → {bases}: " + (inspect.getdoc(cls) or "").split("\n")[0]]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT / "docs/reference.md")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = render()
    if args.check:
        if not args.output.is_file() or args.output.read_text() != content:
            raise SystemExit("API reference drift: regenerate from the candidate implementation")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
