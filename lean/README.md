# Lean library — initial research slice

Pinned to Lean 4.15.0. Run from this directory:

```sh
bash check.sh
```

These proofs check three closed equalities and five universally quantified arithmetic laws in the concrete four-coefficient definition. They do not prove all ring axioms, the quotient representation, Zeckendorf or Binet results, the Pisot property, braid relations, implementation equivalence, security, or hardware behavior. The five universal-law proofs depend on Lean’s standard propositional extensionality axiom (`propext`); the three closed identities depend on no axioms. H1.1 remains **in progress**, not complete. No production or external-validation claim is made.
