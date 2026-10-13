# Sandbox → Repository Transfer Manifest

Recorded: 2026-08-16

The HYBA nature-first test programme was developed in an ephemeral sandbox. This
manifest records the authoritative byte size and **git blob SHA-1** of each
artifact as it existed in that sandbox, so fidelity can be re-verified at any
time without the sandbox.

Verify a checked-out file with:

```sh
git hash-object experiments/hyba_test_results_v5.json   # -> blob SHA below
wc -c            experiments/hyba_test_results_v5.json   # -> bytes below
```

Or list everything git already knows:

```sh
git ls-files -s experiments/
```

---

## Verified byte-exact

These files in the repository are identical to the sandbox originals, confirmed
by matching git blob SHA-1:

| File | Bytes | git blob SHA-1 |
|---|---|---|
| `hyba_test_results.json` | 7213 | `a7291a16ba3c363a97a920e1b4a023246509bf5a` |
| `hyba_test_results_v2.json` | 6498 | `7b25f83bdf3459094c16cd2a8f5e914b3a06a796` |
| `hyba_test_results_v3.json` | 5559 | `a341222712b25d58bf9e79e5a19ea4a8f9eca37c` |
| `hyba_test_results_v4.json` | 6700 | `9f699e68a96c4a9cc2fc6aa180aa1e82cb42d25c` |
| `hyba_test_results_v5.json` | 8233 | `0ac971657894a3926f1f27af9b09671aa95505a2` |
| `lgt_su2_phi_resonance.py` | 5465 | `5cf834194fd8702b063aee44957c75e5f43b572b` |
| `patch_v3.py` | 468 | `dc798732709749e131fe15a9d3dc7dc3cf6995fa` |
| `patch_v4.py` | 744 | `463ce0a2cfd54cb757e148ae47a85146df5d5513` |

All numerical results, therefore, are byte-exact as produced. The result JSONs
are the source of truth for every figure quoted in `TEST_RESULTS_SUMMARY.md`.

---

## Known cosmetic deviations

The five Python test suites carry small deviations from their sandbox originals,
introduced during transfer. **None affects logic, constants, control flow, or
results — the suites run and reproduce the committed JSONs.** Both deviation
classes are confined to comments and print formatting:

1. **Comment rule padding.** Section separator comments are padded with runs of
   U+2500 (light horizontal) or U+2550 (double horizontal). Some runs differ in
   length from the original.
2. **Escaped newline in print statements.** In some `print(f"...")` calls the
   newline escape was transferred as a doubled backslash, so the statement emits
   a literal `\n` token instead of a blank line. Cosmetic console output only.

| File | Sandbox bytes | Sandbox git blob SHA-1 | Repo delta |
|---|---|---|---|
| `hyba_nature_first_tests.py` | 24034 | `b71e91ca195ff680339bfa589feae1a4fda097b8` | +15 bytes (5 extra U+2500 on the `Summary` rule) |
| `hyba_nature_first_v2.py` | 20276 | `22803bc97a210abf42dfc4aa9faac4d047bf995b` | -139 bytes (48 missing U+2500, plus 5 doubled `\n`) |
| `hyba_nature_first_v3.py` | 17962 | `5f51b533d4fe64ab299e9adc9f175a93068c5e07` | -142 bytes (51 missing U+2500, plus 11 doubled `\n`) |
| `hyba_nature_first_v4.py` | 22066 | `106ec95e6a66e877efba75520d20f338f25e2304` | +12 bytes (12 doubled `\n`; rules correct) |
| `hyba_v5.py` | 34781 | `9d779c08eba59b8b903819158ec2e44fae94d67c` | +18 bytes (18 doubled escapes; rules correct) |

### Repair data

Every separator comment uses a 3-character leading run. Authoritative trailing
run lengths, by source line number in the sandbox original:

| File | Char | Line: trailing run |
|---|---|---|
| `hyba_nature_first_tests.py` | U+2500 | 33:13, 99:61, 114:26, 187:45, 251:13, 390:42, 423:35, 531:42, 551:65 |
| `hyba_nature_first_v2.py` | U+2500 | 28:57, 70:60, 85:6, 111:31, 179:18, 315:30, 356:15, 412:34, 429:64 |
| `hyba_nature_first_v3.py` | U+2500 | 62:37, 72:42, 100:34, 169:20, 211:38, 236:46, 245:36, 308:24, 330:64 |
| `hyba_nature_first_v4.py` | U+2550 | 59:37, 72:43, 99:35, 161:29, 222:39, 244:47, 253:27, 340:27, 357:15, 425:65 |
| `hyba_v5.py` | U+2500 | 25:61, 62:37, 68:47, 116:44, 146:47, 202:40, 274:63 |
| `hyba_v5.py` | U+2550 | 283:40, 296:46, 323:36, 385:22, 430:42, 452:48, 461:34, 510:34, 521:46, 557:28, 593:42, 625:38, 666:68 |

For the U+2550 rows the figure is the total run length on that line; the leading
run is 3, so the trailing run is the figure minus 3.

To restore byte-exactness, replace any doubled `\\n` with `\n` inside `print`
f-strings, pad the rules above to the recorded lengths, then confirm against the
sandbox blob SHAs in the table.

---

## Intentionally different

| File | Note |
|---|---|
| `lgt_su2_phi_resonance_original.py` | The sandbox original was 4863 bytes. An 8-line header was prepended on commit to document the isotropic-T bug, so the committed file is 5427 bytes by design. The body is unmodified, including the incorrect "traceless anti-Hermitian" comment, which is preserved deliberately. |

## Not transferred

| File | Reason |
|---|---|
| `github_payload.json` | 95879-byte base64 scratch artifact from an earlier transfer attempt; no independent value. |
| `golden_fourier.py` | Never present in the sandbox; built locally and still uncommitted. |
