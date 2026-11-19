# Internal paradigm closure — proposed implementation

Source: owner-supplied closure transcript, 19 November 2026, sections 1–10 and four sentinels. This is a bounded software implementation; the production gate remains separate. The broader storage product work order remains ordered and incomplete.

| Closure | Implementation and acceptance |
|---|---|
| Units and lazy ledger | math/fold_ledger.py; companion matrix in (phi,1) coordinates; reduce at every fast-doubling operation; inverse uses existing GL2 verifier; compare sequential with composed execution. |
| Equivariance | Actual native modular add/sub/scale/equality, dedup, lookup, compensated dot; explicit same-transform check; exact eligible fraction. The metric for original inner product is inverse-transpose times inverse. Zeckendorf increment is not asserted equivariant without its precise action. |
| Positional codec | storage/positional_codec.py; exhaustive all 256 bytes, reject unused codewords, explicit provisional CHRN parameter. Four bytes per source byte plus framing; no capacity claim. |
| Tamper | Compensating edits preserve a modular sum. SHA-256 remains mandatory at the CHRN boundary, not an authentication claim. |
| Torus | research/torus_certificate.py: validate oriented edges, connected circle vertex links, boundary composition, rational and binary ranks; enumerate nontrivial logical operators excluding stabilizer spans separately for X and Z. Finite chain-complex certificate only. |
| Capacity | research/paradigm_seal.py uses existing PVScale and TIER_4. Explicit logical unit, not a physical count; positive Lucas rungs start at L1. |
| Refusals | Gauss square computed from residues for p=5 and p=7; named open obstructions; separate TURING authority for extension. |
| Memory | Git-tracked findings registry; closure checks exact reachable commit and evidence digest, still requires independent review. |
| Seal | Detached content-only digest and verification; timestamp outside digest. |
| Sentinels | tests/test_paradigm_closure.py, collected in existing main CI. |

The supplied sample implementation would not be safe to copy directly. It materialized very large unreduced Fibonacci integers; used a noncanonical torus face list with duplicate/reversed faces and failed orientation checks; tested a lower bound instead of an exact homological distance; used the wrong compensated metric; calculated a float eligibility fraction; labelled Fibonacci as Lucas; and used digest syntax and a transient dict as closure evidence. These defects are addressed in the new bounded implementation. No protected PULVINI source, TURING authority, customer surfaces or release verdicts changed.

The positional codec is not the same as an integer entropy coder followed by a variable-width fold; it does not fill the missing owner-approved parameter 1. The candidate header conventions and wire profile remain provisional. The existing root research prototypes include stale codec and benchmark claims; those paths require separate caller reconciliation before promotion. Neither actual folded-residency counters on customer workloads nor measured savings have been established by eligibility classification.

Prior findings stay open until exact-commit evidence and independent acceptance exist. This branch does not grant a production seal merely because four unit tests pass.
