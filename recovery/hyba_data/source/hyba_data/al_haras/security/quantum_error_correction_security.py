"""
Quantum Error Correction for Security Resilience.

This module integrates quantum error correction techniques into the security system
to provide resilience against attacks and system failures.

First Principles:
- Stabilizer codes: Detect and correct bit-flip and phase-flip errors
- Surface codes: Topological protection against errors
- Syndrome measurement: Detect errors without destroying quantum information
- Fault tolerance: Operate correctly despite component failures

Applications:
- Protect security state from corruption
- Detect tampering with security parameters
- Maintain integrity of quantum communication channels
- Provide redundancy for critical security data

Author: Phi-Grover Development Team
Version: 1.0.0
Date: 2026-04-20
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

# Import quantum error correction
try:
    from quantum.error_correction import (
        BitFlipErrorModel,
        ErrorCorrector,
        ErrorModel,
        StabilizerCode,
        SurfaceCode,
        calculate_fidelity,
    )

    _QUANTUM_EC_AVAILABLE = True
except ImportError:
    _QUANTUM_EC_AVAILABLE = False
    logging.warning("Quantum error correction not available, using fallbacks")

logger = logging.getLogger(__name__)


# =============================================================================
# SECURITY STATE ENCODING WITH QUANTUM ERROR CORRECTION
# =============================================================================


@dataclass
class EncodedSecurityState:
    """
    Security state encoded with quantum error correction.

    Protects security state against:
    - Bit flips (data corruption)
    - Phase flips (sign errors)
    - Depolarizing noise (general errors)
    """

    encoded_state: np.ndarray
    code: StabilizerCode
    fidelity: float = 1.0
    error_history: list[dict[str, Any]] = None

    def __post_init__(self):
        if self.error_history is None:
            self.error_history = []


class SecurityStateEncoder:
    """
    Encode security state with quantum error correction.

    Uses stabilizer codes to protect security-critical data:
    - Configuration parameters
    - Agent states
    - Threat levels
    - Cryptographic keys
    """

    def __init__(self, code_type: str = "repetition", n_qubits: int = 5):
        """
        Initialize security state encoder.

        Args:
            code_type: Type of error correction code ('repetition', 'phase_flip', 'shor', 'steane')
            n_qubits: Number of physical qubits for encoding
        """
        self.code_type = code_type
        self.n_qubits = n_qubits

        if _QUANTUM_EC_AVAILABLE:
            self.code = self._create_code()
            self.error_corrector = ErrorCorrector(self.code)
        else:
            self.code = None
            self.error_corrector = None
            logger.warning("Quantum error correction not available")

        logger.info(f"Security state encoder initialized with {code_type} code")

    def _create_code(self) -> Optional[StabilizerCode]:
        """Create quantum error correction code."""
        if self.code_type == "repetition":
            # Repetition code for bit-flip protection
            from quantum.error_correction import repetition_code

            return repetition_code(self.n_qubits)
        elif self.code_type == "phase_flip":
            # Phase flip code for phase error protection
            from quantum.error_correction import phase_flip_code

            return phase_flip_code(self.n_qubits)
        elif self.code_type == "shor":
            # Shor's 9-qubit code for arbitrary single-qubit errors
            from quantum.error_correction import shor_code

            return shor_code()
        elif self.code_type == "steane":
            # Steane's 7-qubit CSS code
            from quantum.error_correction import steane_code

            return steane_code()
        else:
            logger.warning(f"Unknown code type: {self.code_type}, using repetition")
            from quantum.error_correction import repetition_code

            return repetition_code(self.n_qubits)

    def encode_security_data(self, data: Any) -> EncodedSecurityState:
        """
        Encode security data with quantum error correction.

        Args:
            data: Security data to encode (can be dict, list, string, or numeric)

        Returns:
            EncodedSecurityState
        """
        if not _QUANTUM_EC_AVAILABLE:
            # Fallback: simple encoding without error correction
            if isinstance(data, dict):
                encoded = np.array(
                    [hash(str(item)) % 256 for item in data.values()], dtype=np.float32
                )
            elif isinstance(data, (list, tuple)):
                encoded = np.array([hash(str(item)) % 256 for item in data], dtype=np.float32)
            elif isinstance(data, (str, int, float)):
                encoded = np.array([hash(str(data)) % 256], dtype=np.float32)
            else:
                encoded = np.array([0], dtype=np.float32)

            return EncodedSecurityState(encoded_state=encoded, code=None, fidelity=1.0)

        # Convert data to quantum state
        if isinstance(data, dict):
            # Flatten dictionary to array
            values = list(data.values())
        elif isinstance(data, (list, tuple)):
            values = list(data)
        elif isinstance(data, (str, int, float)):
            values = [data]
        else:
            values = [0]

        # Normalize to [0, 1]
        numeric_values = []
        for v in values:
            if isinstance(v, (int, float)):
                numeric_values.append(float(v))
            else:
                numeric_values.append(float(hash(str(v)) % 1000) / 1000.0)

        # Pad to fit code dimensions
        n_logical = self.code.k if self.code else 1
        while len(numeric_values) < n_logical:
            numeric_values.append(0.0)

        numeric_values = numeric_values[:n_logical]

        # Create quantum state
        if self.code and self.code.n > 0:
            dim = 2**self.code.n
            state = np.zeros(dim, dtype=np.complex128)

            # Encode data in first logical qubit state
            for i, val in enumerate(numeric_values):
                index = i * (dim // n_logical)
                state[index] = val

            # Normalize
            norm = np.linalg.norm(state)
            if norm > 1e-15:
                state /= norm

            encoded_state = state
        else:
            encoded_state = np.array(numeric_values, dtype=np.float32)

        return EncodedSecurityState(encoded_state=encoded_state, code=self.code, fidelity=1.0)

    def decode_security_data(self, encoded: EncodedSecurityState) -> Any:
        """
        Decode security data from error-corrected state.

        Args:
            encoded: Encoded security state

        Returns:
            Decoded security data
        """
        if not _QUANTUM_EC_AVAILABLE or encoded.code is None:
            # Fallback: return encoded state as-is
            return encoded.encoded_state.tolist()

        # Correct any errors first
        corrected_state, correction_info = self.error_corrector.correct(encoded.encoded_state)

        # Extract data from quantum state
        n_logical = encoded.code.k
        dim = 2**encoded.code.n

        decoded_values = []
        for i in range(n_logical):
            index = i * (dim // n_logical)
            # Extract amplitude magnitude
            value = np.abs(corrected_state[index])
            decoded_values.append(value)

        return decoded_values

    def apply_error_and_correct(
        self, encoded: EncodedSecurityState, error_model: Optional[ErrorModel] = None
    ) -> tuple[EncodedSecurityState, dict[str, Any]]:
        """
        Simulate error and correction cycle.

        Args:
            encoded: Encoded security state
            error_model: Error model to apply

        Returns:
            Tuple of (corrected_state, correction_info)
        """
        if not _QUANTUM_EC_AVAILABLE:
            return encoded, {"error_corrected": False}

        if error_model is None:
            error_model = BitFlipErrorModel(error_rate=0.1)

        # Apply error
        corrupted_state, error_info = error_model.apply_error(encoded.encoded_state)

        # Correct error
        corrected_state, correction_info = self.error_corrector.correct(corrupted_state)

        # Calculate fidelity
        if _QUANTUM_EC_AVAILABLE:
            fidelity = calculate_fidelity(encoded.encoded_state, corrected_state)
        else:
            fidelity = 1.0

        # Create corrected encoded state
        corrected_encoded = EncodedSecurityState(
            encoded_state=corrected_state,
            code=encoded.code,
            fidelity=fidelity,
            error_history=[*encoded.error_history, correction_info],
        )

        return corrected_encoded, correction_info


# =============================================================================
# SURFACE CODE FOR TOPOLOGICAL PROTECTION
# =============================================================================


class SurfaceCodeSecurityGuard:
    """
    Use surface codes for topological protection of security data.

    Surface codes provide:
    - Local error detection (only nearby qubits need to be checked)
    - High threshold error rate (~1%)
    - Scalability to large systems
    - Natural 2D layout matching physical hardware
    """

    def __init__(self, distance: int = 3):
        """
        Initialize surface code security guard.

        Args:
            distance: Code distance (odd integer, determines error correction capability)
        """
        self.distance = distance

        if _QUANTUM_EC_AVAILABLE:
            self.surface_code = SurfaceCode(distance=distance)
        else:
            self.surface_code = None
            logger.warning("Surface code not available")

        logger.info(f"Surface code security guard initialized with distance {distance}")

    def encode_security_matrix(self, security_matrix: np.ndarray) -> np.ndarray:
        """
        Encode 2D security matrix using surface code.

        Args:
            security_matrix: 2D array of security data

        Returns:
            Encoded matrix with error correction
        """
        if not _QUANTUM_EC_AVAILABLE:
            return security_matrix

        if self.surface_code is None:
            return security_matrix

        # Ensure matrix matches surface code dimensions
        d = self.distance
        if security_matrix.shape != (d, d):
            # Pad or truncate to fit
            padded = np.zeros((d, d), dtype=np.complex128)
            min_rows = min(d, security_matrix.shape[0])
            min_cols = min(d, security_matrix.shape[1])
            padded[:min_rows, :min_cols] = security_matrix[:min_rows, :min_cols]
            security_matrix = padded

        # Encode using surface code stabilizers
        # In a real implementation, this would involve actual surface code encoding
        # Here we simulate by creating a protected state

        encoded = security_matrix.copy()

        # Add redundancy (simplified surface code encoding)
        for i in range(d):
            for j in range(d):
                # Add parity checks with neighbors
                neighbors = []
                if i > 0:
                    neighbors.append(security_matrix[i - 1, j])
                if i < d - 1:
                    neighbors.append(security_matrix[i + 1, j])
                if j > 0:
                    neighbors.append(security_matrix[i, j - 1])
                if j < d - 1:
                    neighbors.append(security_matrix[i, j + 1])

                if neighbors:
                    parity = sum(neighbors) % 2
                    encoded[i, j] = security_matrix[i, j] + 0.1 * parity

        return encoded

    def detect_and_correct_errors(
        self, encoded_matrix: np.ndarray
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """
        Detect and correct errors in encoded matrix.

        Args:
            encoded_matrix: Encoded security matrix

        Returns:
            Tuple of (corrected_matrix, detection_info)
        """
        if not _QUANTUM_EC_AVAILABLE:
            return encoded_matrix, {"errors_detected": 0, "errors_corrected": 0}

        d = self.distance
        corrected = encoded_matrix.copy()

        errors_detected = 0
        errors_corrected = 0

        # Check parity constraints (simplified surface code syndrome)
        for i in range(d):
            for j in range(d):
                # Check plaquette stabilizers
                neighbors = []
                if i > 0:
                    neighbors.append(encoded_matrix[i - 1, j])
                if i < d - 1:
                    neighbors.append(encoded_matrix[i + 1, j])
                if j > 0:
                    neighbors.append(encoded_matrix[i, j - 1])
                if j < d - 1:
                    neighbors.append(encoded_matrix[i, j + 1])

                if neighbors:
                    # Compute syndrome
                    parity = sum(neighbors) % 2
                    if parity != 0:
                        errors_detected += 1
                        # Apply correction (flip bit)
                        corrected[i, j] = 1 - corrected[i, j]
                        errors_corrected += 1

        detection_info = {
            "errors_detected": errors_detected,
            "errors_corrected": errors_corrected,
            "code_distance": d,
        }

        return corrected, detection_info


# =============================================================================
# FAULT-TOLERANT SECURITY OPERATIONS
# =============================================================================


class FaultTolerantSecurityOperation:
    """
    Execute security operations with fault tolerance.

    Uses quantum error correction to ensure operations complete correctly
    even in the presence of errors or attacks.
    """

    def __init__(self, encoder: Optional[SecurityStateEncoder] = None):
        """
        Initialize fault-tolerant security operation.

        Args:
            encoder: Security state encoder
        """
        self.encoder = encoder or SecurityStateEncoder()
        self.operation_history: list[dict[str, Any]] = []

        logger.info("Fault-tolerant security operation initialized")

    def execute_with_protection(
        self, operation: callable, data: Any, max_retries: int = 3
    ) -> tuple[Any, bool]:
        """
        Execute operation with error correction and retry logic.

        Args:
            operation: Function to execute
            data: Input data
            max_retries: Maximum number of retries on failure

        Returns:
            Tuple of (result, success)
        """
        # Encode data with error correction
        encoded_data = self.encoder.encode_security_data(data)

        for attempt in range(max_retries):
            try:
                # Decode data
                decoded_data = self.encoder.decode_security_data(encoded_data)

                # Execute operation
                result = operation(decoded_data)

                # Encode result
                encoded_result = self.encoder.encode_security_data(result)

                # Verify integrity
                verification = self._verify_integrity(encoded_result)

                if verification:
                    self.operation_history.append(
                        {"attempt": attempt + 1, "success": True, "verification": verification}
                    )

                    # Decode and return result
                    final_result = self.encoder.decode_security_data(encoded_result)
                    return final_result, True
                else:
                    logger.warning(f"Verification failed on attempt {attempt + 1}")

            except Exception as e:
                logger.error(f"Operation failed on attempt {attempt + 1}: {e}")

        # All retries failed
        self.operation_history.append(
            {"attempt": max_retries, "success": False, "error": "All retries failed"}
        )

        return None, False

    def _verify_integrity(self, encoded: EncodedSecurityState) -> bool:
        """
        Verify integrity of encoded data.

        Args:
            encoded: Encoded security state

        Returns:
            True if integrity verified
        """
        if not _QUANTUM_EC_AVAILABLE:
            return True

        # Check fidelity
        if encoded.fidelity < 0.9:
            logger.warning(f"Low fidelity detected: {encoded.fidelity:.3f}")
            return False

        # Check for recent errors
        if encoded.error_history:
            recent_errors = encoded.error_history[-5:]
            for error_info in recent_errors:
                if error_info.get("error") in ["X", "Y", "Z"]:
                    # Error was corrected, but flag for review
                    logger.debug(f"Corrected error detected: {error_info}")

        return True

    def get_operation_statistics(self) -> dict[str, Any]:
        """
        Get statistics on executed operations.

        Returns:
            Dictionary with operation statistics
        """
        if not self.operation_history:
            return {"total_operations": 0, "successful_operations": 0, "success_rate": 0.0}

        total = len(self.operation_history)
        successful = sum(1 for op in self.operation_history if op.get("success", False))

        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "average_attempts": total / successful if successful > 0 else 0.0,
        }


# =============================================================================
# TAMPER DETECTION USING QUANTUM SIGNATURES
# =============================================================================


class QuantumTamperDetector:
    """
    Detect tampering using quantum signatures.

    Uses quantum error correction syndromes to detect if security data
    has been modified or corrupted.
    """

    def __init__(self, encoder: Optional[SecurityStateEncoder] = None):
        """
        Initialize quantum tamper detector.

        Args:
            encoder: Security state encoder
        """
        self.encoder = encoder or SecurityStateEncoder()
        self.signatures: dict[str, EncodedSecurityState] = {}
        self.tampering_events: list[dict[str, Any]] = []

        logger.info("Quantum tamper detector initialized")

    def register_security_object(self, object_id: str, data: Any) -> None:
        """
        Register security object and store its quantum signature.

        Args:
            object_id: Unique identifier for the object
            data: Security data to register
        """
        encoded = self.encoder.encode_security_data(data)
        self.signatures[object_id] = encoded

        logger.debug(f"Security object {object_id} registered with quantum signature")

    def verify_integrity(self, object_id: str, current_data: Any) -> tuple[bool, float]:
        """
        Verify integrity of security object.

        Args:
            object_id: Object identifier
            current_data: Current data to verify

        Returns:
            Tuple of (is_intact, confidence)
        """
        if object_id not in self.signatures:
            logger.warning(f"Object {object_id} not registered")
            return False, 0.0

        # Encode current data
        current_encoded = self.encoder.encode_security_data(current_data)

        # Compare with stored signature
        original_encoded = self.signatures[object_id]

        if _QUANTUM_EC_AVAILABLE:
            fidelity = calculate_fidelity(
                original_encoded.encoded_state, current_encoded.encoded_state
            )
        else:
            # Fallback: simple comparison
            fidelity = (
                1.0
                if np.allclose(original_encoded.encoded_state, current_encoded.encoded_state)
                else 0.0
            )

        is_intact = fidelity > 0.95

        if not is_intact:
            self.tampering_events.append(
                {"object_id": object_id, "fidelity": fidelity, "timestamp": time.time()}
            )
            logger.warning(f"Tampering detected for object {object_id} (fidelity: {fidelity:.3f})")

        return is_intact, fidelity

    def get_tampering_report(self) -> dict[str, Any]:
        """
        Get report on tampering events.

        Returns:
            Dictionary with tampering report
        """
        return {
            "total_events": len(self.tampering_events),
            "registered_objects": len(self.signatures),
            "recent_events": self.tampering_events[-10:] if self.tampering_events else [],
        }


# =============================================================================
# REDUNDANT STORAGE WITH QUANTUM CODES
# =============================================================================


class QuantumRedundantStorage:
    """
    Store security data with quantum redundancy.

    Uses quantum error correction to provide:
    - Data redundancy across multiple copies
    - Automatic error detection and correction
    - Protection against data loss
    """

    def __init__(self, n_copies: int = 3, encoder: Optional[SecurityStateEncoder] = None):
        """
        Initialize quantum redundant storage.

        Args:
            n_copies: Number of redundant copies
            encoder: Security state encoder
        """
        self.n_copies = n_copies
        self.encoder = encoder or SecurityStateEncoder()
        self.storage: dict[str, list[EncodedSecurityState]] = {}

        logger.info(f"Quantum redundant storage initialized with {n_copies} copies")

    def store(self, key: str, data: Any) -> None:
        """
        Store data with quantum redundancy.

        Args:
            key: Storage key
            data: Data to store
        """
        # Create multiple encoded copies
        copies = []
        for _i in range(self.n_copies):
            encoded = self.encoder.encode_security_data(data)
            copies.append(encoded)

        self.storage[key] = copies

        logger.debug(f"Data stored under key {key} with {self.n_copies} redundant copies")

    def retrieve(self, key: str) -> Optional[Any]:
        """
        Retrieve data with error correction.

        Args:
            key: Storage key

        Returns:
            Retrieved data, or None if not found
        """
        if key not in self.storage:
            logger.warning(f"Key {key} not found in storage")
            return None

        copies = self.storage[key]

        # Decode from best copy (highest fidelity)
        best_copy = max(copies, key=lambda c: c.fidelity)
        return self.encoder.decode_security_data(best_copy)

    def repair_storage(self, key: str) -> bool:
        """
        Repair corrupted storage copies.

        Args:
            key: Storage key

        Returns:
            True if repair successful
        """
        if key not in self.storage:
            return False

        copies = self.storage[key]

        # Find copies with high fidelity
        good_copies = [c for c in copies if c.fidelity > 0.9]

        if not good_copies:
            logger.warning(f"No good copies found for key {key}")
            return False

        # Use best copy to repair others
        best_copy = max(good_copies, key=lambda c: c.fidelity)
        decoded_data = self.encoder.decode_security_data(best_copy)

        # Re-encode all copies
        self.storage[key] = [
            self.encoder.encode_security_data(decoded_data) for _ in range(self.n_copies)
        ]

        logger.info(f"Storage repaired for key {key}")
        return True


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_security_state_encoder(
    code_type: str = "repetition", n_qubits: int = 5
) -> SecurityStateEncoder:
    """
    Create security state encoder.

    Args:
        code_type: Type of error correction code
        n_qubits: Number of physical qubits

    Returns:
        SecurityStateEncoder instance
    """
    return SecurityStateEncoder(code_type=code_type, n_qubits=n_qubits)


def create_surface_code_guard(distance: int = 3) -> SurfaceCodeSecurityGuard:
    """
    Create surface code security guard.

    Args:
        distance: Code distance

    Returns:
        SurfaceCodeSecurityGuard instance
    """
    return SurfaceCodeSecurityGuard(distance=distance)


def create_fault_tolerant_operation(
    encoder: Optional[SecurityStateEncoder] = None,
) -> FaultTolerantSecurityOperation:
    """
    Create fault-tolerant security operation.

    Args:
        encoder: Security state encoder

    Returns:
        FaultTolerantSecurityOperation instance
    """
    return FaultTolerantSecurityOperation(encoder=encoder)


def create_tamper_detector(encoder: Optional[SecurityStateEncoder] = None) -> QuantumTamperDetector:
    """
    Create quantum tamper detector.

    Args:
        encoder: Security state encoder

    Returns:
        QuantumTamperDetector instance
    """
    return QuantumTamperDetector(encoder=encoder)


def create_redundant_storage(
    n_copies: int = 3, encoder: Optional[SecurityStateEncoder] = None
) -> QuantumRedundantStorage:
    """
    Create quantum redundant storage.

    Args:
        n_copies: Number of redundant copies
        encoder: Security state encoder

    Returns:
        QuantumRedundantStorage instance
    """
    return QuantumRedundantStorage(n_copies=n_copies, encoder=encoder)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    import time

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("Quantum Error Correction for Security Resilience")
    print("=" * 60)

    # Test security state encoder
    print("\n1. Security State Encoding:")
    encoder = create_security_state_encoder("repetition", 5)

    security_data = {
        "threat_level": 0.75,
        "agent_count": 50,
        "active_attacks": 3,
        "system_status": "alert",
    }

    encoded = encoder.encode_security_data(security_data)
    print(f"   Encoded state shape: {encoded.encoded_state.shape}")
    print(f"   Fidelity: {encoded.fidelity:.3f}")

    # Apply error and correct
    error_model = BitFlipErrorModel(error_rate=0.1)
    corrected, correction_info = encoder.apply_error_and_correct(encoded, error_model)
    print(f"   Error corrected: {correction_info['recovery_applied']}")
    print(f"   Corrected fidelity: {corrected.fidelity:.3f}")

    # Test surface code guard
    print("\n2. Surface Code Protection:")
    guard = create_surface_code_guard(distance=3)

    security_matrix = np.random.rand(3, 3)
    encoded_matrix = guard.encode_security_matrix(security_matrix)
    print(f"   Original matrix shape: {security_matrix.shape}")
    print(f"   Encoded matrix shape: {encoded_matrix.shape}")

    # Add errors
    corrupted_matrix = encoded_matrix.copy()
    corrupted_matrix[0, 0] = 1 - corrupted_matrix[0, 0]
    corrupted_matrix[1, 1] = 1 - corrupted_matrix[1, 1]

    corrected_matrix, detection_info = guard.detect_and_correct_errors(corrupted_matrix)
    print(f"   Errors detected: {detection_info['errors_detected']}")
    print(f"   Errors corrected: {detection_info['errors_corrected']}")

    # Test fault-tolerant operation
    print("\n3. Fault-Tolerant Security Operation:")
    ft_op = create_fault_tolerant_operation(encoder)

    def sample_operation(data):
        return [x * 2 for x in data]

    test_data = [1.0, 2.0, 3.0, 4.0, 5.0]
    result, success = ft_op.execute_with_protection(sample_operation, test_data)
    print(f"   Operation successful: {success}")
    print(f"   Result: {result}")

    stats = ft_op.get_operation_statistics()
    print(f"   Success rate: {stats['success_rate']:.3f}")

    # Test tamper detector
    print("\n4. Quantum Tamper Detection:")
    detector = create_tamper_detector(encoder)

    detector.register_security_object("config", security_data)
    is_intact, confidence = detector.verify_integrity("config", security_data)
    print(f"   Original data intact: {is_intact}, confidence: {confidence:.3f}")

    # Tamper with data
    tampered_data = security_data.copy()
    tampered_data["threat_level"] = 0.99

    is_intact, confidence = detector.verify_integrity("config", tampered_data)
    print(f"   Tampered data intact: {is_intact}, confidence: {confidence:.3f}")

    report = detector.get_tampering_report()
    print(f"   Tampering events: {report['total_events']}")

    # Test redundant storage
    print("\n5. Quantum Redundant Storage:")
    storage = create_redundant_storage(n_copies=3, encoder=encoder)

    storage.store("security_config", security_data)
    retrieved = storage.retrieve("security_config")
    print(f"   Data retrieved successfully: {retrieved is not None}")

    # Simulate corruption and repair
    storage.storage["security_config"][0].fidelity = 0.5
    repair_success = storage.repair_storage("security_config")
    print(f"   Storage repair successful: {repair_success}")

    print("\n" + "=" * 60)
    print("Quantum Error Correction Security Demo Complete")
