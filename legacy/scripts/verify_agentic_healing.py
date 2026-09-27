#!/usr/bin/env python3
"""
HYBA_Phi Agentic Workflow & Self-Healing Validator
Injects topological corruption into the manifold and verifies that
the agentic workflows detect and regenerate the data organically.

Sabotage model (GOLDEN_DENSE node):
  * integer_anchor += 1        -> anchor/Cassini-parity desync
  * sparse_topology masks XOR  -> Zeckendorf decode yields garbage
  * raw_payload overwritten    -> poisoned fast-path cache

After all three corruptions the only copy that can still verify against
the SHA-256 digest committed at ingest is the prime-exponent substrate
(GaloisPrimeSubstrate / curved_storage). A PASS therefore proves a real
prime_exponent_restore, not a cache hit.

Run from the repo root:
    python scripts/verify_agentic_healing.py
"""

import asyncio
import os
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from Intelligence.hardened_unified_substrate import (
    UnifiedSubstrate,
    ManifoldCurvature,
)


async def run_chaos_test() -> bool:
    print("=" * 70)
    print(" HYBA_Phi: Agentic Workflow & Self-Healing Chaos Test")
    print("=" * 70)

    # 1. Bootstrap the substrate (virtual SMs + prime manifold + healer)
    print("[*] Bootstrapping unified substrate and agentic dispatch...")
    substrate = UnifiedSubstrate(n_primes=25, n_sms=4)
    manifold = substrate.manifold

    try:
        # 2. Ingest a healthy payload into the golden-dense curvature
        original_payload = b"CRITICAL_CONSENSUS_TEMPLATE_DATA_BLOCK"
        print(f"\n[*] Ingesting target payload: {original_payload}")

        uid = manifold.ingest_sync(original_payload, ManifoldCurvature.GOLDEN_DENSE)
        node = manifold.tensors[uid]
        print(f"    -> Bound to anchor ID : {uid}")
        print(f"    -> integer_anchor     : {node.integer_anchor}")
        print(f"    -> digest             : {node.digest.hex()[:16]}...")

        # 3. Deliberate sabotage (the chaos injection)
        print("\n[!] INJECTING CORRUPTION (simulated hardware fault / bit flips)...")
        node.integer_anchor += 1
        node.cassini_parity = -(node.cassini_parity or 1)
        print("    -> Desynced integer_anchor / Cassini parity.")

        for offset in list(node.sparse_topology):
            node.sparse_topology[offset] ^= 0xDEADBEEF
        print("    -> Scrambled Zeckendorf sparse-topology masks.")

        node.raw_payload = b"CORRUPTED_DATA_BLOCK"
        print("    -> Overwrote raw payload bytes.")

        corrupted_read = manifold.decode_payload(node)
        print(f"    -> Post-sabotage decode: {corrupted_read!r}")
        assert corrupted_read != original_payload, "sabotage did not take"

        # 4. Trigger the agentic fetch path: digest-gated read -> self-heal
        #    -> digest re-verify. read_payload is the secure_fetch equivalent.
        print("\n[*] Triggering agentic fetch (digest-gated read_payload)...")
        start_heal = time.perf_counter()
        recovered_payload = await substrate.retrieve(uid)
        heal_ms = (time.perf_counter() - start_heal) * 1000

        heal_events = manifold.self_healing.heal_log
        prime_restore = any(
            e.get("kind") == "prime_exponent_restore" and e.get("uuid") == uid for e in heal_events
        )

        # 5. Validation and verdict
        print("\n" + "=" * 70)
        print(" HEALING VERDICT")
        print("=" * 70)

        if recovered_payload == original_payload and prime_restore:
            print(" [PASS] Agentic workflow detected the digest/Cassini fault.")
            print(" [PASS] Substrate regenerated exact payload from prime memory.")
            print(f"        Recovery time : {heal_ms:.2f} ms")
            verdict = True
        else:
            print(" [FAIL] System failed to heal.")
            print(f"        Expected      : {original_payload!r}")
            print(f"        Got           : {recovered_payload!r}")
            print(f"        prime_restore : {prime_restore}")
            verdict = False

        print("-" * 70)
        print(" heal_log:")
        for e in heal_events:
            print(f"   {e}")
        ev = manifold.execution_evidence()
        print(f" backends: stages={ev['stages']} backend={ev['backend']}")
        print("=" * 70)
        return verdict
    finally:
        substrate.shutdown()


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run_chaos_test()) else 1)
