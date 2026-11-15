# Postmortem: a literal `\n` reached `main` and broke the claims gate

**Status:** the defect is fixed (`14ee008c`). The process gap that let it
through is recorded here, because the fix does not close the gap.

**Date:** 2026-11-15
**Commit that introduced the defect:** `73c0313c` ("fix(claims): block
qualified posture while audit blockers remain open"), which is an ancestor of
`origin/main` (`dc920a82`).

## What happened

`src/chronus/service/api/claims.py` reached `main` with a literal
backslash-n inside a parenthesised condition instead of a line break:

```python
if (self.claims and all(c.disposition == "supported" for c in self.claims)\n
        and all(b.status == "closed" for b in self.blockers)):
```

The file does not parse. Importing `chronus.service.api.claims` raises
`SyntaxError: unexpected character after line continuation character`.

The claims gate, `scripts/ci/check_forbidden_claims.py`, imports that module
to validate the claim audit (`validate_claim_audit`). On a clean checkout of
`origin/main` the gate exits 1 for this reason. So the gate was already
wired to catch the defect; it simply never ran for the commits that reached
`main`. Every statement it makes about the repository's claim posture was
therefore unverified on those commits.

## Which CI step should have caught it

**Both of them would have, and neither ran.**

The `CI` workflow has two steps that cover `src/chronus/service`:

- "Lint active implementation": `ruff check --select F src/chronus/... src/chronus/service ...`
- "Compile active implementation": `python -m compileall -q ... src/chronus/service ...`

Measured against the file exactly as it stood on `origin/main`:

| Step | Exit | Result |
|---|---|---|
| `ruff check --select F` | 1 | 5 errors, `invalid-syntax: Expected a newline after line continuation character` |
| `compileall` | 1 | `SyntaxError: unexpected character after line continuation character` |
| `compileall` over the exact CI path list | 1 | same |

So the configuration was correct and the defect was detectable by the steps
as written. The gap is not in the lint configuration.

## Why it passed anyway

**CI never ran for the commits that reached `main`.**

Querying the workflow runs for the relevant commits returns nothing:

```
gh run list --repo HYBAAIDATA/ChronusQiGPU --commit 73c0313c  -> []
gh run list --repo HYBAAIDATA/ChronusQiGPU --commit 58b73d8d  -> []
gh run list --repo HYBAAIDATA/ChronusQiGPU --commit dc920a82  -> []
```

`73c0313c` is the commit that broke `claims.py`. It is an ancestor of
`origin/main`. It has no CI run. Neither do the commits around it.

The runs that do exist are for branch commits, and every one of them is a
failure. The workflow triggers are `push` and `pull_request`, so the
mechanism is in place; the commits reached `main` without a gated push.

This is the larger finding: **the defect was not missed by a weak check, it
was never offered to one.** A lint step that nobody ran catches nothing. The
question "which CI step should have caught it" has the answer "all of them",
and the more useful question is why `main` could be reached without CI at
all.

## What this changes

1. **A gate that never ran is not a gate.** On a clean checkout of
   `origin/main`, `scripts/ci/check_forbidden_claims.py` exits 1, because
   `validate_claim_audit` imports the module that does not parse. The gate
   was already wired to catch this; it simply was not executed for the
   commits that reached `main`. The defect was not missed by a weak check,
   it was never offered to one.

2. **A check is only evidence if it ran on the commit in question.** The
   manifest auditor exists to make this class of gap visible: it reports what
   a manifest claims about its own provenance, so "committed" and "verified"
   cannot be confused. That discipline applies to CI configuration too, and
   the same query used above is the way to check any commit a claim depends
   on.

3. **The lesson about grep versus the linter.** While fixing this, `json` in
   `tests/test_evidence.py` looked unused to a grep, and was removed. The
   linter reported `F821 Undefined name 'json'`, and the import was
   restored. A grep says "this string does not appear"; a linter knows what
   the name means. When they disagree, the linter is right.

## Follow-ups not done here

- Make `main` unreachable without a CI run on the commit. This is a
  repository settings change (required status checks, or a branch
  protection rule), not a code change, and it is an owner decision.
- Audit whether other `main` commits are similarly unverified. The same
  query used above applies to any commit on `main` that a claim or release
  decision relies on.
