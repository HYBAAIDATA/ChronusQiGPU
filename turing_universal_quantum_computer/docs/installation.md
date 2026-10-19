# Installation and package checks

From the monorepo root, use a fresh environment. Kellogg is a real dependency,
not a vendored fork:

```bash
python -m venv .venv-turing
.venv-turing/bin/python -m pip install ./packaging/kellogg-tensor
.venv-turing/bin/python -m pip install './turing_universal_quantum_computer[dev]'
.venv-turing/bin/python examples/turing_public_api.py
```

The last command uses the monorepo example; a package-local example is also
available under `turing_universal_quantum_computer/examples/`.

For the locked research environment, use uv from the monorepo root:

```bash
uv sync --project turing_universal_quantum_computer --locked --group research
uv run --project turing_universal_quantum_computer --locked --group research \
  python scripts/run_turing_tests.py .
```

The lock references the local Kellogg distribution at its real packaging path.
It is a source-checkout research lock, not permission to publish a local-path
requirement to a registry. Public release dependency/version policy remains in
the existing guarded release workflow.

The test runner selects the canonical Python package before pytest encounters
the monorepo's nested namespace/configuration paths. Pass `--all` to run the full
native package suite. Installed wheel tests must also run outside the checkout;
source-path success alone does not establish package isolation.

## Qualification commands

From the monorepo root, after `uv sync`:

```bash
(cd turing_universal_quantum_computer && .venv/bin/python -m mypy --config-file mypy.ini)
uv run --project turing_universal_quantum_computer --locked --group research \
  python scripts/run_turing_tests.py . \
  turing_universal_quantum_computer/tests/test_package_organization.py \
  turing_universal_quantum_computer/tests/test_release_qualification.py
uv run --project turing_universal_quantum_computer --locked --group research \
  python turing_universal_quantum_computer/experiments/run_targeted_mutations.py \
  --output turing_universal_quantum_computer/results/local/mutations
```

To qualify distributable artifacts, build the Kellogg dependency wheel and TURING
wheel/sdist into a **new external directory** (do not mix candidate versions).
Export locked requirements and invoke:

```bash
uv export --project turing_universal_quantum_computer --locked --group research \
  --no-emit-project --no-emit-package hyba-kellogg-tensor \
  --format requirements-txt > /absolute/external/path/requirements.txt
uv run --project turing_universal_quantum_computer --locked --group research \
  python turing_universal_quantum_computer/experiments/qualify_artifacts.py \
  --dist-dir /absolute/external/path/dist \
  --requirements /absolute/external/path/requirements.txt \
  --output turing_universal_quantum_computer/results/local/artifact-qualification
```

Replace those illustrative absolute paths with real locations. The CI workflow
contains complete build commands. The qualifier rebuilds from the sdist, compares
all wheel file contents, creates two independent external environments, checks
dependencies, and runs the API/qualification consumers shipped in the sdist.
It records hashes, JUnit references and failures, and does **not** approve a release.
Byte identity is recorded separately from normalized content equality. For
repeat-build studies, control `SOURCE_DATE_EPOCH` from the actual candidate commit.

Generate or check the [API reference](reference.md) from the actual implementation:

```bash
uv run --project turing_universal_quantum_computer --locked --group research \
  python turing_universal_quantum_computer/experiments/generate_api_reference.py --check
```

Strict typing currently covers all definitions in the five explicitly listed
contract/configuration/protocol/exception/optimizer modules. Opaque legacy JSON
payloads and the entire existing engine are **not** claimed to be fully typed.
