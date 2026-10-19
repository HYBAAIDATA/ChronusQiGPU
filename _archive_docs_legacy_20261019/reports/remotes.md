# Git Remotes — Canonical State (GAP-8)

## Sole remote

```
origin  https://github.com/QUANTUMDATA2/PYTHIAPhiMiner.git  (fetch + push)
```

`origin` is the **only** configured remote and the canonical project home.
Branch `main` tracks `origin/main`.

## Intentionally NOT configured

```
gitlab.com/hyba-group1/hyba_pythia   — removed
```

Reason: the GitLab project was unreachable for both read and push
(`remote: The project you were looking for could not be found or you
don't have permission to view it`). The user directed GitHub as the
canonical repository; GitLab is not an authorized mirror. **Do not
re-add it** without explicit instruction and working credentials.

## Removed duplicates

```
old-origin  https://github.com/PHIDATA2/PYTHIA.git  — removed
```

A stale duplicate left over from a mid-task remote rename. The
`PHIDATA2/PYTHIA` name is the project's previous identity; the current
canonical name is `QUANTUMDATA2/PYTHIAPhiMiner`. Do not re-add
`old-origin` or any `PHIDATA2` remote.

## Verification

```
git remote -v
# → origin  https://github.com/QUANTUMDATA2/PYTHIAPhiMiner.git (fetch)
# → origin  https://github.com/QUANTUMDATA2/PYTHIAPhiMiner.git (push)
```
