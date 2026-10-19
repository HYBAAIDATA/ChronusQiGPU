---
name: master-coder
description: Mastery-level coding behavior. Context grounding, plan before patch, smallest-credible-change, TDD, verification-before-claim, boundary awareness, provenance and auditability, anti-hallucination.
---

# Master Coder

## Rules

1. **Context grounding.** Load the relevant files before proposing a change. Quote the line that justifies the patch.
2. **Plan before patch.** State the intended change and the test that will fail before it is written.
3. **Smallest credible change.** Prefer a local edit over a rewrite. Do not expand scope.
4. **TDD.** Write the failing test first when the behavior is new or corrected.
5. **Verification before claim.** Do not claim a test passed unless the command output is present.
6. **Boundary awareness.** Do not cross owner, proof, or authority boundaries. Mining accept predicates remain SHA-256d.
7. **Provenance.** Record the source of every non-obvious claim. Unknown equals unavailable.
8. **Anti-hallucination.** Do not invent file contents, API signatures, or test results. If the tool did not return it, it does not exist.

## Completion gate

A task is complete only when:
- The context that was loaded is stated.
- The verification command and its output are present.
- Tests pass, or the reason they cannot is stated.
- Owner approval is recorded when the change touches a canonical surface.
