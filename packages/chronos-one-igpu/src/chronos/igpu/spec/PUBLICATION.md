# Standalone package publication

The completed original core is retained. Enhancements are additive Python modules and small facade/routing changes. `validation/CORE_PRESERVATION.json` lists hashes for every original source file. No original source module is removed.

## Release contents

- installable wheel and source distribution;
- exact-core and enhancement regression suites;
- operator CLI, authenticated service and declared optional Apple/OpenCL extras;
- compatible dependency range and tested environment lock;
- package metadata/LICENSE and distribution validation;
- Linux/Windows/macOS × Python 3.10–3.13 CI definition;
- source-to-code record, supplied notes, public-framework provenance and executed evidence.

```bash
python -m pip install chronos_gpu-3.7.0-py3-none-any.whl
chronos-igpu doctor
chronos-igpu family 10 12 15 > family.json
chronos-igpu verify-family family.json
```

For a source build:

```bash
python -m pip install .[dev]
python -m pytest -q
python -m build
python -m twine check dist/*
```

Wheel and sdist can be submitted to the chosen registry today. This deliverable does not upload a package or claim the `chronos-gpu` name is available on a public registry. Review the project name/ownership, choose your registry and configure trusted publishing/private credentials before uploading. Tokens never belong in this archive.

The CI definition is delivered, not represented as an already executed multi-OS matrix. Tested Linux results are separately recorded. Production readiness must be claimed per supported operation and tested target, not inferred from a wheel being buildable. Native core paths are tested; Apple/OpenCL hardware, Docker deployment and the previously identified missing ISA/geometry/pool extensions retain their recorded status.

## Upgrade compatibility

- Existing public symbols and original modules retained.
- OneIGPU default remains standalone, Golden Quantum enabled.
- Added family algebra/CLI and Apple tensor/neural bindings do not alter SHA256d or exact sequence authority.
- Optional neural ranking is a permutation only and requires an explicit supplied model.
- Evidence-chain appends are serialized for concurrent callers.
