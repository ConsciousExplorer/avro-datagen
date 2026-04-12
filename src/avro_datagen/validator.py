"""Schema validator -- checks Avro schemas for structural issues and common mistakes.

Validates:
- Required fields (name, type, fields for records)
- Valid primitive and logical types
- Logical type compatibility with base types (e.g. uuid must be on string)
- Known arg.properties hint keys (warns on unknown keys)
- Rule conditions reference declared fields
- ref targets exist and appear before the referencing field

Validation is not mandatory -- generate() still works with any schema the
resolver accepts. Use validate() before generation for clearer errors, or call
it from the `avro-datagen validate` CLI subcommand.
"""

from pathlib import Path
from typing import Any

from avro_datagen.resolver import load_schema

_PRIMITIVE_TYPES = {"null", "boolean", "int", "long", "float", "double", "bytes", "string"}
_COMPLEX_TYPES = {"record", "array", "map", "enum", "fixed"}

# logical type -> allowed base types
_LOGICAL_TYPE_BASES: dict[str, set[str]] = {
    "uuid": {"string"},
    "timestamp-millis": {"long"},
    "timestamp-micros": {"long"},
    "iso-timestamp": {"string"},
    "date": {"int"},
    "time-millis": {"int"},
    "time-micros": {"long"},
    "decimal": {"bytes", "fixed"},
}

_KNOWN_HINT_KEYS = {
    "options",
    "range",
    "pool",
    "pattern",
    "faker",
    "ref",
    "template",
    "rules",
    "null_probability",
    "length",
    "min_length",
    "max_length",
    "items",
    "keys",
    "foreign_key",
}

_KNOWN_CONDITION_KEYS = {
    "field",
    "equals",
    "not_equals",
    "is_null",
    "in",
    "not_in",
    "gt",
    "gte",
    "lt",
    "lte",
    "matches",
}


class SchemaValidationError(ValueError):
    """Raised when a schema fails validation.

    Contains a list of error messages, one per issue found.  The first message
    is also used as the exception's main message.
    """

    def __init__(self, errors: list[str]):
        self.errors = errors
        message = errors[0] if errors else "Schema validation failed"
        if len(errors) > 1:
            message += f" ({len(errors) - 1} more issue(s))"
        super().__init__(message)


def validate(schema: dict | str | Path) -> list[str]:
    """Validate an Avro schema and return a list of warnings.

    Errors (structural problems) raise SchemaValidationError.  Warnings
    (unknown hint keys, etc.) are returned as a list.

    Args:
        schema: Parsed schema dict or path to an .avsc file.

    Returns:
        List of warning strings (empty if the schema is clean).

    Raises:
        SchemaValidationError: if the schema has structural errors.
    """
    if isinstance(schema, (str, Path)):
        schema = load_schema(schema)

    errors: list[str] = []
    warnings: list[str] = []
    _validate_record(schema, path="", errors=errors, warnings=warnings)

    if errors:
        raise SchemaValidationError(errors)
    return warnings


def _validate_record(schema: dict, path: str, errors: list[str], warnings: list[str]) -> None:
    """Validate a record schema node."""
    if not isinstance(schema, dict):
        errors.append(f"{path or 'root'}: expected record object, got {type(schema).__name__}")
        return

    if schema.get("type") != "record":
        errors.append(f"{path or 'root'}: top-level schema must be a record")
        return

    if "name" not in schema:
        errors.append(f"{path or 'root'}: record is missing 'name'")

    fields = schema.get("fields")
    if fields is None:
        errors.append(f"{path or 'root'}: record is missing 'fields'")
        return
    if not isinstance(fields, list):
        errors.append(f"{path or 'root'}: 'fields' must be a list")
        return

    # Track field names we've seen so refs/rules can reference them
    seen_names: list[str] = []
    for i, field in enumerate(fields):
        field_path = f"{path}.fields[{i}]" if path else f"fields[{i}]"
        if not isinstance(field, dict):
            errors.append(f"{field_path}: expected field object")
            continue

        name = field.get("name")
        if not name:
            errors.append(f"{field_path}: field is missing 'name'")
            continue
        if name in seen_names:
            errors.append(f"{field_path}: duplicate field name {name!r}")
        field_path = f"{path}.{name}" if path else name

        if "type" not in field:
            errors.append(f"{field_path}: field is missing 'type'")
            seen_names.append(name)
            continue

        _validate_type(field["type"], field_path, errors, warnings)
        _validate_arg_properties(
            field.get("arg.properties", {}),
            field_path,
            seen_names,
            errors,
            warnings,
        )
        seen_names.append(name)


def _validate_type(avro_type: Any, path: str, errors: list[str], warnings: list[str]) -> None:
    """Validate an Avro type (primitive, complex, or union)."""
    if isinstance(avro_type, str):
        if avro_type not in _PRIMITIVE_TYPES:
            errors.append(f"{path}: unknown primitive type {avro_type!r}")
        return

    if isinstance(avro_type, list):
        # Union
        if len(avro_type) < 2:
            errors.append(f"{path}: union must have at least 2 branches")
            return
        for branch in avro_type:
            _validate_type(branch, f"{path} (union branch)", errors, warnings)
        return

    if isinstance(avro_type, dict):
        inner = avro_type.get("type")
        if inner is None:
            errors.append(f"{path}: type object is missing 'type'")
            return

        # Logical type compatibility check
        logical = avro_type.get("logicalType")
        if logical is not None:
            allowed_bases = _LOGICAL_TYPE_BASES.get(logical)
            if allowed_bases is None:
                warnings.append(f"{path}: unknown logicalType {logical!r}")
            elif inner not in allowed_bases:
                errors.append(
                    f"{path}: logicalType {logical!r} requires base type "
                    f"in {sorted(allowed_bases)}, got {inner!r}"
                )
            if logical == "decimal":
                if "precision" not in avro_type:
                    errors.append(f"{path}: decimal requires 'precision'")
                else:
                    precision = avro_type["precision"]
                    scale = avro_type.get("scale", 0)
                    if not isinstance(precision, int) or precision <= 0:
                        errors.append(f"{path}: decimal 'precision' must be a positive int")
                    if not isinstance(scale, int) or scale < 0:
                        errors.append(f"{path}: decimal 'scale' must be a non-negative int")
                    elif isinstance(precision, int) and scale > precision:
                        errors.append(
                            f"{path}: decimal 'scale' ({scale}) cannot exceed "
                            f"'precision' ({precision})"
                        )

        # Complex type structure check
        if inner == "record":
            _validate_record(avro_type, path, errors, warnings)
        elif inner == "array":
            if "items" not in avro_type:
                errors.append(f"{path}: array is missing 'items'")
            else:
                _validate_type(avro_type["items"], f"{path}.items", errors, warnings)
        elif inner == "map":
            if "values" not in avro_type:
                errors.append(f"{path}: map is missing 'values'")
            else:
                _validate_type(avro_type["values"], f"{path}.values", errors, warnings)
        elif inner == "enum":
            symbols = avro_type.get("symbols")
            if not symbols or not isinstance(symbols, list):
                errors.append(f"{path}: enum must have a non-empty 'symbols' list")
        elif inner == "fixed":
            if "size" not in avro_type:
                errors.append(f"{path}: fixed is missing 'size'")
        elif inner in _PRIMITIVE_TYPES:
            pass  # primitive with optional logicalType is fine
        elif inner not in _COMPLEX_TYPES:
            errors.append(f"{path}: unknown type {inner!r}")
        return

    errors.append(f"{path}: unsupported type value {avro_type!r}")


def _validate_arg_properties(
    props: dict,
    path: str,
    seen_fields: list[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    """Validate arg.properties hints on a field."""
    if not isinstance(props, dict):
        errors.append(f"{path}: arg.properties must be an object")
        return

    for key in props:
        if key not in _KNOWN_HINT_KEYS:
            warnings.append(f"{path}: unknown arg.properties key {key!r}")

    # ref must reference a previously declared field
    ref = props.get("ref")
    if isinstance(ref, str) and ref not in seen_fields:
        errors.append(f"{path}: ref target {ref!r} does not exist or is declared after this field")

    # rules: validate conditions and recurse into `then` hints
    rules = props.get("rules")
    if rules is not None:
        if not isinstance(rules, list):
            errors.append(f"{path}.rules: must be a list")
        else:
            for i, rule in enumerate(rules):
                rule_path = f"{path}.rules[{i}]"
                if not isinstance(rule, dict):
                    errors.append(f"{rule_path}: must be an object")
                    continue
                cond = rule.get("when")
                if not isinstance(cond, dict):
                    errors.append(f"{rule_path}: missing 'when' object")
                else:
                    cond_field = cond.get("field")
                    if not cond_field:
                        errors.append(f"{rule_path}.when: missing 'field'")
                    elif cond_field not in seen_fields:
                        errors.append(
                            f"{rule_path}.when: field {cond_field!r} is not declared "
                            f"before this field"
                        )
                    # Warn on unknown condition keys
                    for key in cond:
                        if key not in _KNOWN_CONDITION_KEYS:
                            warnings.append(f"{rule_path}.when: unknown condition key {key!r}")
                # then may be null, a dict of hints, or a literal
                then = rule.get("then")
                if isinstance(then, dict):
                    _validate_arg_properties(
                        then, f"{rule_path}.then", seen_fields, errors, warnings
                    )
