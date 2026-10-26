# Skill integration and capability evidence — scoped delivery

## Implemented

`Intelligence/skill_graft.py` now binds each planned graft's complete path/hash table to a trusted content digest in the importer plan, separately from imported `PROVENANCE.json`. Rewriting both an imported document and its local checksum no longer forges admission. Verification also rejects malformed provenance, unsafe manifest paths and altered routing/license metadata. This is a trusted-code boundary, not protection against an attacker able to replace the verifier and its plan.

Seven anchors were reproduced from exact upstream git objects at the existing plan's pins. These are source-fidelity anchors, not declarations that all upstream instructions are safe, legally approved for every use, or executable capabilities. No upstream scripts were installed or executed. Original bundled scripts require independent sandboxing and least-privilege review before any execution adapter.

## Source inventory, not bulk activation

Six public source repositories were cloned as pinned no-checkout snapshots: Anthropic cookbooks and skills, Microsoft skills, Gemini CLI, obra/superpowers and GitHub awesome-copilot. Complete catalogue entries retain paths, git blob identities and source commits in `reports/skill_sources`; `reports/SKILL_SOURCE_LOCK.json` records catalogue hashes and root-license hashes. Catalogues include test/fixture material where upstream uses SKILL.md. Counts are source documents, not unique skills, runtime capabilities or intelligence scores.

Awesome-copilot is a community-contributed catalogue; hosting by GitHub does not establish review of every entry. Anthropic licensing is mixed: review each artifact, including source-available document skills. Cookbooks, provider SDK examples, CI workflows and SKILL.md guidance have different contracts. They cannot be made native by copying names or Markdown.

The inspected Euclid tree has twelve skill directories: six local and six recorded upstream grafts. Current provenance records were inspected; all actual repository skill bytes were not replayed. The seventh planned graft, claude-api, remains absent in the inspected repository. It was reconstructed locally from its existing pin (70 files, 1,175,805 bytes) but NOT committed: some individual files exceed this connector's safe request size. Do not truncate files, silently omit references, or mark it grafted. Use an approved patch-capable authenticated executor and then run actual installed-loader qualification.

## Vendor workflow boundaries

The supplied Claude scheduled reviewer cookbook is catalogued through its pinned source snapshot, not wired or run. It needs a Claude Agent SDK/provider runtime, bounded read-only repository access, path/symlink confinement, strict tool configuration, bounded turns/budget, resumed-cycle relisting and error handling. No provider call, schedule or automatic trigger was activated.

Antigravity documents workflow-to-Agent-Skills migration, not a universal repository containing all workflows. No universal bundle was found or claimed. Microsoft/Azure, Copilot and Gemini source inventories are not integrations with those cloud services: each promoted artifact needs license admission, schema/domain validation, dependency/tool mapping, authorization boundaries and integration tests.

## Validation and release boundary

Twelve new regression cases: original importer 6 failed/6 passed; patched combined suite 20 passed/4 explicitly deselected. One baseline failure is the new API admission case, not a pre-existing executable test interface. Existing fixture setup now supplies its independently calculated trusted anchor; assertions were not weakened. Black(100), changed-file Flake8, Ruff E9/F and compilation passed locally. See `docs/skill_anchor_local_validation.json` for scope and exclusions. Full package initialization, full engine, actual repository graft replay, semantic publication, installed artifacts and CI remain unqualified.

This feature branch is based on main 6688e83c22d36dc16dfd5516e9e7d81959c84438, independent of PR #66's repair/recovery changes. It does not incorporate or approve PR #65 or #66. PR #66 is draft/blocked, reviews are absent and current check-run access returned 403. No merge, main push, release, deployment, mining or pool connection occurred.

## Scientific capability contract

`reports/EUCLID_CAPABILITY_MANIFEST.json` and `docs/EUCLID_CAPABILITY_EVALUATION_PROTOCOL.md` distinguish tested code properties from unavailable system/model performance evidence. No competitor runs have executed; superiority, AGI/ASI status, Millennium proof and measured Lucas intelligence multiplier are not established. Hosted comparisons can match tasks/tools/budgets but cannot claim identical undisclosed provider hardware. Internal/shared profiles are research/restriction targets, not deployed enforceable profiles.

Next gates: license/security review and tested adapters for selected sources; authenticated byte-preserving graft executor; actual loader/full-engine/installed-package and CI qualification; frozen task/holdout/grader/budget and independent model comparison; independent release approval for a fixed artifact. Do not promote catalogue state to executable state without those results.
