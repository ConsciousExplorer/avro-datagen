"""Schema validator -- checks Avro schemas for structural issues and common mistakes.

Validates:
- Required fields (name, type, fields for records)
- Valid primitive and logical types
- Logical type compatibility with base types (e.g. uuid must be on string)
- Known arg.properties hint keys (warns on unknown keys)
- Hints that are misplaced rather than misspelled: `args`/`kwargs`/`locale`
  without a sibling `faker`, and hints nested inside the type object
- faker specs: the method exists, the spec shape is known
- range bounds match the field's (logical) type
- options entries can be encoded as the field's Avro type
- Rule conditions reference declared fields
- ref targets exist and appear before the referencing field

Validation is not mandatory -- generate() still works with any schema the
resolver accepts. Use validate() before generation for clearer errors, or call
it from the `avro-datagen validate` CLI subcommand.
"""

import re
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
    # Only meaningful alongside a string-form `faker` hint — see _validate_faker
    "args",
    "kwargs",
    "locale",
}

# Keys that configure a faker call but do nothing on their own
_FAKER_SIBLING_KEYS = ("args", "kwargs", "locale")
_FAKER_SPEC_KEYS = {"method", "args", "kwargs", "locale"}

# Relative/absolute forms accepted by RecordResolver._parse_time_offset,
# _parse_date_offset and _parse_time_of_day respectively.
_TIME_OFFSET_RE = re.compile(r"^(-?\d+)([dhms])$")
_DAY_OFFSET_RE = re.compile(r"^([+-]?\d+)d$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_OF_DAY_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?$")

_NUMERIC_BASES = {"int", "long", "float", "double"}
_TEMPORAL_LOGICALS = {"timestamp-millis", "timestamp-micros", "iso-timestamp"}

_faker_methods: set[str] | None = None


def _known_faker_methods() -> set[str]:
    """Provider method names available on a default Faker instance.

    Built lazily and cached — instantiating Faker is not free, and `validate`
    is often called on schemas with no faker hints at all.
    """
    global _faker_methods
    if _faker_methods is None:
        from faker import Faker

        _faker_methods = {name for name in dir(Faker()) if not name.startswith("_")}
    return _faker_methods


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

        avro_type = field["type"]
        _validate_type(avro_type, field_path, errors, warnings)

        # The resolver reads arg.properties from inside the type object when
        # the field carries none (see RecordResolver._resolve_field), so a hint
        # written there must be checked too — that is precisely where a
        # misplaced key hides.
        props = field.get("arg.properties", {})
        if not props and isinstance(avro_type, dict):
            props = avro_type.get("arg.properties", {})

        _validate_arg_properties(
            props,
            field_path,
            seen_names,
            errors,
            warnings,
            avro_type,
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


def _logical_of(avro_type: Any) -> str | None:
    """Extract the logicalType, unwrapping unions.

    Mirrors RecordResolver._get_logical_type so the validator judges hints
    against the same type the resolver will act on.
    """
    if isinstance(avro_type, dict):
        return avro_type.get("logicalType")
    if isinstance(avro_type, list):
        for branch in avro_type:
            if isinstance(branch, dict) and "logicalType" in branch:
                return branch["logicalType"]
    return None


def _base_of(avro_type: Any) -> str | None:
    """Extract the base primitive type name, unwrapping unions.

    Mirrors RecordResolver._get_base_type.
    """
    if isinstance(avro_type, str):
        return avro_type
    if isinstance(avro_type, dict):
        return avro_type.get("type")
    if isinstance(avro_type, list):
        for branch in avro_type:
            if isinstance(branch, dict):
                return branch.get("type")
            if isinstance(branch, str) and branch != "null":
                return branch
    return None


def _union_allows_null(avro_type: Any) -> bool:
    return isinstance(avro_type, list) and "null" in avro_type


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_faker(
    props: dict,
    path: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Validate a faker hint and the sibling keys that configure it.

    The string form takes `args`/`kwargs`/`locale` from its siblings in the
    same arg.properties block; the dict form carries them inside the spec.
    """
    spec = props["faker"]

    if isinstance(spec, str):
        method_name: str | None = spec
        call_spec = props
        spec_label = path
    elif isinstance(spec, dict):
        method_name = spec.get("method")
        call_spec = spec
        spec_label = f"{path}.faker"
        if method_name is None:
            errors.append(f"{spec_label}: faker spec is missing 'method'")
        elif not isinstance(method_name, str):
            errors.append(f"{spec_label}: faker 'method' must be a string")
            method_name = None
        for key in spec:
            if key not in _FAKER_SPEC_KEYS:
                warnings.append(f"{spec_label}: unknown faker spec key {key!r}")
    else:
        errors.append(f"{path}.faker: must be a method name or a spec object")
        return

    if isinstance(method_name, str) and method_name not in _known_faker_methods():
        warnings.append(f"{path}: unknown Faker method {method_name!r}")

    args = call_spec.get("args")
    if args is not None and not isinstance(args, (list, dict)):
        warnings.append(
            f"{spec_label}: faker 'args' should be a list (positional) or an "
            f"object (keyword), got {type(args).__name__}"
        )
    kwargs = call_spec.get("kwargs")
    if kwargs is not None and not isinstance(kwargs, dict):
        warnings.append(f"{spec_label}: faker 'kwargs' must be an object")
    locale = call_spec.get("locale")
    if locale is not None and not isinstance(locale, str):
        warnings.append(f"{spec_label}: faker 'locale' must be a string")


def _validate_range(
    range_spec: Any,
    avro_type: Any,
    path: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Check a range hint's shape against the field's (logical) type."""
    if not isinstance(range_spec, dict):
        errors.append(f"{path}.range: must be an object with 'min' and 'max'")
        return
    for bound in ("min", "max"):
        if bound not in range_spec:
            errors.append(f"{path}.range: missing {bound!r}")
    if "min" not in range_spec or "max" not in range_spec:
        return

    low, high = range_spec["min"], range_spec["max"]
    logical = _logical_of(avro_type)
    base = _base_of(avro_type)

    def bad(bound: str, value: Any, expected: str) -> None:
        warnings.append(f"{path}.range.{bound}: {value!r} is not valid for {expected}")

    if logical in _TEMPORAL_LOGICALS:
        for bound, value in (("min", low), ("max", high)):
            ok = _is_number(value) or (
                isinstance(value, str) and (value == "now" or _TIME_OFFSET_RE.match(value))
            )
            if not ok:
                bad(bound, value, f"{logical} (expects a number, 'now', or an offset like '-30d')")
        return

    if logical == "date":
        for bound, value in (("min", low), ("max", high)):
            ok = (isinstance(value, int) and not isinstance(value, bool)) or (
                isinstance(value, str)
                and (value == "today" or _DAY_OFFSET_RE.match(value) or _ISO_DATE_RE.match(value))
            )
            if not ok:
                bad(bound, value, "date (expects days-since-epoch, 'today', '-30d', or YYYY-MM-DD)")
        return

    if logical in ("time-millis", "time-micros"):
        for bound, value in (("min", low), ("max", high)):
            ok = (isinstance(value, int) and not isinstance(value, bool)) or (
                isinstance(value, str) and _TIME_OF_DAY_RE.match(value)
            )
            if not ok:
                bad(bound, value, f"{logical} (expects a number or 'HH:MM[:SS[.fff]]')")
        return

    if logical == "decimal" or base in _NUMERIC_BASES:
        numeric = True
        for bound, value in (("min", low), ("max", high)):
            if not _is_number(value):
                bad(bound, value, "a numeric range")
                numeric = False
        if numeric and low > high:
            warnings.append(f"{path}.range: min ({low}) is greater than max ({high})")
        return

    if base in ("string", "boolean", "bytes", "enum", "fixed"):
        warnings.append(
            f"{path}: 'range' has no effect on a {base!r} field without a "
            f"temporal or decimal logicalType"
        )


def _validate_options(
    options: Any,
    avro_type: Any,
    path: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Check that each option can be encoded as the field's Avro type."""
    if not isinstance(options, list):
        errors.append(f"{path}.options: must be a list")
        return
    if not options:
        warnings.append(f"{path}.options: is empty, no value can be generated")
        return

    base = _base_of(avro_type)
    logical = _logical_of(avro_type)
    allows_null = _union_allows_null(avro_type)
    symbols = avro_type.get("symbols") if isinstance(avro_type, dict) else None

    def flag(value: Any, expected: str) -> None:
        warnings.append(f"{path}.options: {value!r} is not encodable as {expected}")

    for value in options:
        if value is None:
            if not allows_null and base != "null":
                flag(value, "a non-nullable field")
            continue
        if base == "enum":
            if isinstance(symbols, list) and value not in symbols:
                flag(value, f"enum symbols {symbols}")
        elif base in ("string", "bytes") or logical in ("uuid", "iso-timestamp"):
            if not isinstance(value, str):
                flag(value, f"{base!r}")
        elif base in ("int", "long"):
            if not isinstance(value, int) or isinstance(value, bool):
                flag(value, f"{base!r}")
        elif base in ("float", "double"):
            if not _is_number(value):
                flag(value, f"{base!r}")
        elif base == "boolean" and not isinstance(value, bool):
            flag(value, "'boolean'")


def _validate_arg_properties(
    props: dict,
    path: str,
    seen_fields: list[str],
    errors: list[str],
    warnings: list[str],
    avro_type: Any = None,
) -> None:
    """Validate arg.properties hints on a field.

    `avro_type` is the type the hints resolve against, so range shapes and
    options values can be judged against it. It is None only when the caller
    genuinely does not know the type.
    """
    if not isinstance(props, dict):
        errors.append(f"{path}: arg.properties must be an object")
        return

    for key in props:
        if key not in _KNOWN_HINT_KEYS:
            warnings.append(f"{path}: unknown arg.properties key {key!r}")

    # faker spec, plus the sibling keys that only configure one
    if "faker" in props:
        _validate_faker(props, path, errors, warnings)
    else:
        for key in _FAKER_SIBLING_KEYS:
            if key in props:
                warnings.append(f"{path}: {key!r} has no effect without a sibling 'faker' hint")

    if "range" in props:
        _validate_range(props["range"], avro_type, path, errors, warnings)

    if "options" in props:
        _validate_options(props["options"], avro_type, path, errors, warnings)

    # items: hints applied to each element of an array
    if "items" in props:
        item_type = avro_type.get("items") if isinstance(avro_type, dict) else None
        items_props = props["items"]
        if isinstance(items_props, dict):
            _validate_arg_properties(
                items_props, f"{path}.items", seen_fields, errors, warnings, item_type
            )

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
                    # `then` hints resolve against the field's own type
                    _validate_arg_properties(
                        then, f"{rule_path}.then", seen_fields, errors, warnings, avro_type
                    )
