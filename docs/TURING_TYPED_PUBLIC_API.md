# TURING typed public API and package organization

TURING remains one `hyba-turing-vqc` distribution and the existing
`turing_universal_quantum_computer` namespace. No separately branded pipeline
package is introduced. The exact implementations execute through their actual
admitted representations; package correctness does not depend on external
device access or substitute a different thesis about computation.

- [Architecture and implementation ownership](../turing_universal_quantum_computer/docs/architecture.md)
- [Public API](../turing_universal_quantum_computer/docs/api.md)
- [Installation and locked environment](../turing_universal_quantum_computer/docs/installation.md)
- [Reproducibility and publication evidence](../turing_universal_quantum_computer/docs/reproducibility.md)
- [Layout compatibility decision](../turing_universal_quantum_computer/docs/decisions/0001-preserve-canonical-package.md)

The facade is additive; the canonical `pipeline.VQCPipeline`, mathematical
engines, certificates and shared enterprise ownership remain authoritative.
