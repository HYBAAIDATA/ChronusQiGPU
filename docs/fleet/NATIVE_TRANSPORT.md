# Native fleet HTTP transport (stage 1)

Build independently of the existing Chronus SIMD library:

```sh
cmake -S cpp/fleet_transport -B /tmp/chronus-fleet-native -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/chronus-fleet-native --parallel
export CHRONUS_FLEET_NATIVE_TRANSPORT=/tmp/chronus-fleet-native/libchronus_fleet_transport.so
chronus-fleet join --coordinator https://coordinator.example:8740 --token-file /secure/token --tls-ca /secure/ca.pem
```

The C++ libcurl path handles actual HTTP/TLS for existing worker heartbeat,
lease, result and client RPCs when explicitly configured. ctypes releases the
GIL during the native call. The existing FleetAuth still signs each request
and verifies the exact response bytes and nonce; TLS peer/hostname validation,
body limits, no redirects or proxy and no Python fallback are enforced.
An unavailable library or failed native request does not silently run the
Python HTTP path. One connection per request preserves the coordinator's
current connection-lifetime contract. Linux is the initial CI build target;
other platforms require build and qualification evidence.

This is a native transport component, **not** a complete native node daemon.
Python still owns heartbeat timing, lease policy, scheduling, tile execution
and result orchestration. No RDMA/NCCL/gRPC path is asserted. No measured
speedup or physical fleet capacity is claimed. The required CI job builds
the library and exercises real local HTTP/TLS against the maintained server,
including authentication, replay budget and error cases.
