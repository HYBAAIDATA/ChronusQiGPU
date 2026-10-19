# QuantumAPI

Exact quantum mathematics. No sampling. No hardware.

```python
from quantum_api import QuantumAPI

api = QuantumAPI()          # refuses to construct if golden identities fail
psi = api.ghz(3)
print(api.fidelity(psi, psi))

g = api.grover(3, [7])      # exact Born, P* and fidelity to |111>
q = api.qaoa(3, J, p=3, scaled=True)  # Φ×Lucas angles inside the unitaries
print(api.qft(api.basis(1, 16)).fidelity)  # inversion check

print(api.fold_zeckendorf([15, 100]).data)
print(api.fold_binet("F", 20).data)
print(api.deutsch_jozsa(3, "balanced").data)
print(api.walk(adjacency, steps=4).ok)
```

Measure returns the exact Born distribution. It does not collapse at random.
