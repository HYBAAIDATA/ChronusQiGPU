"""Shared validation and serialization for expert skill contracts."""

from __future__ import annotations

import math
from typing import Any, Mapping


class SkillError(RuntimeError):
    """A skill could not produce a supported result."""


def validate_schema(value: Any, schema: Mapping[str, Any], path: str = "$") -> list[str]:
    """Validate the JSON Schema subset used by the registered skill contracts."""
    expected = schema.get("type")
    valid_types = expected if isinstance(expected, list) else [expected]
    matches = {
        "object": lambda item: isinstance(item, Mapping),
        "array": lambda item: isinstance(item, (list, tuple)),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if valid_types and not any(matches.get(kind, lambda _: False)(value) for kind in valid_types):
        return [f"{path} must be of type {' or '.join(valid_types)}"]

    errors: list[str] = []
    if isinstance(value, Mapping):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key} is required")
        if schema.get("additionalProperties") is False:
            errors.extend(f"{path}.{key} is not allowed" for key in value if key not in properties)
        for key, item in value.items():
            if key in properties:
                errors.extend(validate_schema(item, properties[key], f"{path}.{key}"))
    if isinstance(value, (list, tuple)) and "items" in schema:
        for index, item in enumerate(value):
            errors.extend(validate_schema(item, schema["items"], f"{path}[{index}]"))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(float(value)):
            errors.append(f"{path} must be finite")
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path} must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path} must be <= {schema['maximum']}")
    if isinstance(value, str) and "minLength" in schema and len(value) < schema["minLength"]:
        errors.append(f"{path} must contain at least {schema['minLength']} characters")
    if (
        isinstance(value, (list, tuple))
        and "maxItems" in schema
        and len(value) > schema["maxItems"]
    ):
        errors.append(f"{path} must contain at most {schema['maxItems']} items")
    return errors


def json_safe(value: Any) -> Any:
    """Convert supported result values to JSON-compatible primitives."""
    if isinstance(value, bytes):
        return list(value)
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "as_dict") and callable(value.as_dict):
        return json_safe(value.as_dict())
    return value
