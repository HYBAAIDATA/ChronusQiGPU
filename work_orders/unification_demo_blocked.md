# Cross-domain demo — blocked

The requested runnable demo and three-domain network do not exist on the branch as of the preceding module check. Command and actual failure: `artifacts/unification/demo-attempt.txt`, produced in the isolated new-file workspace with `PYTHONPATH=src python -m hyba.unification.run_unification_demo`. The error is a missing module, not a completed end-to-end test. The workspace is not a complete checkout; repository tree inspection separately found no demo under `src/hyba/unification` at the inspected head.

No `demo_<sha256>.json`, hash-verification success, signature, receipt, endpoint or medical/security/storage result was generated. An internally embedded full-file SHA-256 would be self-referential; the producer must document a verifiable content-address convention, for example SHA-256 of the exact file bytes in the filename with a separate manifest, or hash a clearly specified payload excluding its digest field. Signature status must be explicitly unsigned until a verified signing implementation and key custody exist.

Next: finish the real field/network/invariant/domain integration and reproducible evidence gates on a complete checkout, then build the demo and test its exact byte-hash convention. No CI claim.
