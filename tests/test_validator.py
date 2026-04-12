"""Tests for the schema validator."""

import pytest

from avro_datagen.validator import SchemaValidationError, validate


class TestBasicStructure:
    def test_valid_minimal_record(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [{"name": "x", "type": "string"}],
        }
        assert validate(schema) == []

    def test_missing_name_is_error(self):
        schema = {"type": "record", "fields": []}
        with pytest.raises(SchemaValidationError, match="missing 'name'"):
            validate(schema)

    def test_missing_fields_is_error(self):
        schema = {"type": "record", "name": "T"}
        with pytest.raises(SchemaValidationError, match="missing 'fields'"):
            validate(schema)

    def test_non_record_top_level_is_error(self):
        schema = {"type": "string", "name": "T"}
        with pytest.raises(SchemaValidationError, match="top-level schema must be a record"):
            validate(schema)

    def test_field_missing_name(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [{"type": "string"}],
        }
        with pytest.raises(SchemaValidationError, match="missing 'name'"):
            validate(schema)

    def test_field_missing_type(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [{"name": "x"}],
        }
        with pytest.raises(SchemaValidationError, match="missing 'type'"):
            validate(schema)

    def test_duplicate_field_names(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "x", "type": "string"},
                {"name": "x", "type": "int"},
            ],
        }
        with pytest.raises(SchemaValidationError, match="duplicate field name"):
            validate(schema)


class TestPrimitiveTypes:
    def test_unknown_primitive(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [{"name": "x", "type": "integer"}],  # should be "int"
        }
        with pytest.raises(SchemaValidationError, match="unknown primitive type"):
            validate(schema)

    def test_all_valid_primitives(self):
        for t in ["null", "boolean", "int", "long", "float", "double", "bytes", "string"]:
            schema = {
                "type": "record",
                "name": "T",
                "fields": [{"name": "x", "type": t}],
            }
            assert validate(schema) == []


class TestLogicalTypes:
    def test_uuid_requires_string(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [{"name": "x", "type": {"type": "int", "logicalType": "uuid"}}],
        }
        with pytest.raises(SchemaValidationError, match=r"uuid.*requires base type"):
            validate(schema)

    def test_timestamp_millis_requires_long(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "ts", "type": {"type": "string", "logicalType": "timestamp-millis"}}
            ],
        }
        with pytest.raises(SchemaValidationError):
            validate(schema)

    def test_decimal_requires_precision(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [{"name": "x", "type": {"type": "bytes", "logicalType": "decimal"}}],
        }
        with pytest.raises(SchemaValidationError, match="decimal requires 'precision'"):
            validate(schema)

    def test_decimal_scale_exceeds_precision(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "x",
                    "type": {
                        "type": "bytes",
                        "logicalType": "decimal",
                        "precision": 5,
                        "scale": 10,
                    },
                }
            ],
        }
        with pytest.raises(SchemaValidationError, match=r"scale.*cannot exceed"):
            validate(schema)

    def test_unknown_logical_type_is_warning(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [{"name": "x", "type": {"type": "string", "logicalType": "custom-type"}}],
        }
        warnings = validate(schema)
        assert any("unknown logicalType" in w for w in warnings)


class TestComplexTypes:
    def test_array_missing_items(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [{"name": "x", "type": {"type": "array"}}],
        }
        with pytest.raises(SchemaValidationError, match="missing 'items'"):
            validate(schema)

    def test_map_missing_values(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [{"name": "x", "type": {"type": "map"}}],
        }
        with pytest.raises(SchemaValidationError, match="missing 'values'"):
            validate(schema)

    def test_enum_missing_symbols(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [{"name": "x", "type": {"type": "enum", "name": "E"}}],
        }
        with pytest.raises(SchemaValidationError, match="symbols"):
            validate(schema)

    def test_nested_record(self):
        schema = {
            "type": "record",
            "name": "Outer",
            "fields": [
                {
                    "name": "inner",
                    "type": {
                        "type": "record",
                        "name": "Inner",
                        "fields": [{"name": "x", "type": "string"}],
                    },
                }
            ],
        }
        assert validate(schema) == []


class TestRefValidation:
    def test_ref_to_nonexistent_field(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "x",
                    "type": "string",
                    "arg.properties": {"ref": "nonexistent"},
                }
            ],
        }
        with pytest.raises(SchemaValidationError, match="does not exist"):
            validate(schema)

    def test_ref_to_later_field(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "x",
                    "type": "string",
                    "arg.properties": {"ref": "y"},  # y is declared after x
                },
                {"name": "y", "type": "string"},
            ],
        }
        with pytest.raises(SchemaValidationError, match="declared after"):
            validate(schema)

    def test_ref_to_earlier_field_ok(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "source", "type": "string"},
                {
                    "name": "copy",
                    "type": "string",
                    "arg.properties": {"ref": "source"},
                },
            ],
        }
        assert validate(schema) == []


class TestRulesValidation:
    def test_rule_references_nonexistent_field(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "x",
                    "type": "string",
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "ghost", "equals": "yes"},
                                "then": {"options": ["a"]},
                            }
                        ]
                    },
                }
            ],
        }
        with pytest.raises(SchemaValidationError, match="not declared"):
            validate(schema)

    def test_rule_valid(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "cat", "type": "string"},
                {
                    "name": "label",
                    "type": "string",
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "cat", "equals": "a"},
                                "then": {"options": ["x"]},
                            }
                        ]
                    },
                },
            ],
        }
        assert validate(schema) == []

    def test_unknown_condition_key_is_warning(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "cat", "type": "string"},
                {
                    "name": "label",
                    "type": "string",
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "cat", "wrongkey": "a"},
                                "then": {"options": ["x"]},
                            }
                        ]
                    },
                },
            ],
        }
        warnings = validate(schema)
        assert any("unknown condition key" in w for w in warnings)


class TestHintWarnings:
    def test_unknown_hint_key_is_warning(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "x",
                    "type": "string",
                    "arg.properties": {"typo_key": "value"},
                }
            ],
        }
        warnings = validate(schema)
        assert any("typo_key" in w for w in warnings)


class TestMultipleErrors:
    def test_collects_multiple_errors(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "a", "type": "integer"},  # unknown primitive
                {"name": "b"},  # missing type
                {"name": "a", "type": "string"},  # duplicate name
            ],
        }
        with pytest.raises(SchemaValidationError) as exc_info:
            validate(schema)
        assert len(exc_info.value.errors) >= 3
