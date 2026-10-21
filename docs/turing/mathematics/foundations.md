# Definitions, invariants and evidence classes

## Definitions and assumptions

A pure state is a normalised vector in a complex Hilbert space. A unitary transformation preserves its inner product; a measurement distribution follows the Born rule. These definitions do not by themselves establish that any implementation correctly computes every requested state.

For orthonormal basis vectors |k> and amplitudes αₖ:

```text
|psi> = sum_k alpha_k |k>     sum_k |alpha_k|^2 = 1
U_dagger U = I               p(k) = |alpha_k|^2
```

The equations state normalisation, unitarity and Born probabilities. Symbols: ψ is the state; αₖ its kth amplitude; U the admitted operator; † conjugate transpose; I identity; p(k) the probability of outcome k. The preview uses accessible text notation; a production equation renderer remains an explicit design acceptance item.

## Scope of invariants

Exact-field identities require exact comparison within their specified domain. Sampling uncertainty and numerical algorithms require their own assumptions and error analysis. A digest checks content binding, not mathematical validity. Agreement between two code paths is not independent proof when they share an implementation defect.

## Evidence taxonomy

| Category | What must be retained |
| --- | --- |
| Proved | Statement, assumptions, proof and independently checkable proof artefact |
| Analytically derived | Derivation, domain and independently known reference |
| Experimentally observed | Exact source, environment, inputs, method, raw outputs and limitations |
| Hypothesis | Explicit unverified status and a falsifiable test plan |

An inspected function or test definition is implementation evidence, not an executed result. A certificate is evidence about a particular computation, not an automatically established theorem.

## Reference case

Starting from |00>, apply H on qubit 0 and CX from 0 to 1. The Bell state has probabilities 1/2 at 00 and 11, zero elsewhere; either single-qubit Z expectation is zero. The independent reference is algebraic, not derived from the observed TURING output.

Read [research methodology](../research/overview.md) and [capability limits](../product/capabilities.md).
