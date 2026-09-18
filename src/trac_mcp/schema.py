#!/usr/bin/env python3
"""Small JSON-schema subset shared by the MCP adapter and local CLI."""

from __future__ import annotations

from typing import Any


class SchemaValidationError(ValueError):
    """A value does not satisfy the supported schema subset."""


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_value(value: Any, schema: dict[str, Any], path: str) -> None:
    expected = schema.get("type")

    if expected == "object":
        if not isinstance(value, dict):
            raise SchemaValidationError(f"{path} must be an object")
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        missing = required - set(value)
        if missing:
            raise SchemaValidationError(
                f"{path} is missing required field(s): {', '.join(sorted(missing))}"
            )
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                raise SchemaValidationError(
                    f"{path} has unsupported field(s): {', '.join(sorted(extra))}"
                )
        for key, item in value.items():
            child_schema = properties.get(key)
            if child_schema is not None:
                validate_value(item, child_schema, f"{path}.{key}")
        return

    if expected == "string":
        if not isinstance(value, str):
            raise SchemaValidationError(f"{path} must be a string")
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise SchemaValidationError(f"{path} is shorter than minLength")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise SchemaValidationError(f"{path} exceeds maxLength")
    elif expected == "integer":
        if not _is_integer(value):
            raise SchemaValidationError(f"{path} must be an integer")
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaValidationError(f"{path} is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaValidationError(f"{path} exceeds maximum")
    elif expected == "boolean":
        if not isinstance(value, bool):
            raise SchemaValidationError(f"{path} must be a boolean")
    elif expected == "array":
        if not isinstance(value, list):
            raise SchemaValidationError(f"{path} must be an array")
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise SchemaValidationError(f"{path} has too few items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise SchemaValidationError(f"{path} has too many items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_value(item, item_schema, f"{path}[{index}]")
    elif expected is not None:
        raise SchemaValidationError(
            f"{path} uses unsupported schema type {expected!r}"
        )

    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(f"{path} is not an allowed value")
