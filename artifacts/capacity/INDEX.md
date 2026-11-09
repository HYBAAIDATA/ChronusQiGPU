# Reference measurement artifacts

These measurements are not product capacity claims. The specification-conformant codec and recovery module are not established. Device write amplification is unmeasured. Reproduce with the harness; results vary by environment.

| Artifact | Encoding and harness source commit | Run date (UTC) | Sample manifest SHA-256 | Class coverage |
| --- | --- | --- | --- | --- |
| [2571bd0e1f1e8d1b93056808bbd098196873b70b6c3d493340131bfdc80a356b](./2571bd0e1f1e8d1b93056808bbd098196873b70b6c3d493340131bfdc80a356b.json) | `18f3b8225e01e796b6d5433b32e95f521dde12a9` | 2026-11-09 | `f5da4332fd93255b7e29ef7fdb41ef7b7b5bd97e72608045f71959373391eae9` | synthetic-text |

| [a03e59aec7731151b49becb6a9ba85949137ec3dc043595c6dad9939b70301cb](./a03e59aec7731151b49becb6a9ba85949137ec3dc043595c6dad9939b70301cb.json) | `eea7c91559547eb4906cd70db12de9f2b1df4adb` | 2026-11-09 | `f5da4332fd93255b7e29ef7fdb41ef7b7b5bd97e72608045f71959373391eae9` | synthetic-text |

Artifact introduction commit: use `git log --diff-filter=A -- artifacts/capacity/2571bd0e1f1e8d1b93056808bbd098196873b70b6c3d493340131bfdc80a356b.json`. This avoids embedding a commit ID into its own commit. Source export provenance: local codec and harness Git blobs were independently compared against the source commit via the GitHub contents API; the export itself has no Git checkout. Hardware inputs used by this run are in `harness/reference-hardware.json`.

The later artifact includes a controlled corruption detection probe and a guest block-device observation. Neither is a measurement of successful recovery or physical media writes. The run used a partial source export; the source blob was independently checked against the source commit. Hardware inputs: `harness/probe-hardware.json`.
