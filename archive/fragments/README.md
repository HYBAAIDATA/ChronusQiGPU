# Source fragments held out of the shipped package

These files are kept exactly as committed. Nothing imports them and Python cannot compile them, so they are held here instead of inside the `hyba-chronus` distribution, whose checks now require every shipped module to compile.

| File | Former path | Added in | Why it is held here |
|---|---|---|---|
| trust_ledger.py | src/chronus/core/trust_ledger.py | e04dbd0 (9 Nov 2026) | Line 1 is an escaped docstring (a backslash before each quote), which Python rejects. The file also uses `dataclass`, `field`, `Dict`, `datetime` and a `Touchpoint` type that it never imports or defines. |

To restore a file, complete it so that it compiles and has tests, then move it back to its former path in the same change.
