# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: amplitude
"""
HYBA Analytics - Unified Data Model
===================================

This module defines the canonical unified data model for HYBA with:
- Canonical entity schema
- Canonical insight schema
- Canonical prediction schema
- Canonical metric schema
- Schema evolution rules
- Schema validation
- Schema versioning

The unified data model enables HYBA to be interoperable across all 19+ domains.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import threading
from collections import defaultdict

from core_engine.unified_platform_engine import ConfigurationManager, EnterpriseLogger, Substrate


class SchemaVersion:
    """Schema version identifier"""

    def __init__(self, major: int, minor: int, patch: int):
        self.major = major
        self.minor = minor
        self.patch = patch

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __eq__(self, other) -> bool:
        if not isinstance(other, SchemaVersion):
            return False
        return self.major == other.major and self.minor == other.minor and self.patch == other.patch

    def __lt__(self, other) -> bool:
        if not isinstance(other, SchemaVersion):
            return False
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        return self.patch < other.patch

    @classmethod
    def from_string(cls, version_str: str) -> "SchemaVersion":
        """Parse version string"""
        parts = version_str.split(".")
        return cls(int(parts[0]), int(parts[1]), int(parts[2]))


class SchemaValidationResult:
    """Result of schema validation"""

    def __init__(self, is_valid: bool, errors: List[str] = None, warnings: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []

    def add_error(self, error: str):
        """Add validation error"""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str):
        """Add validation warning"""
        self.warnings.append(warning)


class SchemaEvolutionRule:
    """Rule for schema evolution"""

    def __init__(
        self,
        from_version: SchemaVersion,
        to_version: SchemaVersion,
        transformation: callable,
        description: str = "",
    ):
        self.from_version = from_version
        self.to_version = to_version
        self.transformation = transformation
        self.description = description


class CanonicalEntitySchema:
    """
    Canonical entity schema.

    Defines the standard structure for all entities across domains.
    """

    CURRENT_VERSION = SchemaVersion(1, 0, 0)

    @staticmethod
    def validate(data: Dict[str, Any]) -> SchemaValidationResult:
        """Validate entity data against canonical schema"""
        result = SchemaValidationResult(True)

        # Required fields
        required_fields = ["entity_id", "entity_type", "domain", "created_at"]
        for field_name in required_fields:
            if field_name not in data:
                result.add_error(f"Missing required field: {field_name}")

        # Field types
        if "entity_id" in data and not isinstance(data["entity_id"], str):
            result.add_error("entity_id must be a string")

        if "entity_type" in data and not isinstance(data["entity_type"], str):
            result.add_error("entity_type must be a string")

        if "domain" in data and not isinstance(data["domain"], str):
            result.add_error("domain must be a string")

        # Substrate field
        if "substrate" in data:
            valid_substrates = [s.value for s in Substrate]
            if data["substrate"] not in valid_substrates:
                result.add_error(f"substrate must be one of {valid_substrates}")

        return result

    @staticmethod
    def create(
        entity_id: str,
        entity_type: str,
        domain: str,
        attributes: Dict[str, Any],
        substrate: Substrate = Substrate.CLASSICAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a canonical entity"""
        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "domain": domain,
            "attributes": attributes,
            "substrate": substrate.value,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "schema_version": str(CanonicalEntitySchema.CURRENT_VERSION),
        }


class CanonicalInsightSchema:
    """
    Canonical insight schema.

    Defines the standard structure for all insights across domains.
    """

    CURRENT_VERSION = SchemaVersion(1, 0, 0)

    @staticmethod
    def validate(data: Dict[str, Any]) -> SchemaValidationResult:
        """Validate insight data against canonical schema"""
        result = SchemaValidationResult(True)

        # Required fields
        required_fields = ["insight_id", "insight_type", "domain", "created_at"]
        for field_name in required_fields:
            if field_name not in data:
                result.add_error(f"Missing required field: {field_name}")

        # Field types
        if "insight_id" in data and not isinstance(data["insight_id"], str):
            result.add_error("insight_id must be a string")

        if "confidence" in data and not isinstance(data["confidence"], (int, float)):
            result.add_error("confidence must be a number")

        if "confidence" in data and not (0.0 <= data["confidence"] <= 1.0):
            result.add_error("confidence must be between 0.0 and 1.0")

        # Substrate field
        if "substrate" in data:
            valid_substrates = [s.value for s in Substrate]
            if data["substrate"] not in valid_substrates:
                result.add_error(f"substrate must be one of {valid_substrates}")

        return result

    @staticmethod
    def create(
        insight_id: str,
        insight_type: str,
        domain: str,
        content: Dict[str, Any],
        confidence: float = 0.95,
        substrate: Substrate = Substrate.AGI,
        source_entities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a canonical insight"""
        return {
            "insight_id": insight_id,
            "insight_type": insight_type,
            "domain": domain,
            "content": content,
            "confidence": confidence,
            "substrate": substrate.value,
            "source_entities": source_entities or [],
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "schema_version": str(CanonicalInsightSchema.CURRENT_VERSION),
        }


class CanonicalPredictionSchema:
    """
    Canonical prediction schema.

    Defines the standard structure for all predictions across domains.
    """

    CURRENT_VERSION = SchemaVersion(1, 0, 0)

    @staticmethod
    def validate(data: Dict[str, Any]) -> SchemaValidationResult:
        """Validate prediction data against canonical schema"""
        result = SchemaValidationResult(True)

        # Required fields
        required_fields = ["prediction_id", "prediction_type", "domain", "created_at"]
        for field_name in required_fields:
            if field_name not in data:
                result.add_error(f"Missing required field: {field_name}")

        # Field types
        if "prediction_id" in data and not isinstance(data["prediction_id"], str):
            result.add_error("prediction_id must be a string")

        if "confidence" in data and not isinstance(data["confidence"], (int, float)):
            result.add_error("confidence must be a number")

        if "confidence" in data and not (0.0 <= data["confidence"] <= 1.0):
            result.add_error("confidence must be between 0.0 and 1.0")

        # Prediction horizon
        if "prediction_horizon" in data:
            if not isinstance(data["prediction_horizon"], dict):
                result.add_error("prediction_horizon must be a dictionary")
            else:
                required_horizon_fields = ["unit", "value"]
                for field_name in required_horizon_fields:
                    if field_name not in data["prediction_horizon"]:
                        result.add_error(
                            f"Missing required field in prediction_horizon: {field_name}"
                        )

        # Substrate field
        if "substrate" in data:
            valid_substrates = [s.value for s in Substrate]
            if data["substrate"] not in valid_substrates:
                result.add_error(f"substrate must be one of {valid_substrates}")

        return result

    @staticmethod
    def create(
        prediction_id: str,
        prediction_type: str,
        domain: str,
        prediction: Dict[str, Any],
        confidence: float = 0.95,
        substrate: Substrate = Substrate.AGI,
        prediction_horizon: Optional[Dict[str, Any]] = None,
        target_entities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a canonical prediction"""
        return {
            "prediction_id": prediction_id,
            "prediction_type": prediction_type,
            "domain": domain,
            "prediction": prediction,
            "confidence": confidence,
            "substrate": substrate.value,
            "prediction_horizon": prediction_horizon or {"unit": "days", "value": 30},
            "target_entities": target_entities or [],
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "schema_version": str(CanonicalPredictionSchema.CURRENT_VERSION),
        }


class CanonicalMetricSchema:
    """
    Canonical metric schema.

    Defines the standard structure for all metrics across domains.
    """

    CURRENT_VERSION = SchemaVersion(1, 0, 0)

    @staticmethod
    def validate(data: Dict[str, Any]) -> SchemaValidationResult:
        """Validate metric data against canonical schema"""
        result = SchemaValidationResult(True)

        # Required fields
        required_fields = ["metric_id", "metric_name", "domain", "value", "timestamp"]
        for field_name in required_fields:
            if field_name not in data:
                result.add_error(f"Missing required field: {field_name}")

        # Field types
        if "metric_id" in data and not isinstance(data["metric_id"], str):
            result.add_error("metric_id must be a string")

        if "value" in data and not isinstance(data["value"], (int, float)):
            result.add_error("value must be a number")

        # Unit field
        if "unit" in data and not isinstance(data["unit"], str):
            result.add_error("unit must be a string")

        # Substrate field
        if "substrate" in data:
            valid_substrates = [s.value for s in Substrate]
            if data["substrate"] not in valid_substrates:
                result.add_error(f"substrate must be one of {valid_substrates}")

        return result

    @staticmethod
    def create(
        metric_id: str,
        metric_name: str,
        domain: str,
        value: float,
        unit: str = "count",
        substrate: Substrate = Substrate.CLASSICAL,
        dimensions: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a canonical metric"""
        return {
            "metric_id": metric_id,
            "metric_name": metric_name,
            "domain": domain,
            "value": value,
            "unit": unit,
            "substrate": substrate.value,
            "dimensions": dimensions or {},
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
            "schema_version": str(CanonicalMetricSchema.CURRENT_VERSION),
        }


class UnifiedDataModel:
    """
    Unified Data Model manager.

    Provides:
    - Schema validation
    - Schema evolution
    - Schema versioning
    - Cross-domain interoperability
    """

    def __init__(self, config: ConfigurationManager, logger: EnterpriseLogger):
        self.config = config
        self.logger = logger

        # Schema registries
        self._entity_schemas: Dict[str, SchemaVersion] = {}
        self._insight_schemas: Dict[str, SchemaVersion] = {}
        self._prediction_schemas: Dict[str, SchemaVersion] = {}
        self._metric_schemas: Dict[str, SchemaVersion] = {}

        # Evolution rules
        self._evolution_rules: Dict[str, List[SchemaEvolutionRule]] = defaultdict(list)

        self._lock = threading.Lock()

        # Initialize with canonical schemas
        self._initialize_canonical_schemas()

        self.logger.set_context(component="UnifiedDataModel")
        self.logger.info("Unified Data Model initialized")

    def _initialize_canonical_schemas(self):
        """Initialize with canonical schemas"""
        # Register canonical schemas
        self._entity_schemas["canonical"] = CanonicalEntitySchema.CURRENT_VERSION
        self._insight_schemas["canonical"] = CanonicalInsightSchema.CURRENT_VERSION
        self._prediction_schemas["canonical"] = CanonicalPredictionSchema.CURRENT_VERSION
        self._metric_schemas["canonical"] = CanonicalMetricSchema.CURRENT_VERSION

    def validate_entity(
        self, data: Dict[str, Any], schema_name: str = "canonical"
    ) -> SchemaValidationResult:
        """Validate entity data"""
        return CanonicalEntitySchema.validate(data)

    def validate_insight(
        self, data: Dict[str, Any], schema_name: str = "canonical"
    ) -> SchemaValidationResult:
        """Validate insight data"""
        return CanonicalInsightSchema.validate(data)

    def validate_prediction(
        self, data: Dict[str, Any], schema_name: str = "canonical"
    ) -> SchemaValidationResult:
        """Validate prediction data"""
        return CanonicalPredictionSchema.validate(data)

    def validate_metric(
        self, data: Dict[str, Any], schema_name: str = "canonical"
    ) -> SchemaValidationResult:
        """Validate metric data"""
        return CanonicalMetricSchema.validate(data)

    def register_schema_version(self, schema_type: str, schema_name: str, version: SchemaVersion):
        """Register a schema version"""
        with self._lock:
            if schema_type == "entity":
                self._entity_schemas[schema_name] = version
            elif schema_type == "insight":
                self._insight_schemas[schema_name] = version
            elif schema_type == "prediction":
                self._prediction_schemas[schema_name] = version
            elif schema_type == "metric":
                self._metric_schemas[schema_name] = version

            self.logger.info(f"Registered {schema_type} schema: {schema_name} v{version}")

    def add_evolution_rule(self, rule: SchemaEvolutionRule, schema_type: str):
        """Add a schema evolution rule"""
        with self._lock:
            self._evolution_rules[schema_type].append(rule)
            self.logger.info(
                f"Added evolution rule for {schema_type}: {rule.from_version} -> {rule.to_version}"
            )

    def evolve_data(
        self,
        data: Dict[str, Any],
        from_version: SchemaVersion,
        to_version: SchemaVersion,
        schema_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Evolve data from one schema version to another"""
        rules = self._evolution_rules.get(schema_type, [])

        current_data = data
        current_version = from_version

        while current_version < to_version:
            # Find applicable rule
            applicable_rule = None
            for rule in rules:
                if rule.from_version == current_version:
                    applicable_rule = rule
                    break

            if not applicable_rule:
                self.logger.error(
                    f"No evolution rule found for {schema_type} from {current_version}"
                )
                return None

            # Apply transformation
            try:
                current_data = applicable_rule.transformation(current_data)
                current_version = applicable_rule.to_version
            except Exception as e:
                self.logger.error(f"Evolution transformation failed: {str(e)}")
                return None

        return current_data

    def get_schema_version(
        self, schema_type: str, schema_name: str = "canonical"
    ) -> Optional[SchemaVersion]:
        """Get schema version"""
        with self._lock:
            if schema_type == "entity":
                return self._entity_schemas.get(schema_name)
            elif schema_type == "insight":
                return self._insight_schemas.get(schema_name)
            elif schema_type == "prediction":
                return self._prediction_schemas.get(schema_name)
            elif schema_type == "metric":
                return self._metric_schemas.get(schema_name)
            return None

    def get_schema_report(self) -> Dict[str, Any]:
        """Get comprehensive schema report"""
        with self._lock:
            return {
                "entity_schemas": {
                    name: str(version) for name, version in self._entity_schemas.items()
                },
                "insight_schemas": {
                    name: str(version) for name, version in self._insight_schemas.items()
                },
                "prediction_schemas": {
                    name: str(version) for name, version in self._prediction_schemas.items()
                },
                "metric_schemas": {
                    name: str(version) for name, version in self._metric_schemas.items()
                },
                "evolution_rules": {
                    schema_type: len(rules) for schema_type, rules in self._evolution_rules.items()
                },
            }


def create_unified_data_model(
    config: ConfigurationManager, logger: EnterpriseLogger
) -> UnifiedDataModel:
    """Factory function to create unified data model"""
    udm = UnifiedDataModel(config, logger)
    return udm


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (amplitude_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("amplitude_kernel")([1.0, 1.0], n)
    result["module"] = __name__
    return result
