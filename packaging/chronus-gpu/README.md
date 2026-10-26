# Chronus GPU package

This distribution installs the shared Chronus implementation and its canonical
TURING/Kellogg dependencies. It does not duplicate their Python modules.

`chronus-gpu tiers` prints finite technical limits and exact algebraic witnesses.
`chronus-gpu capacity --root ./capacity --tenant example --tier starter` runs a
Lucas/Pisot request through Chronus, OVID and THESEUS.

`chronus-pythia-fleet --root ./fleet --tenant pythia --tier pro --workers 4 --items 256`
executes a synthetic batch across bounded local logical workers, with authenticated
custody and measured work. It neither connects to a pool nor grants live submission.

Both executors accept `--mode independent` or `--mode host`. Host selection is
automatic; physical-device availability and fallback are recorded in receipts.
Technical tiers are configuration limits, not pricing, SLA or hash-rate promises.
See `docs/CHRONUS_GPU_PACKAGING.md` in the source release for limits and deployment.
