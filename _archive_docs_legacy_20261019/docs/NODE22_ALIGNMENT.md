# Permanent Node 22 Alignment

## The Issue

- Global Node: 20.18.0
- `package.json` pinned: `engines.node >=22`
- `src/**/*.test.ts` glob requires Node ≥22 (`node --test` glob support)
- Under Node 20, the glob doesn't expand → silent test skip
- Under Node 22, the glob expands → all tests run

## The Fix (Permanent) — Implemented

### Step 1: Install Node 22 via nvm4w (already done)

```powershell
nvm install 22.15.0
```

Node 22.15.0 is installed (`nvm list` shows `22.15.0` and `* 20.18.0`).

### Step 2: `.nvmrc` in repo root ✅

```
22.15.0
```

This pins the project to Node 22.15.0. Any contributor running `nvm use`
in the repo directory automatically switches.

### Step 3: `package.json` engines field ✅ (already present)

```json
{
  "engines": {
    "node": ">=22.0.0"
  }
}
```

### Step 4: CI configuration ✅

```yaml
# .github/workflows/ci.yml
- uses: actions/setup-node@v4
  with:
    node-version-file: '.nvmrc'
```

CI now uses the pinned version from `.nvmrc`.

### Step 5: Pre-install version check ✅

In `package.json` scripts:

```json
{
  "scripts": {
    "preinstall": "node -e \"const v=process.versions.node.split('.'); if(+v[0]<22){console.error('Node >=22 required. Run: nvm use'); process.exit(1)}\"",
    "test": "node node_modules/tsx/dist/cli.mjs --test src/**/*.test.ts"
  }
}
```

`npm ci` now refuses to install under Node <22.

### Step 6: Local switch (only when actively testing)

```powershell
cd C:\Users\USER\Downloads\PYTHIA-main\PYTHIA-main
nvm use 22.15.0
npm ci
npm test
```

Switch back when done with other sessions:

```powershell
nvm use 20.18.0
```

## Why Not Global Switch

Cline/CodeBuddy sessions run on Node 20. Switching global to 22 would break
those sessions.

**Solution:** `.nvmrc` gives per-project switching. The repo pins Node 22;
other work stays on Node 20. No global switch needed.

## Verification

```powershell
# In repo directory
nvm use
# Expected: Found '...\PYTHIA-main\PYTHIA-main\.nvmrc' with version 22.15.0
#           Now using node v22.15.0

npm ci
npm test
# Expected: all src/**/*.test.ts tests execute and pass
```

## The One-Line Summary

**Node 22.15.0 is installed. `.nvmrc` added, `engines` enforced, CI reads
`.nvmrc`, preinstall check added. Per-project switch via `nvm use`. No
global change needed. The environmental drift is fixed permanently.**
