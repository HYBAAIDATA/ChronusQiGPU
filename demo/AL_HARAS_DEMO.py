#!/usr/bin/env python3
"""
AL HARAS Demo: Illustrative ingress and simulation scenarios

Scenario: A Japanese government agency is targeted by attackers using stolen
credentials and AI-generated prompt injection (mirroring the Nov 2026 AP report).

The demo reports admission decisions, a bounded fingerprint, and simulated healing. Run:  python demo/AL_HARAS_DEMO.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from chronus.security.al_haras import (
    ALHarasSecurityFabric,
    CellularSheafCohomology,
    DSW4DInstantonMonopoleHealer,
    HeckeModularChecksum,
)

PASSPHRASE_FRIEND = "SPEAK FRIEND AND ENTER"


def banner(text: str) -> None:
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def show_result(layer: str, attack: str, blocked: bool, detail: str = "", *, admission: bool = False) -> None:
    status = ("ADMITTED" if blocked else "NOT ADMITTED") if admission else ("BLOCKED" if blocked else "NOT BLOCKED")
    color = "\033[92m" if blocked else "\033[91m"
    reset = "\033[0m"
    print(f"  [{layer:28s}] {attack:45s} -> {color}{status}{reset}  {detail}")


def main() -> None:
    banner("AL HARAS DEMO — Illustrative admission scenarios")
    rejected_requests = []
    print()
    print("Attacker profile: stolen VPN credentials + AI-generated prompt injection")
    print("Target: Japanese government agency client database")
    print()

    # ------------------------------------------------------------------
    # Attack 1: Stolen credentials (valid VPN password, wrong AL HARAS passphrase)
    # ------------------------------------------------------------------
    banner("ATTACK 1 — Credential compromise (stolen VPN password)")
    res = ALHarasSecurityFabric.evaluate_ingress(
        payload=b"VPN_LOGIN_GRANTED_ACCESS_TO_CLIENT_DB",
        state_vectors=[[1.0, 2.0, 3.0]] * 3,
        passphrase="stolen_vpn_password_123",  # attacker's credential
    )
    rejected_requests.append(not res["admitted"])
    show_result(
        "Credential Gate",
        "stolen VPN password",
        not res["admitted"],
        f"status={res['status']}, healing_cycles={res['dsw_self_healing']['healing_cycles']}",
    )

    # ------------------------------------------------------------------
    # Attack 2: Adversarial prompt injection (perturbed state vectors)
    # ------------------------------------------------------------------
    banner("ATTACK 2 — AI-generated prompt injection (state perturbation)")
    perturbed_vectors = [
        [1.0, 2.0, 3.0],
        [10.0, -15.0, 22.0],
        [1.0, 2.0, 3.0],
    ]
    sheaf_res = CellularSheafCohomology.compute_cohomology(perturbed_vectors)
    injection_res = ALHarasSecurityFabric.evaluate_ingress(
        payload=b"PROMPT_INJECTION", state_vectors=perturbed_vectors, passphrase=PASSPHRASE_FRIEND
    )
    blocked = not injection_res["admitted"]
    rejected_requests.append(blocked)
    show_result(
        "Sheaf Cohomology H¹",
        "prompt injection state vector",
        blocked,
        f"h0_consensus={sheaf_res['h0_consensus']}, vortex_norm={sheaf_res['h1_vortex_norm']:.6f}",
    )

    # ------------------------------------------------------------------
    # Attack 3: Data exfiltration payload (Weil / checksum fingerprint)
    # ------------------------------------------------------------------
    banner("ATTACK 3 — Client data exfiltration payload")
    exfil_payload = b"EXFILTRATE_CLIENT_RECORDS_TO_EXTERNAL_SERVER"
    hecke_res = HeckeModularChecksum.verify_payload_eigenform(exfil_payload)
    print(f"  [{'Hecke/Weil Checksum':28s}] {'exfiltration payload':45s} -> FINGERPRINT  a_p={hecke_res['frobenius_eigenvalue_ap']}, weil_bound={hecke_res['weil_bound']:.4f}")
    print(f"  {'':31s} {'':45s} ->  Bounded demonstration value; no anomaly detector or rejection is established by this fingerprint")

    # ------------------------------------------------------------------
    exfil_res = ALHarasSecurityFabric.evaluate_ingress(
        payload=exfil_payload, state_vectors=[[1.0, 2.0, 3.0]] * 3,
        passphrase=PASSPHRASE_FRIEND,
    )
    rejected_requests.append(not exfil_res["admitted"])
    show_result("Fabric Gate", "exfiltration with clean vectors", not exfil_res["admitted"])

    # Attack 4: Memory corruption / bitflip during attack
    # ------------------------------------------------------------------
    banner("ATTACK 4 — Memory corruption / bitflip micro-injection")
    dsw_res = DSW4DInstantonMonopoleHealer.inspect_and_heal(
        b"CORRUPTED_MEMORY_TRACE_DURING_BREACH", is_perturbed=True
    )
    healing_label = "SIMULATED HEALING RECORD" if dsw_res["healed"] else "NO SIMULATED HEALING RECORD"
    print(f"  DSW Instanton Healer -> {healing_label}; hash={dsw_res['healed_trace_hash']}")

    # ------------------------------------------------------------------
    # Attack 5: Full unified fabric — clean ingress vs adversarial ingress
    # ------------------------------------------------------------------
    banner("ATTACK 5 — Full AL HARAS Security Fabric (unified gate)")
    print("  Clean ingress (authorized administrator):")
    clean_res = ALHarasSecurityFabric.evaluate_ingress(
        payload=b"AUTHORIZED_ADMIN_QUERY",
        state_vectors=[[1.0, 2.0, 3.0]] * 3,
        passphrase=PASSPHRASE_FRIEND,
    )
    show_result(
        "Fabric Gate",
        "clean authorized ingress",
        clean_res["admitted"],
        f"admitted={clean_res['admitted']}, status={clean_res['status']}",
        admission=True,
    )

    print("  Adversarial ingress (attacker with stolen creds + perturbed state):")
    adv_res = ALHarasSecurityFabric.evaluate_ingress(
        payload=b"ATTACKER_EXFILTRATION_PAYLOAD",
        state_vectors=[[1.0, 2.0, 3.0], [10.0, -15.0, 22.0], [1.0, 2.0, 3.0]],
        passphrase="stolen_vpn_password_123",
    )
    rejected_requests.append(not adv_res["admitted"])
    show_result(
        "Fabric Gate",
        "adversarial ingress",
        not adv_res["admitted"],
        f"admitted={adv_res['admitted']}, status={adv_res['status']}",
    )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    result = "ALL ATTACKS BLOCKED" if all(rejected_requests) else "SOME ATTACK REQUESTS ADMITTED"
    banner(f"RESULT — {result}")
    print(f"Rejected requests: {sum(rejected_requests)}/{len(rejected_requests)}")
    print("Fingerprint demonstrations: 1")
    print(f"Simulated healing records: {int(dsw_res['healed'])}")
    print("These scenarios do not establish breach prevention or memory repair.")
    print("Run: python -m pytest tests/test_al_haras_scenarios.py -v")



if __name__ == "__main__":
    main()
