# Heartbeat filesystem policy

| Filesystem | Directory fsync | Rename | Default policy |
|---|---|---|---|
| ext4 | supported | atomic | `STRICT` |
| xfs | supported | atomic | `STRICT` |
| overlayfs | may vary | atomic | `LENIENT` |
| tmpfs | commonly no-op | atomic | `LENIENT` |
| NFS | may vary | not universally atomic | `LENIENT_WITH_WARN` |
| EFS | may vary | generally atomic | `LENIENT` |
| Docker Desktop bind mount | may vary | atomic at guest boundary | `LENIENT` |

The main control service detects the heartbeat filesystem at startup, appends a
`fs_selfcheck` audit event, and warns when `PYTHIA_DIR_FSYNC_POLICY` disagrees
with the recommended policy. `STRICT` turns an unsupported directory fsync
into a typed heartbeat-channel failure; `LENIENT` preserves liveness while
retaining the warning.
