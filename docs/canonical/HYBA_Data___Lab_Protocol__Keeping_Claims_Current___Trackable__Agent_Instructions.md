# HYBA Data — Lab Protocol: Keeping Claims Current & Trackable (Agent Instructions)

Company: HYBA Data · Parent: HYBA Software Ltd

Purpose: standing instructions for any agent (human or AI) working on HYBA Data's technical claims. The goal is a lab discipline — nothing stated as a capability unless it was tested, and every test is dated, reproducible, and linked from the document that cites it.

## Rule 1 — No claim without an artifact

Every capability number in a data sheet, pitch deck, or briefing must link to a runnable script/test and its dated output. If a number can't currently be traced to an artifact, mark it with its actual provenance (doctrine, projection, prior seal) instead of presenting it as freshly verified.

## Rule 2 — Update documentation in the same session code changes land

When new or updated code lands (a new module, an "elevated" version of an existing one, a bug fix), the agent must, in that same working session:

1. Test the change for real.
2. Update the relevant data sheet(s) with a dated addendum reflecting what was actually verified.
3. Update the Sealed Claims Register / claim lane if the change moves a claim between lanes.

Documentation must never be allowed to describe code that no longer exists, or omit code that now does.

## Rule 3 — Keep a running Lab Log

Every test gets a dated entry recording: hypothesis, method (including any environment caveats, e.g. missing packages/shims used), the actual numbers observed, and a verdict/claim lane. Negative or inconclusive results are recorded with the same rigor as positive ones — a gap found today is tomorrow's fix, not something to omit.

## Rule 4 — Separate "visible" metrics from "real" metrics

Any time a system reports an internal ratio (e.g. a folded array's size relative to input, a per-stage compression number), the agent must also compute and report the real end-to-end number — i.e., what must actually be stored/transmitted to reconstruct the data losslessly, including side-channel data (kernels, cores, metadata). Never present a component-level ratio as if it were the whole-system claim.

## Rule 5 — Deterministic math ≠ sealed product claim

A mathematical identity (e.g. fold size scaling exactly as φ^depth) can be marked SEALED once independently reproduced from the real code, with the deviation quantified. That seal covers the identity, not automatically any downstream compression/performance claim built on top of it — those need their own, separately dated test.

## Rule 6 — Structured-vs-random claims require a structured-vs-random test

Any claim that a capability "applies to structured data" (or performs differently depending on data class) must be backed by a test that actually runs multiple data classes side by side and reports the differentiated numbers — not asserted from doctrine alone.

## Rule 7 — Re-test before re-stating

Whenever underlying operator code changes, previously stated ratios/claims that depend on it are considered stale until re-run. Re-run the relevant Lab Log test before repeating the number anywhere.

## Rule 8 — Golden-ratio / φ-power claims

Because HYBA Data's compression is explicitly deterministic and tied to φ and its powers, any claim of the form "increasing φ-power/depth increases compression" must be tested at multiple depths (not just one), with the real net ratio (Rule 4) reported at each depth — see the 23 Jul 2026 Lab Log entry for the reference methodology and a worked counter-example (net ratio currently decreases with depth under the present fold+kernel scheme).

Reference implementation of this protocol: HYBA Data — PULVINI Lab Log: Phi-Depth Determinism & Structured-Data Test (23 Jul 2026).