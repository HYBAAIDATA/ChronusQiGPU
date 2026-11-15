# Native build profile (sealed appliance, defence in depth)

This profile compiles selected modules to native extension modules with
Cython. It exists for one purpose: to add a layer inside the **sealed
appliance image** described in
[`docs/distribution/partner-distribution.md`](../../docs/distribution/partner-distribution.md).

> A compiled wheel is never a participant deliverable on its own. Any code
> shipped to a participant's machine can eventually be reverse engineered.
> Hosted execution is the default channel; on-premises delivery happens only
> inside the sealed appliance.

## Files

| File | Role |
| --- | --- |
| `../../setup.py` | Plain `setup()` unless `HYBA_NATIVE_BUILD=1`, so every existing pip, build and CI flow is unchanged. |
| `native-modules.txt` | Glob patterns (repository-relative, `.py` only, `#` comments) of the modules to compile. |
| `native_modules.py` | Standard-library helper used by `setup.py`, the workflow and the tests: resolves patterns to module names through the package roots `src` and `packages/turing/src`, filters build outputs and validates an embedded trust store. |
| `../../.github/workflows/partner-build.yml` | Builds the wheel, inspects it, installs it in a fresh virtual environment and runs the licensing tests against it. |

This directory deliberately has no `__init__.py`, so it can never shadow the
third-party `packaging` distribution on `sys.path`.

## Build

On Linux, with the CPython version of the appliance image and a C compiler:

```bash
python -m pip install "cython>=3.1" build setuptools wheel
HYBA_NATIVE_BUILD=1 \
HYBA_LEASE_TRUST_STORE=/secure/build-inputs/trust_store.json \
python -m build --wheel --no-isolation
```

- Build from a source checkout. The profile is not supported from an sdist
  or with `pip install -e`.
- `HYBA_NATIVE_BUILD` must be unset, `0` or `1`; any other value stops the
  build, so a typo can never produce a pure-Python wheel by accident.
- `HYBA_LEASE_TRUST_STORE` is optional. It names a public-key trust store
  (`hyba.trust-store/1`, at least one key) that is validated and written to
  `chronus/licensing/trust_store.json` inside the wheel. Without it the
  committed, empty store is shipped and every lease verification fails
  closed. There is no run-time override.

## What the profile does

1. Reads `native-modules.txt`, resolves each pattern to dotted module names
   and never compiles `__init__.py`. A pattern that matches nothing is
   skipped with a warning (packages that have not merged yet); the build
   fails if nothing resolves, if a match lies outside the package roots or if
   two files map to one module name.
2. Cythonizes with `language_level=3`, `binding=True`,
   `embedsignature=False` and `annotation_typing=False` (annotations keep
   Python semantics). Generated C goes to `build/cython/` and is not shipped.
3. Links with `-s` on Linux, stripping the symbol tables.
4. Overrides `build_py` so the wheel contains no `.py`, `.pyi`, `.c`,
   `.pyx` or `.html` file of a compiled module, removes stale copies from a
   reused build directory and ships the trust store.

The workflow fails unless every resolved module is present as exactly one
stripped `.so` and its sources are absent, then imports each module from the
installed wheel (outside the source tree) and checks that it is an
extension module.

## What compilation does and does not protect

It does:

- remove readable Python source, docstring signatures and symbol tables for
  the listed modules, which deters casual inspection and copying.

It does not:

- stop determined reverse engineering. Cython output is ordinary machine
  code that can be disassembled and decompiled; constants and string
  literals remain in the binary; module objects can still be introspected,
  traced and debugged at run time.
- protect anything not listed. Every unlisted module, every `__init__.py`
  and all package data ship as they are.
- protect the lease check by itself. Whoever controls the machine can
  replace the trust store file or patch the verifier.

The protection that carries weight is elsewhere: hosted execution (no engine
code leaves HYBA), the sealed appliance's attestation-gated image encryption,
and the written licence. Compilation only raises the effort for anyone who
gets past those layers.

## Limits of the artefact

- The wheel is tagged for one CPython version and platform (for example
  `cp313-cp313-linux_x86_64`) and is not `manylinux`-audited; build it for
  the exact interpreter in the appliance image.
- CI artefacts are kept for 7 days and are visible only to repository
  collaborators. They are build evidence, not deliverables.
- Never upload a wheel from this profile to PyPI or any public registry.
