"""Tool schema definitions and validation for agent harness.

Provides dataclasses and utilities for defining tool schemas
compatible with Claude's tool use API.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


@dataclass
class PropertySchema:
    """Schema for a single property in a tool's input schema."""

    type: str
    description: str
    enum: Optional[list[str]] = None
    default: Optional[Any] = None
    items: Optional[dict[str, Any]] = None  # For array types


@dataclass
class ToolSchema:
    """Schema for a tool definition.

    Follows Claude's tool use API schema format.
    """

    name: str
    description: str
    properties: dict[str, PropertySchema] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to Claude API tool format.

        Returns:
            Dictionary in Claude's tool schema format.
        """
        properties_dict = {}
        for name, prop in self.properties.items():
            prop_dict: dict[str, Any] = {
                "type": prop.type,
                "description": prop.description,
            }
            if prop.enum is not None:
                prop_dict["enum"] = prop.enum
            if prop.default is not None:
                prop_dict["default"] = prop.default
            if prop.items is not None:
                prop_dict["items"] = prop.items
            properties_dict[name] = prop_dict

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties_dict,
                "required": self.required,
            },
        }


def create_tool_schema(
    name: str,
    description: str,
    properties: Optional[dict[str, dict[str, Any]]] = None,
    required: Optional[list[str]] = None,
) -> ToolSchema:
    """Create a ToolSchema from simplified parameters.

    Args:
        name: Tool name.
        description: Tool description.
        properties: Dictionary of property name to property definition.
        required: List of required property names.

    Returns:
        ToolSchema instance.

    Example:
        >>> schema = create_tool_schema(
        ...     name="run_test",
        ...     description="Run a test file",
        ...     properties={
        ...         "test_file": {
        ...             "type": "string",
        ...             "description": "Path to test file",
        ...         },
        ...         "verbose": {
        ...             "type": "boolean",
        ...             "description": "Enable verbose output",
        ...             "default": False,
        ...         },
        ...     },
        ...     required=["test_file"],
        ... )
    """
    props = {}
    if properties:
        for prop_name, prop_def in properties.items():
            props[prop_name] = PropertySchema(
                type=prop_def.get("type", "string"),
                description=prop_def.get("description", ""),
                enum=prop_def.get("enum"),
                default=prop_def.get("default"),
                items=prop_def.get("items"),
            )

    return ToolSchema(
        name=name,
        description=description,
        properties=props,
        required=required or [],
    )


def validate_schema(schema: ToolSchema) -> list[str]:
    """Validate a tool schema for common issues.

    Args:
        schema: ToolSchema to validate.

    Returns:
        List of validation error messages (empty if valid).
    """
    errors = []

    # Check name
    if not schema.name:
        errors.append("Tool name is required")
    elif not schema.name.replace("_", "").isalnum():
        errors.append(f"Tool name '{schema.name}' contains invalid characters")

    # Check description
    if not schema.description:
        errors.append("Tool description is required")

    # Check required fields exist in properties
    for req in schema.required:
        if req not in schema.properties:
            errors.append(f"Required field '{req}' not in properties")

    # Check property types are valid
    valid_types = {"string", "number", "integer", "boolean", "array", "object"}
    for name, prop in schema.properties.items():
        if prop.type not in valid_types:
            errors.append(f"Property '{name}' has invalid type '{prop.type}'")

        # Check array items
        if prop.type == "array" and prop.items is None:
            errors.append(f"Array property '{name}' missing 'items' definition")

    return errors


def validate_tool_input(
    schema: ToolSchema,
    inputs: dict[str, Any],
) -> list[str]:
    """Validate tool inputs against a schema.

    Args:
        schema: ToolSchema to validate against.
        inputs: Dictionary of input values.

    Returns:
        List of validation error messages (empty if valid).
    """
    errors = []

    # Check required fields
    for req in schema.required:
        if req not in inputs:
            errors.append(f"Missing required field: {req}")

    # Check types
    for name, value in inputs.items():
        if name not in schema.properties:
            # Extra fields are allowed but noted
            continue

        prop = schema.properties[name]
        expected_type = prop.type

        # Type validation
        type_valid = True
        if expected_type == "string" and not isinstance(value, str):
            type_valid = False
        elif expected_type == "number" and not isinstance(value, (int, float)):
            type_valid = False
        elif expected_type == "integer" and not isinstance(value, int):
            type_valid = False
        elif expected_type == "boolean" and not isinstance(value, bool):
            type_valid = False
        elif expected_type == "array" and not isinstance(value, list):
            type_valid = False
        elif expected_type == "object" and not isinstance(value, dict):
            type_valid = False

        if not type_valid:
            errors.append(
                f"Field '{name}' expected {expected_type}, got {type(value).__name__}"
            )

        # Enum validation
        if prop.enum is not None and value not in prop.enum:
            errors.append(
                f"Field '{name}' value '{value}' not in allowed values: {prop.enum}"
            )

    return errors
