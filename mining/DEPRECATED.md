# DEPRECATED: Classical Mining Path Quarantined

**Notice:** The classical mining library formerly located in this directory has been **quarantined** to:
[`legacy_mining_classical_quarantined_814002a7/`](../legacy_mining_classical_quarantined_814002a7/)

### Mandatory Direction: Use Kellogg Route
In accordance with [`OWNER_DECLARATIONS.md`](../OWNER_DECLARATIONS.md) and [`UNIVERSAL_PRINCIPLE_MAP.md`](../UNIVERSAL_PRINCIPLE_MAP.md):
- **Canonical Tensor State:** Use [`kellogg/`](../kellogg/) and [`tensor/`](../tensor/).
- **Canonical Mining Coordinator & Execution Plane:** Use [`chronus/mla1517/mining/`](../chronus/mla1517/mining/) and [`chronus/mla1517_platform/python/`](../chronus/mla1517_platform/python/).
- **Canonical Search Ordering:** Use Hendrix coprime bijection ($gcd(s, W) = 1$) via `chronus.mla1517.mining.hendrix_order` and 32-face frame via `kellogg.traversal`.

Direct imports of `mining` fail closed with:
```
ImportError: Classical mining path quarantined: use Kellogg route
```
