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
