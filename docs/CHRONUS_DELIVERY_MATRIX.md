# Chronus delivery capability matrix

The two Chronus delivery methods are product peers. The matrix records what is
currently evidenced in this repository; it is not a ranking.

| Capability | Embedded Chronus | Cloud Instance |
|---|---|---|
| Placement | Customer/container environment | HYBA Chronus instance in customer's chosen cloud |
| Selection | Explicit `embedded` | Explicit `cloud_instance` |
| Transport | In-process | `remote_opencl_v1` |
| Measured device inventory | Local Chronus probes across OpenCL/CUDA/Metal tensor surfaces | `/v1/devices` remote measured inventory |
| Tensor execution | Local `chronus-opencl`, `chronus-cuda`, or `chronus-metal` when that physical runtime is available | Not yet exposed by current remote wire protocol |
| SHA-256d | Existing local OpenCL/mining path or explicit CPU path | Existing verified `/v1/sha256d` path |
| Lucas/Pisot ladder | Existing local execution | Existing verified `/v1/ladder` path |
| Silent cross-mode fallback | None | None |
| Performance claims | Measurement evidence only | Remote measured evidence only |

The cloud protocol is deliberately not credited with capabilities it does not
advertise. Adding a verified remote tensor surface is a capability addition,
not a prerequisite for preserving the existing cloud mining/ladder service.

The native CUDA/Metal work in this branch expands the embedded tensor surface;
it does not claim that the mining SHA-256d kernel has also been ported to those
substrates. That is a separate execution surface and remains evidence-gated.
