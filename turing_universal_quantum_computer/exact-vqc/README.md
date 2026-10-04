# Exact VQC snapshot for review

Sources copied from the Turing sandbox on 4 October 2026. This is not a claim that a conjecture is proved. Reports that say `theorem_proven = False` mean that.

Checked in the sandbox before this branch:

- `node --experimental-strip-types --test src/lib/vqc/independent.test.ts src/lib/vqc/console.test.ts` — 24 passed
- `tsc --noEmit` — passed

The console file must parse. The `six` command block is closed.

What a reviewer should not treat as one object:

- a Grover amplitude on eight basis states
- an integer folded by Zeckendorf

Those are separate checks.
