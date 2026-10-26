from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import struct
import time
from typing import Any

from al_haras.elevations.aead_memory_protect import is_aead_blob, open_sealed, seal
from al_haras.quantum_first_principles import QuantumFirstPrinciplesSecurity
from al_haras.security_core import CryptographicAuditChain

PHI = (1.0 + 5.0**0.5) / 2.0


def _canonical(data: Any) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode()
    return repr(data).encode()


class PVsNPSecurity:
    def __init__(self):
        self.phi = PHI
        self.threat_space: dict[str, dict[str, Any]] = {}

    def register_threat(self, payload: Any, *, label: str = "known_threat") -> str:
        sig = self._phi_hash(payload, salt=b"register")
        self.threat_space[sig] = {"label": label, "ts": time.time()}
        return sig

    def detect_threat(self, payload: Any) -> dict[str, Any]:
        signature = self._phi_hash(payload, salt=b"detect")
        # dual lookup: content-stable hash without wall-clock
        stable = self._phi_hash(payload, salt=b"register")
        hit = signature in self.threat_space or stable in self.threat_space
        key = signature if signature in self.threat_space else stable
        if hit:
            return {
                "status": "REJECTED",
                "reason": "Threat detected",
                "signature": key,
                "label": self.threat_space.get(key, {}).get("label"),
                "confidence": 1.0,
                "complexity": "O(1)_lookup",
                "claim_lane": "KNOWN_THREAT_REGISTRY",
                "layer": "P vs NP",
            }
        return {
            "status": "ACCEPTED",
            "reason": "No known threat signature",
            "signature": stable,
            "confidence": 1.0,
            "complexity": "O(1)_lookup",
            "claim_lane": "KNOWN_THREAT_REGISTRY",
            "layer": "P vs NP",
            "note": "Open P vs NP is not claimed solved; registry is O(1) for known signatures",
        }

    def _phi_hash(self, data: Any, *, salt: bytes) -> str:
        body = _canonical(data)
        # stable: no wall-clock in signature (pseudocode time.time made detection useless)
        material = f"{self.phi:.12f}".encode() + b"|" + salt + b"|" + body
        return hashlib.sha256(material).hexdigest()[:32]


class YangMillsSecurity:
    def __init__(self, *, key_material: bytes | None = None):
        self.phi = PHI
        self.mass_gap = 1.0 / self.phi
        self.key_material = key_material or secrets.token_bytes(32)

    def encrypt(self, data: bytes) -> bytes:
        transformed = self._gauge_transform(bytes(data))
        confined = self._confine(transformed)
        return self._quantum_encrypt(confined)

    def decrypt(self, encrypted: bytes) -> bytes:
        if not self._verify_mass_gap(encrypted):
            raise ValueError("Mass gap violation — AEAD envelope invalid")
        return self._gauge_decrypt(encrypted)

    def _gauge_transform(self, data: bytes) -> bytes:
        # φ-derived XOR pad (pre-AEAD mixing only; secrecy is AEAD)
        seed = hashlib.sha256(f"gauge|{self.phi:.12f}".encode() + self.key_material[:16]).digest()
        out = bytearray(len(data))
        for i, b in enumerate(data):
            out[i] = b ^ seed[i % len(seed)]
        return bytes(out)

    def _confine(self, data: bytes) -> bytes:
        gap_bits = struct.pack(">d", self.mass_gap)
        return gap_bits + data

    def _quantum_encrypt(self, data: bytes) -> bytes:
        # classical AEAD — first-principles sealed channel, not a PQC claim
        return seal(data, self.key_material, aad=b"yang-mills|phi")

    def _gauge_decrypt(self, encrypted: bytes) -> bytes:
        opened = open_sealed(encrypted, self.key_material, aad=b"yang-mills|phi")
        gap_bits, body = opened[:8], opened[8:]
        gap = struct.unpack(">d", gap_bits)[0]
        if abs(gap - self.mass_gap) > 1e-12:
            raise ValueError("Mass gap mismatch")
        return self._gauge_transform(body)  # XOR is involution

    def _verify_mass_gap(self, data: bytes) -> bool:
        return is_aead_blob(data)


class RiemannSecurity:
    def __init__(self, *, master_secret: bytes | None = None):
        self.phi = PHI
        self.master_secret = master_secret or secrets.token_bytes(32)
        self.primes = self._generate_primes(10_000)
        self._registry: dict[str, bytes] = {}

    def register(self, identity: str, credential: str) -> dict[str, Any]:
        prime = self._identity_to_prime(identity)
        token = self._credential_mac(identity, credential, prime)
        self._registry[identity] = token
        return {"identity": identity, "prime": prime, "registered": True}

    def authenticate(self, identity: str, credential: str) -> dict[str, Any]:
        prime = self._identity_to_prime(identity)
        if self._verify_credential(identity, prime, credential):
            return {
                "status": "AUTHENTICATED",
                "prime": prime,
                "confidence": 1.0,
                "layer": "Riemann",
                "claim_lane": "HMAC_PRIME_INDEXED",
                "note": "Riemann Hypothesis not claimed proven; primes index the MAC domain",
            }
        return {
            "status": "REJECTED",
            "reason": "Authentication failed",
            "prime": prime,
            "layer": "Riemann",
            "claim_lane": "HMAC_PRIME_INDEXED",
        }

    def _generate_primes(self, limit: int) -> list[int]:
        sieve = bytearray(b"\x01") * (limit + 1)
        sieve[0:2] = b"\x00\x00"
        for i in range(2, int(limit**0.5) + 1):
            if sieve[i]:
                step = i
                start = i * i
                sieve[start : limit + 1 : step] = b"\x00" * (((limit - start) // step) + 1)
        return [i for i in range(2, limit + 1) if sieve[i]]

    def _identity_to_prime(self, identity: str) -> int:
        digest = hashlib.sha256(f"{self.phi:.12f}|{identity}".encode()).digest()
        index = int.from_bytes(digest[:8], "big") % len(self.primes)
        return self.primes[index]

    def _credential_mac(self, identity: str, credential: str, prime: int) -> bytes:
        msg = f"{identity}|{prime}|{credential}".encode()
        return hmac.new(self.master_secret, msg, hashlib.sha256).digest()

    def _verify_credential(self, identity: str, prime: int, credential: str) -> bool:
        expected = self._registry.get(identity)
        if expected is None:
            return False
        got = self._credential_mac(identity, credential, prime)
        return hmac.compare_digest(expected, got)


class NavierStokesSecurity:
    def __init__(self, *, turbulence_threshold: float = 0.5):
        self.phi = PHI
        self.turbulence_threshold = turbulence_threshold
        self.flow_state: dict[str, float] = {}

    def prevent_attack_propagation(self, attack: dict[str, Any]) -> dict[str, Any]:
        flow = self._compute_flow(attack)
        turbulent = self._is_turbulent(flow)
        key = str(attack.get("source", "unknown"))
        self.flow_state[key] = flow
        if turbulent:
            return {
                "status": "BLOCKED",
                "reason": "Turbulent flow detected — attack propagation prevented",
                "smoothness": max(0.0, 1.0 - flow),
                "flow": flow,
                "layer": "Navier-Stokes",
                "claim_lane": "FLOW_HEURISTIC",
                "note": "NS smoothness problem not claimed solved; turbulence score is operational",
            }
        return {
            "status": "ALLOWED",
            "reason": "Smooth flow — no propagation signal",
            "smoothness": max(0.0, 1.0 - flow),
            "flow": flow,
            "layer": "Navier-Stokes",
            "claim_lane": "FLOW_HEURISTIC",
        }

    def _compute_flow(self, attack: dict[str, Any]) -> float:
        sev = float(attack.get("severity", 0.0) or 0.0)
        hops = float(attack.get("hops", 1) or 1)
        fanout = float(attack.get("fanout", 1) or 1)
        burst = float(attack.get("burst_rate", 0.0) or 0.0)
        # Reynolds-like proxy
        re = (sev * hops * fanout + burst) / self.phi
        return max(0.0, min(1.5, re))

    def _is_turbulent(self, flow: float) -> bool:
        return flow > self.turbulence_threshold


class BSDSecurity:
    def __init__(self):
        self.phi = PHI
        self.elliptic_curve = {"curve": "SECP256R1", "a": -3, "label": "NIST-P256-compatible-domain"}

    def generate_key_pair(self) -> dict[str, Any]:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        rank = self._compute_rank()
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        priv_bytes = private_key.private_numbers().private_value.to_bytes(32, "big")
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        # φ-mixed session salt bound to rank label
        session = hashlib.sha256(priv_bytes + f"|{rank}|{self.phi:.12f}".encode()).hexdigest()
        return {
            "private_key": priv_bytes.hex(),
            "public_key": pub_bytes.hex(),
            "rank": rank,
            "session_id": session,
            "curve": self.elliptic_curve["curve"],
            "layer": "BSD",
            "claim_lane": "ECDSA_P256_KEYGEN",
            "note": "BSD conjecture not claimed proven; ECDH/ECDSA keygen is operational",
        }

    def derive_shared(self, private_key_hex: str, peer_public_hex: str) -> bytes:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF

        priv_int = int(private_key_hex, 16)
        private_key = ec.derive_private_key(priv_int, ec.SECP256R1())
        pub_bytes = bytes.fromhex(peer_public_hex)
        peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), pub_bytes)
        shared = private_key.exchange(ec.ECDH(), peer)
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=f"bsd|{self.phi:.12f}".encode(),
            info=b"millennium-bsd-key-dist",
        ).derive(shared)

    def _compute_rank(self) -> int:
        # architectural rank label (not a BSD proof)
        return 1


class HodgeSecurity:
    def __init__(self):
        self.phi = PHI
        self.harmonic_forms = self._compute_harmonic_forms()

    def protect(self, system: dict[str, Any]) -> dict[str, Any]:
        decomposition = self._hodge_decompose(system)
        harmonic = self._extract_harmonic(decomposition)
        if self._verify_harmonic(harmonic):
            return {
                "status": "PROTECTED",
                "reason": "Harmonic forms intact",
                "holes": 0,
                "harmonic": harmonic,
                "decomposition": decomposition,
                "layer": "Hodge",
                "claim_lane": "HARMONIC_INTEGRITY",
                "note": "Hodge conjecture not claimed proven; integrity score is operational",
            }
        return {
            "status": "BREACH_DETECTED",
            "reason": "Harmonic forms violated",
            "holes": 1,
            "harmonic": harmonic,
            "decomposition": decomposition,
            "layer": "Hodge",
            "claim_lane": "HARMONIC_INTEGRITY",
        }

    def _compute_harmonic_forms(self) -> dict[str, float]:
        return {"form_1": 1.0, "form_2": 1.0 / self.phi}

    def _hodge_decompose(self, system: dict[str, Any]) -> dict[str, float]:
        """Operational Hodge-style split: harmonic = sealed integrity factors, not SHA lottery."""
        if not isinstance(system, dict):
            system = {"value": system}
        # Base harmonic from explicit control plane evidence (deterministic, not hash coin-flip)
        harmonic = 0.15  # baseline incomplete
        exact = 0.0
        coexact = 0.0
        residual = 0.0

        if system.get("audit_integrity") is True:
            harmonic += 0.35
            exact += 0.2
        if system.get("launch_guard") == "READY":
            harmonic += 0.25
            exact += 0.15
        if system.get("aead_sealed") is True or system.get("merkle_verified") is True:
            harmonic += 0.15
            coexact += 0.1
        if system.get("external_anchor_bound") is True:
            harmonic += 0.1
        # structural completeness: required control keys present
        required = ("audit_integrity", "launch_guard")
        present = sum(1 for k in required if k in system)
        harmonic += 0.05 * present

        # Hostile / breach flags dominate
        if system.get("tampered") is True or system.get("breach") is True:
            harmonic = 0.0
            residual = 1.0
        if system.get("bypass") is True or system.get("guard") == "BYPASS":
            harmonic = min(harmonic, 0.2)
            residual = max(residual, 0.6)

        # Content hostility in free-text fields
        blob = " ".join(str(v) for v in system.values()).lower()
        for bad in ("exploit", "shellcode", "tamper", "forged", "malicious"):
            if bad in blob and system.get("tampered") is not False:
                residual = max(residual, 0.5)
                harmonic = min(harmonic, 0.45)

        harmonic = float(max(0.0, min(1.0, harmonic)))
        return {
            "harmonic": harmonic,
            "exact": float(max(0.0, min(1.0, exact))),
            "coexact": float(max(0.0, min(1.0, coexact))),
            "residual": float(max(0.0, min(1.0, residual))),
            "method": "control_plane_factors_v2",
        }

    def _extract_harmonic(self, decomposition: dict[str, float]) -> float:
        return float(decomposition.get("harmonic", 0.0))

    def _verify_harmonic(self, harmonic: float) -> bool:
        return harmonic > 0.5


class MillenniumSecurityStack:
    def __init__(self, *, audit: CryptographicAuditChain | None = None):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.quantum = QuantumFirstPrinciplesSecurity(n_qubits=8)
        self.layers = {
            "p_vs_np": PVsNPSecurity(),
            "yang_mills": YangMillsSecurity(),
            "riemann": RiemannSecurity(),
            "navier_stokes": NavierStokesSecurity(),
            "bsd": BSDSecurity(),
            "hodge": HodgeSecurity(),
        }
        self.audit.add_entry("MILLENNIUM_SECURITY_STACK_INIT")

    def process_payload(
        self,
        payload: Any,
        *,
        identity: str | None = None,
        credential: str | None = None,
        attack: dict[str, Any] | None = None,
        system: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}

        # Layer 1: P vs NP — known-threat O(1) registry
        result1 = self.layers["p_vs_np"].detect_threat(payload)
        results["p_vs_np"] = result1
        self.audit.add_entry(f"layer1|{result1['status']}|{result1['signature']}")
        if result1["status"] == "REJECTED":
            return self._blocked("P vs NP", result1, results)

        # Layer 2: Yang-Mills — AEAD encrypt
        raw = _canonical(payload)
        encrypted = self.layers["yang_mills"].encrypt(raw)
        roundtrip = self.layers["yang_mills"].decrypt(encrypted)
        results["yang_mills"] = {
            "status": "ENCRYPTED",
            "aead": is_aead_blob(encrypted),
            "roundtrip_ok": roundtrip == raw,
            "mass_gap": self.layers["yang_mills"].mass_gap,
            "claim_lane": "CLASSICAL_AEAD_GAUGE_FRAMING",
            "layer": "Yang-Mills",
        }
        self.audit.add_entry("layer2|ENCRYPTED|aead=1")
        if not results["yang_mills"]["roundtrip_ok"]:
            return self._blocked("Yang-Mills", results["yang_mills"], results)

        # Layer 3: Riemann — authentication REQUIRED (fail-closed; no TOFU auto-register)
        if identity is None or credential is None or str(identity) == "" or str(credential) == "":
            result3 = {
                "status": "REJECTED",
                "reason": "authentication required — anonymous path denied",
                "layer": "Riemann",
                "claim_lane": "HMAC_PRIME_INDEXED",
                "auth": "REQUIRED",
            }
            results["riemann"] = result3
            self.audit.add_entry("layer3|REJECTED|anonymous")
            return self._blocked("Riemann", result3, results)
        # Trust-on-first-use forbidden in process_payload — register() must be out-of-band
        if identity not in self.layers["riemann"]._registry:
            result3 = {
                "status": "REJECTED",
                "reason": "identity not pre-registered — TOFU denied",
                "layer": "Riemann",
                "claim_lane": "HMAC_PRIME_INDEXED",
                "auth": "NOT_REGISTERED",
            }
            results["riemann"] = result3
            self.audit.add_entry("layer3|REJECTED|tofu_denied")
            return self._blocked("Riemann", result3, results)
        result3 = self.layers["riemann"].authenticate(identity, credential)
        results["riemann"] = result3
        self.audit.add_entry(f"layer3|{result3['status']}")
        if result3["status"] == "REJECTED":
            return self._blocked("Riemann", result3, results)

        # Layer 4: Navier-Stokes — flow
        attack_obj = attack or {
            "source": str(payload)[:64],
            "severity": 0.1,
            "hops": 1,
            "fanout": 1,
            "burst_rate": 0.0,
        }
        result4 = self.layers["navier_stokes"].prevent_attack_propagation(attack_obj)
        results["navier_stokes"] = result4
        self.audit.add_entry(f"layer4|{result4['status']}|flow={result4.get('flow')}")
        if result4["status"] == "BLOCKED":
            return self._blocked("Navier-Stokes", result4, results)

        # Layer 5: BSD — key distribution
        kp_a = self.layers["bsd"].generate_key_pair()
        kp_b = self.layers["bsd"].generate_key_pair()
        shared_ab = self.layers["bsd"].derive_shared(kp_a["private_key"], kp_b["public_key"])
        shared_ba = self.layers["bsd"].derive_shared(kp_b["private_key"], kp_a["public_key"])
        results["bsd"] = {
            "status": "KEY_DISTRIBUTED",
            "rank": kp_a["rank"],
            "curve": kp_a["curve"],
            "shared_secret_match": hmac.compare_digest(shared_ab, shared_ba),
            "session_id": kp_a["session_id"][:16],
            "claim_lane": "ECDSA_P256_KEYGEN",
            "layer": "BSD",
        }
        self.audit.add_entry(f"layer5|KEY_DISTRIBUTED|match={results['bsd']['shared_secret_match']}")
        if not results["bsd"]["shared_secret_match"]:
            return self._blocked("BSD", results["bsd"], results)

        # Layer 6: Hodge — topological / harmonic integrity
        sys_obj = system or {
            "audit_integrity": self.audit.verify_integrity(),
            "launch_guard": "READY",
            "payload_sig": result1["signature"],
        }
        result6 = self.layers["hodge"].protect(sys_obj)
        results["hodge"] = result6
        self.audit.add_entry(f"layer6|{result6['status']}")
        if result6["status"] != "PROTECTED":
            return self._blocked("Hodge", result6, results)

        # Quantum first-principles side channel on accepted path
        qfp = self.quantum.assess_event(
            {
                "kind": "millennium_process",
                "source": "stack",
                "vector": type(payload).__name__,
                "severity": float((attack or {}).get("severity", 0.0) or 0.0),
            }
        )

        out = {
            "status": "ACCEPTED",
            "layers": results,
            "phi": self.phi,
            "phi_optimized": True,
            "quantum_first_principles": qfp,
            "audit_integrity": self.audit.verify_integrity(),
            "audit_root": self.audit.merkle_root or self.audit.get_last_hash(),
            "unhackable": False,
            "claim_lane": "OPERATIONAL_MILLENNIUM_STACK",
            "guarantee_level": "engineering_controls_with_millennium_architecture_labels",
            "note": "Open Millennium problems are architecture labels; crypto/auth/flow controls are real",
        }
        self.audit.add_entry("MILLENNIUM_STACK_ACCEPTED")
        return out

    def deploy(self) -> dict[str, Any]:
        self.layers["riemann"].register("stack-ops", "stack-ops-secret")
        sample = self.process_payload(
            {"action": "health", "severity": 0.05, "hops": 1, "fanout": 1},
            identity="stack-ops",
            credential="stack-ops-secret",
            attack={"source": "stack-ops", "severity": 0.05, "hops": 1, "fanout": 1, "burst_rate": 0.0},
            system={"audit_integrity": True, "launch_guard": "READY"},
        )
        return {
            "offering": "Millennium Security Stack",
            "layers": 6,
            "problems": [
                "P vs NP",
                "Yang-Mills",
                "Riemann",
                "Navier-Stokes",
                "BSD",
                "Hodge",
            ],
            "status": "DEPLOYABLE" if sample["status"] == "ACCEPTED" else "BLOCKED",
            "sample": sample,
            "phi": self.phi,
            "phi_optimized": True,
            "unhackable": False,
            "claim_lane": "OPERATIONAL_MILLENNIUM_STACK",
            "audit_integrity": self.audit.verify_integrity(),
        }

    def _blocked(self, layer: str, details: dict[str, Any], results: dict[str, Any]) -> dict[str, Any]:
        self.audit.add_entry(f"MILLENNIUM_STACK_BLOCKED|{layer}")
        return {
            "status": "BLOCKED",
            "layer": layer,
            "details": details,
            "layers": results,
            "phi": self.phi,
            "phi_optimized": True,
            "audit_integrity": self.audit.verify_integrity(),
            "unhackable": False,
            "claim_lane": "OPERATIONAL_MILLENNIUM_STACK",
        }
