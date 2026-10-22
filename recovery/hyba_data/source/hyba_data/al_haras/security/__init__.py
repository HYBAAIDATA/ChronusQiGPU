"""
Security Module - AI-Driven Quantum Security System.

This module provides a comprehensive AI-driven security system that integrates:
- Quantum entanglement for secure communication
- Security agents with deception capabilities
- Agent swarm coordination for defense
- PCI-based attack detection
- Quantum mathematical primitives
- Quantum error correction for resilience
- Quantum walks for anomaly detection
- Attacker tracking and exposure

The system is designed with the AI in charge, using every form of intelligence
available in the codebase to protect the system.

Key Components:
- QuantumSecurityDirector: AI orchestrator coordinating all defenses
- SecurityAgent: Autonomous defense agents with deception capabilities
- AgentSwarm: Coordinated swarm behavior for defense
- QuantumEntanglementChannel: Secure communication via quantum entanglement
- PCIDefenseMonitor: Attack detection using Predictive Computational Intelligence
- QuantumSecurityKey: Quantum key for cryptographic operations
- QuantumInterferenceDetector: Anomaly detection using quantum interference
- QuantumWalkSecurityAnalyzer: Pattern recognition using quantum walks
- SecurityStateEncoder: Encode security data with quantum error correction
- SurfaceCodeSecurityGuard: Topological protection using surface codes
- FaultTolerantSecurityOperation: Execute operations with fault tolerance
- QuantumTamperDetector: Detect tampering using quantum signatures
- QuantumRedundantStorage: Store data with quantum redundancy

Author: Phi-Grover Development Team
Version: 1.0.0
Date: 2026-04-20
"""

# Main security system
# Quantum error correction for security
from .quantum_error_correction_security import (
    EncodedSecurityState,
    FaultTolerantSecurityOperation,
    QuantumRedundantStorage,
    QuantumTamperDetector,
    SecurityStateEncoder,
    SurfaceCodeSecurityGuard,
    create_fault_tolerant_operation,
    create_redundant_storage,
    create_security_state_encoder,
    create_surface_code_guard,
    create_tamper_detector,
)

# Quantum math for security
from .quantum_math_security import (
    QuantumCryptography,
    QuantumHashFunction,
    QuantumInterferenceDetector,
    QuantumRandomNumberGenerator,
    QuantumSecurityKey,
    QuantumState,
    QuantumTeleportationProtocol,
    QuantumWalkSecurityAnalyzer,
    create_interference_detector,
    create_quantum_cryptography,
    create_quantum_security_key,
    create_quantum_walk_analyzer,
)
from .quantum_security_system import (
    AgentRole,
    AgentSwarm,
    AttackSignature,
    DeceptionTactic,
    PCIDefenseMonitor,
    QuantumEntanglementChannel,
    QuantumKey,
    QuantumSecurityDirector,
    SecurityAgent,
    SecurityEnvironment,
    SwarmConfiguration,
    SwarmState,
    create_quantum_security_system,
    create_security_agent,
)

__all__ = [
    # Main security system
    "QuantumSecurityDirector",
    "SecurityAgent",
    "AgentSwarm",
    "QuantumEntanglementChannel",
    "PCIDefenseMonitor",
    "SecurityEnvironment",
    "AttackSignature",
    "AgentRole",
    "DeceptionTactic",
    "SwarmState",
    "SwarmConfiguration",
    "QuantumKey",
    "create_quantum_security_system",
    "create_security_agent",
    # Quantum math for security
    "QuantumState",
    "QuantumSecurityKey",
    "QuantumInterferenceDetector",
    "QuantumWalkSecurityAnalyzer",
    "QuantumTeleportationProtocol",
    "QuantumHashFunction",
    "QuantumRandomNumberGenerator",
    "QuantumCryptography",
    "create_quantum_security_key",
    "create_interference_detector",
    "create_quantum_walk_analyzer",
    "create_quantum_cryptography",
    # Quantum error correction for security
    "EncodedSecurityState",
    "SecurityStateEncoder",
    "SurfaceCodeSecurityGuard",
    "FaultTolerantSecurityOperation",
    "QuantumTamperDetector",
    "QuantumRedundantStorage",
    "create_security_state_encoder",
    "create_surface_code_guard",
    "create_fault_tolerant_operation",
    "create_tamper_detector",
    "create_redundant_storage",
]

__version__ = "1.0.0"
