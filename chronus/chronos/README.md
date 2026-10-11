# `chronos` — deprecated compatibility facade

**BLUF:** Do not develop here. Chronos GPU maths live in **`chronus.v33`**.  
This package only re-exports that surface so older `import chronos` paths keep working.

| What | Where |
| --- | --- |
| Active Chronos engine (v3.3) | `chronus/v33/` |
| Product iGPU offering | `chronus/` (device, virtual_igpu, scale, MLA1517) |
| Archived operator drop (v2) | `legacy/chronos_gpu_v2_drop/` |
| Fuller upstream snapshot | `chronus_local_backup_20261001/src/chronos/` |

```python
# Preferred
from chronus.v33 import ChronosEngine, M32Manifold

# Still works (DeprecationWarning)
from chronos import ChronosEngine
```

See `docs/CHRONOS_DROP_INTEGRATION.md` for the integration record.
