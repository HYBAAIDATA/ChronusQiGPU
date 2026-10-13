#!/usr/bin/env bash
# Scaffold the exact source layout without overwriting existing files.
set -euo pipefail

ROOT="${1:-pythia-production-mining}"
mkdir -p "$ROOT"

# Canonical Python/control plane.
mkdir -p "$ROOT/python/chronus/mla1517/mining" "$ROOT/tests"
# Native, accelerator, persistence, deployment, and release surfaces.
mkdir -p "$ROOT/host" "$ROOT/contracts" "$ROOT/kernels" "$ROOT/rtl" \
  "$ROOT/cpp/include" "$ROOT/cpp/src" "$ROOT/hardware" "$ROOT/docker" \
  "$ROOT/scripts" "$ROOT/docs" "$ROOT/results" \
  "$ROOT/.github/workflows"

# Package markers are created only when absent; existing source is preserved.
touch "$ROOT/python/chronus/mla1517/__init__.py" "$ROOT/python/chronus/mla1517/mining/__init__.py"
touch "$ROOT/tests/__init__.py"

cat > "$ROOT/.env.example" <<'ENV'
# Copy to .env locally; never commit credentials.
MLA1517_STRATUM_USER=
MLA1517_STRATUM_PASSWORD="" # set locally
MLA1517_ENABLE_LIVE_SUBMIT=0
MLA1517_LIVE_APPROVAL_ID=
MLA1517_GPU_BACKEND=unavailable
MLA1517_STRICT_HARDWARE_CI=0
ENV

cat > "$ROOT/README.md" <<'MD'
# PYTHIA production mining

Python is the canonical mining control plane. The frontend is an operator UI;
it does not hash, construct Stratum jobs, validate targets, or submit shares.

The production path is:

```text
Frontend → Python API → coordinator → live Stratum job → complete deterministic
search ordering → observed TOE context → actual hardware/reference executor
→ SHA256d → negotiated target → PRIME-DB/telemetry → proof-checked submit
```

No hardware, pool acceptance, or hashrate is claimed by this scaffold.
Run `make test` and `make release` only after the complete source tree and the
required native toolchains are present.
MD

cat > "$ROOT/pyproject.toml" <<'TOML'
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "pythia-production-mining"
version = "0.1.0"
description = "Truth-labelled Python mining control plane"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
test = ["pytest>=7.4,<10"]
opencl = ["pyopencl>=2024.1"]

[tool.setuptools]
package-dir = {"" = "python"}

[tool.setuptools.packages.find]
where = ["python"]
TOML

cat > "$ROOT/RUNBOOK.md" <<'MD'
# PYTHIA production runbook

1. Install Python 3.11+ and the declared dependencies.
2. Run the Python, native, and release gates; record unavailable tools as
   `NOT_RUN — <tool unavailable>`.
3. Keep live submission disabled until a real subscription, notify job, target,
   and proof-checked candidate are observed.
4. Require a physical OpenCL/MLA1517 device before labelling execution
   `measured_hardware`.
5. Keep CPU reference execution explicitly labelled `measured_cpu_reference`.
6. Do not report pool acceptance or hashrate without an actual pool response and
   measured wall-clock counters.

Deployment requirements include a supported OpenCL 2.0+ device, native C/C++
toolchains, PRIME-DB storage, shared-memory permissions, pool credentials held
outside the repository, and explicit live-submission approval. None of these
physical or external conditions is satisfied by scaffolding alone.
MD

echo "PYTHIA scaffold created at $ROOT"
find "$ROOT" -maxdepth 3 -type d | sort
