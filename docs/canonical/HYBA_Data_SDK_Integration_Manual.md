# HYBA Data SDK Integration Manual

<aside>
📖

**HYBA Data SDK: Developer Integration Manual**  

**Version:** 1.0.0

</aside>

---

## 1. Installation

```bash
pip install hyba-data-sdk
```

## 2. Initialization

```python
from hyba_data.sdk import PhiClient, HermesConfig, SalamanderPolicy

client = PhiClient(
    api_key="your_key",
    endpoint="https://api.hyba.ae/v1/phi-space",
    hermes_acceleration=HermesConfig(backend="auto_gpu"),
    salamander_policy=SalamanderPolicy(auto_heal=True)
)
```

## 3. Folding & Unfolding (Storage)

```python
state_handle = client.storage.fold_and_store(path="geodesic://db/main", data=array)
data = client.storage.unfold_and_read(state_handle)
```

## 4. O(log N) Geodesic Search

```python
match = client.search.geodesic_query(query_tensor=query, manifold_paths=[state_handle])
```