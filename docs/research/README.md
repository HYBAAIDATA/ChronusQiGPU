# Preserved research sources

Files in this directory are historical research inputs, not runtime modules or
evidence that their stated capabilities work.

`golden_search.py` is the byte-identical v3 source found at the repository root
on 2026-11-14. Its SHA-256 is
`3b0b1047fd9cfc475f62e33c3ff26a9ed6ec69be089077bb377a65dc42297b77`.

The file is retained only as an API-shape oracle for route and request-field
parity tests. It must not be imported: its top-level `GaloisField(p=2, n=16)`
initialization performs an unbounded candidate/generator search in Python. Its
production, security, post-quantum, mining-efficiency, and complexity wording
is unverified and is not adopted by the `ga` package.