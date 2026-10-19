# 05 — Migration Classification of Repo Stores

| Store / surface | Class | Enterprise custody role |
| :--- | :--- | :--- |
| **AddressSpace / manifold addressing** | **Canonical** | Logical address model remains source of truth for topological IDs; enterprise root stores opaque envelopes keyed by `record_id` |
| **EUCLID / geometry helpers** | **Remain** | Stay as math libraries; not folded into Theseus disk format |
| **aethel.theseus (triad software)** | **Peer / legacy software path** | Continues as production software triad store; enterprise package is the custody substrate with journal+HMAC+tenants |
| **aethel.enterprise.EnterpriseCustody** | **Enterprise custody (this package)** | Single-root measured custody |
| **Mining / PhiMiner pipelines** | **Out of scope** | Not migrated as Intelligence proof; mining remains proof ground only |
| **Mirror / evidence telemetry** | **Mirror evidence** | Counters + custody_events; `mirror_digest` for bridge envelopes |
| **Hyperscaler SKU** | **Provisional / not claimed here** | Must not inherit READY from single-root custody |
| **Geodesic / Solutions API** | **EXTERNAL** | Outside triad; do not mark READY in this tranche |
| **AL HARAS** | **Security authority (external hooks)** | Adapter only |
| **Cassini / pulvini / durable index** | **Optional anchors** | May coexist; not required for enterprise envelope v1 |

## Adapter registry

`aethel.enterprise.adapters` registers classifications and `mirror_digest` helpers for bridge CI. Wrapping a legacy store does not change its claim class.
