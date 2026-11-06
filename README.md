# CHRONUS QUANTUM iGPU v36.0 — REPRESENTATION-AWARE COMPUTATIONAL SUBSTRATE

> **Chronus Quantum iGPU:** Mathematics-First, Representation-Aware Computational Infrastructure & CIaaS Service Delivery Platform.

---

## 🌟 Overview & Paradigm Shift

Chronus Quantum iGPU transitions computation from classical dense-state matrix expansions to an **exact algebraic, representation-aware ontology**. By leveraging exact quadratic fields $\mathbb{Q}(\sqrt{5})$, non-adjacent Binet-Zeckendorf representations ($c_k c_{k+1} = 0$), and Pisot-Vijayaraghavan (PV) Lucas integer collapse ($L_n = \phi^n + \psi^n \in \mathbb{Z}$), Chronus operates directly on parameterised structural representations in **$O(1)$ constant structural RAM**, bypassing classical memory and hardware scaling walls.

---

## 🏗️ Product Architecture: One Core, Three Commercial Markets

1. **Chronus Enterprise**: High-value organizational workloads in Finance, Legal Litigation, Engineering, and Healthcare.
2. **Chronus Hyperscale**: Infrastructure efficiency for cloud operators, addressing HBM/DRAM scarcity and grid power limits ($5.3T Capex opportunity).
3. **Chronus Sovereign**: National infrastructure, defence environments, NCSC 14 Security Principles, and FedRAMP compliance readiness.

---

## 🔧 Development Environment Setup

### Prerequisites

- **Python >= 3.10**
- **Git** for version control
- (Optional) **Conda** for environment management

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/hybadatadevops1/Chronusv2.git
cd Chronusv2

# 2. Create isolated virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3. Install package in editable mode
pip install -e .

# 4. Install development dependencies
pip install -r requirements-dev.txt

# 5. Configure environment variables
cp .env.example .env  # Create your local .env if needed
```

### Common Development Tasks

The project includes a `Makefile` for common development tasks:

```bash
# Run the test suite
make test

# Run tests with coverage report
make test-cover

# Run code linting
make lint

# Auto-format code
make format

# Build the package
make build

# Clean build artifacts
make clean
```

### Development Environment Structure

```
chronus-quantum-igpu/
├── src/chronus/              # Core package source
│   ├── __init__.py          # Package exports
│   ├── core.py              # Core API and computation engine
│   ├── config.py            # Production configuration
│   └── chronus_gpiu-v36.py  # Latest representation mode (v36.0)
├── tests/                   # Test suite (use pytest)
├── docs/                    # Documentation and directives
├── console/                 # Web console interface (HTML)
├── manifests/               # Deployment manifests
├── pyproject.toml           # Build system configuration
├── setup.py                 # Package setup
├── requirements.txt         # Runtime dependencies
├── requirements-dev.txt     # Development dependencies
└── Makefile                 # Common development tasks
```

---

## ⚡ Quickstart Guide

### Installation

```bash
pip install -e .
```

### Python SDK Usage

```python
from chronus.core import ChronusAPISDK

# Initialize Client
client = ChronusAPISDK(
    tenant_id="tenant_alpha_sdk",
    access_token="sec_token_v36",
    region="us-east-1"
)

# Submit Workload
job = client.submit_workload(
    payload_bytes=b"Quantum Chemistry Hamiltonian Input Payload",
    workload_type="QUANTUM_CHEMISTRY_VQE",
    representation_mode="EXACT_Q5_RATIONAL"
)

print(f"Workload Submitted: {job['workload_id']} | CCU Cost: {job['ccu_cost']}")

# Check Status & Results
status = client.get_workload_status(job['workload_id'])
print(f"Lifecycle State: {status['lifecycle_state']} | Assigned Cluster: {status['assigned_cluster']}")
```

---

## 🧪 Verification & Qualification Suite

Run the full 88-invariant qualification suite:

```bash
pytest tests/
```

---

## 🔐 Security & Compliance

- **Post-Quantum Signatures**: Ed25519 / ML-DSA enabled
- **ZK-STARK Verification**: FRI-based zero-knowledge proof verification
- **Zero-Auth Verify Endpoint**: `/verify/{hash}` with no auth required
- **NCSC 14 Security Principles**: Met for sovereign deployment
- **FedRAMP Ready**: Compliance preparation underway

---

## 📄 License & Release Status

* **License:** MIT License
* **Release Status:** `V36.0 — PACKAGED; QUALIFICATION ACTIVE`
* **Invariants Qualified:** 88 / 88 (100% Green)
* **Release Gates Qualified:** 8 / 8 (100% Green)

---

## 📂 Repository Contents

- **src/chronus/** — Core package source (v36.0)
- **tests/** — Test suite (pytest)
- **docs/** — Documentation and engineering directives
- **console/** — Web console interface (HTML)
- **manifests/** — Deployment manifests
- **pyproject.toml** — Build system configuration
- **setup.py** — Package setup
- **requirements.txt** — Runtime dependencies
- **requirements-dev.txt** — Development dependencies
- **Makefile** — Common development tasks

---

## 📬 Support

- **Repository:** [github.com/hybadatadevops1/Chronusv2](https://github.com/hybadatadevops1/Chronusv2)
- **Issue Tracker:** [GitHub Issues](https://github.com/hybadatadevops1/Chronusv2/issues)

---

*Maintained by Chronus Systems*