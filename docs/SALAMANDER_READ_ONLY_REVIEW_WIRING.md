# Salamander native repository-review wiring

## Delivered scope

The local `repository-review` skill is discovered by the existing skill loader. `SalamanderEngine.execute_skill` dispatches that exact name to a fixed trusted Python adapter. Other upstream/local skill documents remain guidance; documents cannot supply executable callables or permissions. The adapter never imports, executes or changes inspected source. It has no provider client, shell, scheduler or network tool.

This is an independently written native counterpart to the read-only pattern in the pinned [Claude scheduled reviewer](https://github.com/anthropics/claude-cookbooks/blob/39cd5a7a3a29a73e7391e17b7644c51f34a6aaa1/claude_agent_sdk/scheduled_repository_reviewer/scheduled_review.py). It is NOT that SDK workflow wired end-to-end. The external example's model reasoning, resumed sessions, SDK hooks and schedules have not been implemented or run. No upstream code was copied into this adapter.

## Typed admission and execution

- `ReviewPolicy(expected_files, max_file_bytes, max_total_bytes, max_findings)`: frozen value containing 1..64 distinct immutable `(relative_python_path, lowercase_sha256)` tuples. Exact integer limits exclude booleans; ceilings are 262144 bytes/file, 1048576 total bytes and 128 findings. Host chooses root and source hashes independently of inspected instructions. No implicit repository scan.
- `review_repository(repo_root=..., policy=...)`: read declared files through POSIX descriptor-relative no-follow traversal. Reject path traversal, symlinks in root/parents/files, hidden paths, missing/unreadable/nonregular files, mismatched content hashes, malformed input and exceeded budgets. FIFO reads are nonblocking and refused. Hosts lacking required descriptor/no-follow support refuse rather than weakening the boundary.
- Parse source bytes using Python AST without evaluating expressions or importing source modules. Evidence includes syntax errors, lexical eval/exec call candidates and repeated binding candidates. Rebinding may be valid (properties/overloads/intentional shadowing); lexical calls may be rebound. These are review findings, not proof of vulnerabilities or faulty semantics.
- Return a deterministic receipt binding policy, approved path/hash manifest and observed source hashes/findings. Receipt hashes authenticate content, not truth, institutional endorsement or approval. Refusals issue no partial receipt. Output excludes source text and absolute paths.

The host-selected root/hash manifest is an input contract, not authentication or authorization of an untrusted caller. A remote/model-facing tool must apply independent host access policy before calling this adapter. Descriptor confinement and approved byte hashes are not a current git-commit/atomic repository snapshot attestation. File/byte/finding limits are not hard memory/CPU/wall-time envelopes; isolated execution limits are required before exposing the parser to hostile inputs in a service. Root hardlinks/mount policy remains host responsibility.

## Example host composition

```python
from Intelligence.repository_review import ReviewPolicy

# Use independently approved hashes from your pinned checkout/artifact manifest.
policy = ReviewPolicy((("Intelligence/example.py", approved_sha256),))
receipt = engine.execute_skill(
    "repository-review", repo_root=approved_checkout, policy=policy
)
```

Missing/unequipped skill, missing policy and unexpected execution/callback parameters refuse. `REVIEWED_READ_ONLY` is not a test pass, successful repair, semantic/security certificate or production qualification. Zero syntactic findings is not a clean bill of health. Repairs still require the existing transaction admission, independent source validation and recovery verification; review results do not authorize any edit.

## Observed validation

37 focused cases passed locally, including actual method dispatch with actual skill discovery on a constructor-bypassed engine instance. The local harness retained actual method AST bodies, not an alternative dispatcher. Full module imports and engine constructor were deliberately excluded. 69 existing scoped repair/recovery regressions also passed after the eight-line dispatch addition. Black100, Ruff E9/F and compileall for all changed Python files; Flake8 for the new adapter/tests: exit0. Exact scope, versions, hashes, commands and exclusions are in `repository_review_local_validation.json`.

The adapter also actually reviewed three local edited Python source files and issued `reports/repository_review_local_receipt.json`: zero syntactic candidates, explicitly NOT a semantic correctness/security/production verdict. It did not inspect or certify the full remote repository.

## Branch/release controls and remaining integrations

This branch is stacked on PR #66 at d4bed8f28bd5b139d2e82e72ca6284f403d8dc68 to retain its repair/recovery safety corrections, rather than overwriting them with an older main version. The delta to Salamander is only the eight-line native dispatch case. PR #67's independent trusted graft anchors/source catalogues remain a separate dependency for broader upstream guidance admission. Resolve both in reviewed order before a combined installed-artifact qualification.

No automatic triggers, SDK/provider calls, deployment, release, merge, main push, mining or pool connection were performed. Full-engine, actual checkout/conftest, installed-artifact, CI and independent review gates remain unrun. No ASI/AGI, Millennium proof, competitor superiority or Lucas intelligence multiplier is claimed.

Next integrations: qualify this adapter in the actual installed engine; add explicit host authorization/resource isolation for any remote exposure; promote selected licensed Microsoft/Gemini/Copilot artifacts through tested tool adapters; complete the byte-preserving Claude API graft; configure and qualify any Claude SDK runtime separately. Do not represent native syntax inspection as the external model's reasoning capability, or catalogue entries as executable skills.
