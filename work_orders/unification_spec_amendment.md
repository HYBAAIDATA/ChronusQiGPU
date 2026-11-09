# Unification specification amendment — 2026-11-09

Status: **requested amendment recorded; two algebraic compatibility findings require correction before representing it as proved.** The PR remains experimental. This document records the work order faithfully, including a generator formula that fails the executable check below. It does not amend field code by assertion.

## Requested amendment (§1.1/§2.1)

> exact arithmetic in Q(φ), with a lossless embedding into the real subfield of Z[ζ₅] and a lossless restriction back on its domain.

The order specifies the embedding φ ↦ ζ₅ + ζ₅⁻¹, with proof obligations: injective on Q(φ); left inverse on its image; exact for every coefficient the repository stores. The generator and codomain wording are recorded as requested, not accepted as established.

## Executable finding and necessary qualification

Run `python scripts/unification/check_amendment.py /path/to/engine.py`; raw output is `artifacts/unification/amendment-generator-check.txt`, produced from the existing `src/chronus/security/al_haras/engine.py` export whose Git blob was independently checked as `c60c15ea37debab1da04be3f6352ca26d3cd9b24`. For the positive golden ratio satisfying φ²=φ+1 and the existing engine's ζ₅=exp(2πi/5), t=ζ₅+ζ₅⁻¹ satisfies t²+t=1, not t²=t+1; the existing positive φ equals 1+t=−ζ₅²−ζ₅³. Thus the requested mapping is not a homomorphism preserving φ²=φ+1. `1/2` belongs to Q(φ) but not Z[ζ₅], whose power-basis coefficients are integers. The full rational field embeds into the real subfield of **Q(ζ₅)**; its integral subring Z[φ] maps into Z[ζ₅]. The current implementation uses this distinction. Neither finite test cases nor coverage prove the universal obligations.

## Dependency graph and staged gates

Use `field → StubNetwork → StubDomain` for the field integration and E2E test classes, `network → field + StubInvariants → StubDomain` for network, then `invariants → network → StubDomain`; finally replace/add stub journeys using the real domain. A double is not the target module or a customer journey. Passing double-based tests does not establish real-module integration, and those real tests remain an additional release gate. Define Stubs in `src/hyba/unification/testing/doubles.py` and unit-test them before module work.

## Measurement and execution scope

Partial source-export coverage is provisional. Final module coverage must run against the full tree and be at least 90%; otherwise mark blocked. CI is out of scope: report commands and commit SHA, never claim CI green. If a step cannot be completed, commit an explicit blocked record with actual failing output and continue where safe. All external security, clinical and performance claims require evidence; no customer deployment is implied.
