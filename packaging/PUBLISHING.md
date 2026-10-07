# Publishing HYBA Software Limited packages to PyPI

This repository uses PyPI **trusted publishing**. GitHub Actions proves its
identity with a short-lived OIDC token; no permanent PyPI password or API token
belongs in repository secrets or workflow YAML.

The canonical release workflows are:

- KELLOGG: `.github/workflows/kellogg-tensor.yml`
- TURING: `.github/workflows/turing-release.yml`

Both are manual-dispatch publication workflows. Verification may run without
publishing. Production registry upload remains an explicit owner action.

## TURING publication contract

Distribution: `turing-universal-quantum-computer`  
Version: `1.0.0`  
Repository: `QuantumPhiRedux/PhiMiner`  
Dependency: `kellogg-tensor>=1.0`

The TURING release workflow enforces this sequence:

```text
verify exact KELLOGG 1.0.0 release artefact
→ build one staged TURING wheel + sdist
→ metadata / manifest / secret scan
→ clean installed-wheel verification on Python 3.11 / 3.12 / 3.13
→ deterministic cross-version fixture equality
→ complete TURING package tests
→ production-composition / custody / replay tests
→ checkout-bound acceptance gate
→ full benchmark suite including the 10,000-qubit exact voyage
→ TURING-owned Lean verification
→ machine-readable release verdict
→ optional reviewer-gated trusted publication of the exact verified artefact
```

The publishing job does **not** rebuild the package. It downloads
`turing-1.0.0-release`, rechecks the recorded SHA-256 digests, stages exactly
the verified wheel and sdist, and passes those files to
`pypa/gh-action-pypi-publish@release/v1`.

## Owner actions

1. Ensure GitHub Actions can start jobs for `QuantumPhiRedux/PhiMiner`. If
   account billing/spending limits still block Actions, resolve that first.
2. In PyPI, configure a pending trusted publisher for:
   - project: `kellogg-tensor`
   - owner: `QuantumPhiRedux`
   - repository: `PhiMiner`
   - workflow: `kellogg-tensor.yml`
   - environment: `pypi`
3. Configure the corresponding TestPyPI publisher with environment
   `testpypi`.
4. Configure TURING in PyPI:
   - project: `turing-universal-quantum-computer`
   - owner: `QuantumPhiRedux`
   - repository: `PhiMiner`
   - workflow: `turing-release.yml`
   - environment: `pypi`
5. Configure the corresponding TURING TestPyPI publisher with environment
   `testpypi`.
6. Create GitHub environments `testpypi` and `pypi` with HYBA Software
   Limited required reviewers.
7. Run the KELLOGG workflow and publish `kellogg-tensor==1.0.0` to production
   PyPI after its TestPyPI verification succeeds.
8. Run **TURING 1.0.0 release** with `publish=none`. Preserve
   `turing-release-verdict.json`; it must say `publishable: true`.
9. Run the TURING workflow with `publish=testpypi`. The workflow then installs
   the published TURING 1.0.0 distribution from TestPyPI beside the exact
   verified KELLOGG wheel and executes a clean smoke voyage.
10. Only after that succeeds, run the TURING workflow with `publish=pypi`.
    The production job additionally requires `kellogg-tensor==1.0.0` to be
    live on PyPI and TURING 1.0.0 to exist on TestPyPI.

## Truth boundary

A green software release proves the standalone TURING software VQC and its
declared exact/classical execution semantics. It does not prove physical QPU
execution, hardware quantum speedup, mining hashrate, cryptanalytic capability,
or pool acceptance. Those require their own evidence authorities.

Do not mark a package `published=true` until the registry upload actually
succeeds.
