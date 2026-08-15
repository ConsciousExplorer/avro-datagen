"""Tests for the schema validator."""

from pathlib import Path

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


def _one_field(avro_type, props):
    """A one-field record carrying `props` as arg.properties."""
    return {
        "type": "record",
        "name": "T",
        "fields": [{"name": "x", "type": avro_type, "arg.properties": props}],
    }


class TestFakerHintVocabulary:
    """Issue #17 lived undetected because hint typos were silently ignored (#18)."""

    def test_acceptance_case_unknown_key_reported_with_field_path(self):
        schema = _one_field("string", {"faker": "numerify", "argz": {"text": "####"}})
        warnings = validate(schema)
        assert any("argz" in w and w.startswith("x:") for w in warnings), warnings

    def test_sibling_args_form_is_clean(self):
        """The form fixed in #17 is first-class vocabulary now."""
        schema = _one_field("string", {"faker": "numerify", "args": {"text": "####"}})
        assert validate(schema) == []

    def test_sibling_kwargs_and_locale_are_clean(self):
        schema = _one_field("string", {"faker": "name", "kwargs": {}, "locale": "ja_JP"})
        assert validate(schema) == []

    def test_args_without_faker_is_warned(self):
        schema = _one_field("string", {"options": ["a"], "args": {"text": "####"}})
        warnings = validate(schema)
        assert any("'args'" in w and "without a sibling 'faker'" in w for w in warnings), warnings

    def test_kwargs_without_faker_is_warned(self):
        schema = _one_field("string", {"pattern": "[A-Z]{2}", "kwargs": {"min": 1}})
        warnings = validate(schema)
        assert any("'kwargs'" in w for w in warnings), warnings

    def test_unknown_faker_method_is_warned(self):
        schema = _one_field("string", {"faker": "not_a_real_provider"})
        warnings = validate(schema)
        assert any("unknown Faker method" in w for w in warnings), warnings

    def test_known_faker_method_is_clean(self):
        assert validate(_one_field("string", {"faker": "email"})) == []

    def test_dict_form_missing_method_is_error(self):
        schema = _one_field("string", {"faker": {"args": ["###"]}})
        with pytest.raises(SchemaValidationError, match="missing 'method'"):
            validate(schema)

    def test_dict_form_unknown_spec_key_is_warned(self):
        schema = _one_field("string", {"faker": {"method": "numerify", "arguments": ["###"]}})
        warnings = validate(schema)
        assert any("unknown faker spec key" in w and "arguments" in w for w in warnings), warnings

    def test_dict_form_is_clean(self):
        schema = _one_field("string", {"faker": {"method": "bothify", "args": ["###-???"]}})
        assert validate(schema) == []

    def test_bad_args_type_is_warned(self):
        schema = _one_field("string", {"faker": "numerify", "args": 5})
        warnings = validate(schema)
        assert any("'args' should be a list" in w for w in warnings), warnings

    def test_bad_kwargs_type_is_warned(self):
        schema = _one_field("string", {"faker": "numerify", "kwargs": ["a"]})
        warnings = validate(schema)
        assert any("'kwargs' must be an object" in w for w in warnings), warnings

    def test_bad_locale_type_is_warned(self):
        schema = _one_field("string", {"faker": "name", "locale": 42})
        warnings = validate(schema)
        assert any("'locale' must be a string" in w for w in warnings), warnings


class TestRangeShape:
    def test_missing_min_is_error(self):
        schema = _one_field("int", {"range": {"max": 10}})
        with pytest.raises(SchemaValidationError, match="missing 'min'"):
            validate(schema)

    def test_non_object_range_is_error(self):
        schema = _one_field("int", {"range": [1, 10]})
        with pytest.raises(SchemaValidationError, match="must be an object"):
            validate(schema)

    def test_numeric_range_is_clean(self):
        assert validate(_one_field("int", {"range": {"min": 1, "max": 10}})) == []

    def test_string_bounds_on_numeric_field_are_warned(self):
        schema = _one_field("int", {"range": {"min": "1", "max": "10"}})
        warnings = validate(schema)
        assert any("not valid for a numeric range" in w for w in warnings), warnings

    def test_inverted_numeric_range_is_warned(self):
        schema = _one_field("int", {"range": {"min": 10, "max": 1}})
        warnings = validate(schema)
        assert any("greater than max" in w for w in warnings), warnings

    def test_timestamp_offsets_are_clean(self):
        ts = {"type": "long", "logicalType": "timestamp-millis"}
        assert validate(_one_field(ts, {"range": {"min": "-30d", "max": "now"}})) == []

    def test_bad_timestamp_bound_is_warned(self):
        ts = {"type": "long", "logicalType": "timestamp-millis"}
        warnings = validate(_one_field(ts, {"range": {"min": "yesterday", "max": "now"}}))
        assert any("yesterday" in w for w in warnings), warnings

    def test_date_forms_are_clean(self):
        d = {"type": "int", "logicalType": "date"}
        assert validate(_one_field(d, {"range": {"min": "2024-01-01", "max": "today"}})) == []
        assert validate(_one_field(d, {"range": {"min": "-30d", "max": "+7d"}})) == []

    def test_bad_date_bound_is_warned(self):
        d = {"type": "int", "logicalType": "date"}
        warnings = validate(_one_field(d, {"range": {"min": "01/01/2024", "max": "today"}}))
        assert any("01/01/2024" in w for w in warnings), warnings

    def test_time_of_day_is_clean(self):
        t = {"type": "int", "logicalType": "time-millis"}
        assert validate(_one_field(t, {"range": {"min": "09:00", "max": "17:30:00"}})) == []

    def test_bad_time_of_day_is_warned(self):
        t = {"type": "int", "logicalType": "time-millis"}
        warnings = validate(_one_field(t, {"range": {"min": "9am", "max": "17:30"}}))
        assert any("9am" in w for w in warnings), warnings

    def test_range_on_plain_string_is_warned(self):
        warnings = validate(_one_field("string", {"range": {"min": 1, "max": 5}}))
        assert any("has no effect on a 'string' field" in w for w in warnings), warnings

    def test_range_on_nullable_timestamp_union_is_clean(self):
        ts = ["null", {"type": "long", "logicalType": "timestamp-millis"}]
        assert validate(_one_field(ts, {"range": {"min": "-1d", "max": "now"}})) == []


class TestOptionsEncodability:
    def test_matching_strings_are_clean(self):
        assert validate(_one_field("string", {"options": ["a", "b"]})) == []

    def test_string_option_on_int_field_is_warned(self):
        warnings = validate(_one_field("int", {"options": [1, "two", 3]}))
        assert any("'two'" in w and "not encodable" in w for w in warnings), warnings

    def test_int_option_on_string_field_is_warned(self):
        warnings = validate(_one_field("string", {"options": ["a", 2]}))
        assert any("not encodable" in w for w in warnings), warnings

    def test_bool_is_not_accepted_as_int(self):
        warnings = validate(_one_field("int", {"options": [1, True]}))
        assert any("not encodable" in w for w in warnings), warnings

    def test_int_option_on_double_field_is_clean(self):
        assert validate(_one_field("double", {"options": [1, 2.5]})) == []

    def test_null_option_needs_a_null_union_branch(self):
        warnings = validate(_one_field("string", {"options": ["a", None]}))
        assert any("non-nullable" in w for w in warnings), warnings

    def test_null_option_on_nullable_union_is_clean(self):
        assert validate(_one_field(["null", "string"], {"options": ["a", None]})) == []

    def test_non_list_options_is_error(self):
        with pytest.raises(SchemaValidationError, match="must be a list"):
            validate(_one_field("string", {"options": "a"}))

    def test_empty_options_is_warned(self):
        warnings = validate(_one_field("string", {"options": []}))
        assert any("is empty" in w for w in warnings), warnings

    def test_enum_options_must_be_declared_symbols(self):
        enum = {"type": "enum", "name": "E", "symbols": ["A", "B"]}
        assert validate(_one_field(enum, {"options": ["A"]})) == []
        warnings = validate(_one_field(enum, {"options": ["C"]}))
        assert any("enum symbols" in w for w in warnings), warnings


class TestMisplacedHints:
    def test_hints_inside_the_type_object_are_checked(self):
        """The resolver reads these (#11), so the validator must too."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "x",
                    "type": {"type": "int", "arg.properties": {"rnage": {"min": 1, "max": 5}}},
                }
            ],
        }
        warnings = validate(schema)
        assert any("rnage" in w for w in warnings), warnings

    def test_valid_hints_inside_the_type_object_stay_clean(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "x",
                    "type": {"type": "int", "arg.properties": {"range": {"min": 1, "max": 5}}},
                }
            ],
        }
        assert validate(schema) == []

    def test_array_items_hints_are_checked(self):
        schema = _one_field(
            {"type": "array", "items": "string"},
            {"length": 3, "items": {"faker": "numerify", "argz": ["###"]}},
        )
        warnings = validate(schema)
        assert any("argz" in w and "x.items" in w for w in warnings), warnings

    def test_array_items_hints_validate_against_the_item_type(self):
        schema = _one_field(
            {"type": "array", "items": "int"},
            {"items": {"options": ["not-an-int"]}},
        )
        warnings = validate(schema)
        assert any("not encodable" in w for w in warnings), warnings

    def test_rules_then_hints_validate_against_the_field_type(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "kind", "type": "string"},
                {
                    "name": "n",
                    "type": "int",
                    "arg.properties": {
                        "rules": [
                            {"when": {"field": "kind", "equals": "a"}, "then": {"options": ["x"]}}
                        ]
                    },
                },
            ],
        }
        warnings = validate(schema)
        assert any("not encodable" in w for w in warnings), warnings


class TestCheckedInSchemasStayClean:
    """Regression gate: the new checks must not start flagging shipped schemas."""

    @pytest.mark.parametrize(
        "relative",
        [
            "schemas/example3.avsc",
            "src/avro_datagen/schemas/sample.avsc",
            "tests/fixtures/example.avsc",
            "tests/fixtures/faker_fields.avsc",
            "tests/fixtures/transaction.avsc",
        ],
    )
    def test_no_warnings(self, relative):
        root = Path(__file__).resolve().parents[1]
        assert validate(root / relative) == []
