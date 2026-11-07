"""Demonstrator utilities; cryptographic zk-STARK/FRI verification is unavailable."""

from typing import Any, Dict, List, Optional


class ZKSTARKVerifier:
    """Proof-format demonstrator; cryptographic STARK verification is unavailable."""

    def __init__(self, security_level: int = 128) -> None:
        """Initialize zk-STARK verifier.

        Args:
            security_level: Security level in bits (default: 128).
        """
        self.security_level = security_level
        self._algorithm = "unavailable"
        self._proof_system = "not-implemented"
        self._field = "not-applicable"
        self._verification_count = 0
        self._total_verification_time_ms = 0.0

    def verify_proof(
        self,
        proof: Dict[str, Any],
        public_input: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Return false because cryptographic STARK verification is not implemented.

        Args:
            proof: The zk-STARK proof to verify.
            public_input: Optional public input for the proof.

        This must not be used to establish proof validity.
        """
        self._verification_count += 1
        return False

    def _verify_fri_layer(self, layer: Dict[str, Any]) -> bool:
        """Compatibility stub; FRI layer verification is not implemented."""
        return False

    def verify_air_polynomial(
        self,
        polynomial_coefficients: List[int],
        quotient_polynomial: List[int],
        z_h_polynomial: List[int],
    ) -> bool:
        """Check the integer-coefficient identity P(x) = Q(x) * Z_H(x).

        Args:
            polynomial_coefficients: Coefficients of P(x).
            quotient_polynomial: Coefficients of quotient Q(x).
            z_h_polynomial: Coefficients of Z_H(x).

        Returns:
            True if the supplied integer coefficient arrays satisfy the identity.

        This arithmetic check is not an AIR or STARK proof verifier.
        """
        if not polynomial_coefficients or not quotient_polynomial or not z_h_polynomial:
            return False
        product = [0] * (len(quotient_polynomial) + len(z_h_polynomial) - 1)
        for quotient_index, quotient_value in enumerate(quotient_polynomial):
            for domain_index, domain_value in enumerate(z_h_polynomial):
                product[quotient_index + domain_index] += (
                    quotient_value * domain_value
                )
        while product and product[-1] == 0:
            product.pop()
        expected = list(polynomial_coefficients)
        while expected and expected[-1] == 0:
            expected.pop()
        return product == expected

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @property
    def proof_system(self) -> str:
        return self._proof_system

    @property
    def field(self) -> str:
        return self._field

    def get_stats(self) -> Dict[str, Any]:
        """Get verifier statistics."""
        avg_time = (
            self._total_verification_time_ms / self._verification_count
            if self._verification_count > 0
            else 0.0
        )
        return {
            "algorithm": self._algorithm,
            "proof_system": self._proof_system,
            "field": self._field,
            "security_level_bits": self.security_level,
            "verification_available": False,
            "verification_count": self._verification_count,
            "total_verification_time_ms": round(self._total_verification_time_ms, 3),
            "average_verification_time_ms": round(avg_time, 3),
        }