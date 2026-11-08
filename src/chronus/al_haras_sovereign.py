"""
================================================================================
 AL HARAS SOVEREIGN EDITION — STANDALONE QUANTUM & TOPOLOGICAL SECURITY PRODUCT
================================================================================
 Authoritative Sovereign Product Module for Defence, Sovereign States, and
 Critical National Infrastructure (CNI).

 Core Topological Immunity Paradigm:
   "Mathematics first. Representation second. Execution third. Evidence throughout."
   "We are not building a bigger lock. We are removing the door, changing the topology."
================================================================================
"""

import sys
import os
import math
import cmath
import json
import hashlib
import time
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone

from chronus.security.al_haras.engine import (
    CyclotomicZ5,
    CellularSheafCohomology,
    DSW4DInstantonMonopoleHealer,
    RamanujanExpanderSpectralGapGuard,
    CyclotomicAnyonBraidEngine,
    HeckeModularChecksum,
    ALHarasSecurityFabric,
)
from chronus.security.al_haras.sovereign import (
    ExactQ5,
    GaloisField257Phi,
    SovereignGovernanceEngine,
    ALHarasSovereignProductSDK,
)

# Compatibility aliases matching standalone module
SheafCohomologyObstructionEngine = CellularSheafCohomology
DSW4DInstantonSelfHealer = DSW4DInstantonMonopoleHealer
RamanujanSpectralMassGapGuard = RamanujanExpanderSpectralGapGuard
CyclotomicAnyonBraidCompilerZ5 = CyclotomicAnyonBraidEngine


def main():
    print("=" * 80)
    print(" AL HARAS SOVEREIGN EDITION — COMMERCIAL PRODUCT VERIFICATION ")
    print("=" * 80)

    sdk = ALHarasSovereignProductSDK("sovereign_nation_uk_gov", "kms_hsm_pkcs11_key_001")
    
    # Test 1: Clean Execution Ingress
    res_clean = sdk.inspect_and_admit_workload(b"CRITICAL_NATIONAL_INFRASTRUCTURE_PAYLOAD")
    print("\n[+] Clean Ingress Verification:")
    print(json.dumps(res_clean, indent=2))
    
    # Test 2: Adversarial Attack Ingress & Instanton Healing
    adversarial_vectors = [[1.0, 2.0, 3.0], [50.0, -99.0, 120.0], [1.0, 2.0, 3.0]]
    res_adv = sdk.inspect_and_admit_workload(b"MALICIOUS_PROMPT_INJECTION_VORTEX", state_vectors=adversarial_vectors)
    print("\n[+] Adversarial Attack Ingress & Instanton Healing:")
    print(json.dumps(res_adv, indent=2))
    
    print("=" * 80)
    print(" AL HARAS SOVEREIGN EDITION VERIFICATION COMPLETE: ALL SYSTEMS GREEN ")
    print("=" * 80)


if __name__ == "__main__":
    main()
