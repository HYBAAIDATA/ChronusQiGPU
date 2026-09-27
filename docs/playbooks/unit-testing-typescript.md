# TypeScript frontend unit-testing playbook

## Scope

This playbook applies only to the React/Vite/TypeScript frontend under `src/`.
The repository is not a TypeScript monorepo: the root package is
`pythia-operator-frontend`, with a Python backend alongside one frontend.

Python coverage remains separate:

```bash
npm run test:py
```

That command runs `python -m pytest tests/`. Backend modules under `tests/` and
`mla1517_platform_v3.4/python/` are not covered by Vitest.

## Tooling and commands

Vitest is the TypeScript test runner. Tests must import test APIs from
`vitest`, use the repository `@/*` alias, and run in the configured `jsdom`
environment when DOM APIs are required. `firebase`, network APIs, databases,
pools, and all other third-party services are mocked; tests never contact
external systems.

```bash
npm run test:ts
npm run test:ts:cov
npm run test:ts -- --coverage --reporter=json
```

`npm test` intentionally remains the existing lint/build gate:
`npm run lint && npm run build`. Therefore the requested coverage command must
use `npm run test:ts -- ...`; `npm test -- --coverage --reporter=json` is not a
valid coverage command in this repository.

Coverage uses `@vitest/coverage-v8`. The Vitest configuration uses per-file
thresholds: every covered module must exceed 80% line coverage (configured as
81%), with 80% function, branch, and statement thresholds. Coverage reports are
written as text, JSON, and HTML. `all: false` keeps the initial baseline
focused on modules loaded by tests; as each module receives a test file, its
exports become part of the enforced set.

## Test location and naming

Place tests next to the module namespace using:

```text
{module}/__tests__/{filename}.test.ts
```

Examples:

```text
src/lib/__tests__/api.test.ts
src/lib/__tests__/metrics.test.ts
src/security/__tests__/al_haras_gateway.test.ts
```

Do not create a global test directory for module tests. Keep fixtures local to
the module unless they are genuinely shared.

## Test structure: AAA

Every test follows Arrange–Act–Assert:

1. **Arrange** inputs, mocks, and deterministic state.
2. **Act** by calling one exported function or observable behavior.
3. **Assert** the return value, thrown error, side effect, or interaction.

Use one behavioral claim per test. Use stable values, fake timers, and explicit
clock control where time is part of the contract. Never use randomness,
real-time sleeps, real pool endpoints, or machine-specific device state.

## Shared helpers

`src/test/helpers.ts` is the canonical offline helper module. It creates the
following helpers; they were added as part of this playbook and must not be
assumed to have existed previously:

- `createMockUser(overrides?)` — deterministic operator user factory.
- `setupTestDB(initial?)` — in-memory Map-backed persistence substitute with
  `get`, `set`, `reset`, and cleanup operations. It never initializes Firebase.
- `createMockResponse(body, init?)` — deterministic Fetch `Response` factory.

Extend this file only with dependency-free factories that are useful across
multiple frontend modules. Do not add Firebase, database, network, or browser
session setup to the helpers.

## Mocking boundary

Mock every external dependency:

- `fetch` and `apiFetch` for Python/control-plane APIs;
- Firebase modules and persistence calls;
- browser storage and service workers;
- timers and dates when time affects a result;
- third-party SDKs, telemetry exporters, and pool clients.

A test that reaches a real URL, Firebase project, database, Stratum endpoint,
filesystem, or third-party service is invalid. Use `vi.spyOn`, `vi.mock`, and
deterministic helper factories from `src/test/helpers.ts`.

## Required behavioral coverage

For every exported function, class, and public method in `src/lib/` and
`src/security/al_haras_gateway.ts`, add tests for:

- normal success;
- rejected input and thrown errors;
- boundary and empty values;
- dependency failure or timeout;
- truth/provenance labels where applicable;
- exact arithmetic invariants where applicable;
- observable logging/metrics without asserting unstable timestamps.

For `exact_math.ts`, assert exact `BigInt`/fraction results and failure modes;
do not replace exact values with floating-point approximations. For
`truth.ts`, assert that truth classes and sources are preserved. For
`metrics.ts`, use an isolated registry or reset state so tests do not depend on
process-global metric accumulation. For `al_haras_gateway.ts`, all external
transport and authentication boundaries must be mocked.

## Exemplar

`src/lib/__tests__/api.test.ts` is the reference implementation. It covers:

- absolute, relative, and empty URL inputs;
- successful Fetch with header propagation;
- transport rejection without fabricated success;
- shared user/database/response factories;
- no Firebase, network, or real database access.

New tests should match this level of isolation and explicitness.

## Pull-request gate

Every PR that changes TypeScript source must include:

```bash
npm run test:ts:cov
npm run test:ts -- --coverage --reporter=json
npm run lint
npm run build
npm run test:py
```

The PR description must include before/after line coverage for each affected
module and identify any newly uncovered branch. A PR is not complete merely
because Vitest exits zero: the coverage JSON, lint, build, and Python suite must
all be reviewed.

The frontend test suite proves frontend behavior only. It does not prove
OpenCL execution, Stratum connectivity, accepted shares, pool credit, or
backend correctness; those remain separate runtime and pytest/UAT gates.
