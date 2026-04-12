"""Tests for the field resolver engine."""

import random
import uuid
from datetime import UTC, datetime

from avro_datagen.resolver import RecordResolver


class TestPrimitiveTypes:
    """Resolver generates correct values for bare Avro primitive types."""

    def test_string_field(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "x", "type": "string"},
            ],
        }
        record = RecordResolver(schema).generate()
        assert isinstance(record["x"], str)

    def test_int_field(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "x", "type": "int"},
            ],
        }
        record = RecordResolver(schema).generate()
        assert isinstance(record["x"], int)

    def test_long_field(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "x", "type": "long"},
            ],
        }
        record = RecordResolver(schema).generate()
        assert isinstance(record["x"], int)

    def test_double_field(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "x", "type": "double"},
            ],
        }
        record = RecordResolver(schema).generate()
        assert isinstance(record["x"], float)

    def test_boolean_field(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "x", "type": "boolean"},
            ],
        }
        record = RecordResolver(schema).generate()
        assert isinstance(record["x"], bool)

    def test_null_field(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "x", "type": "null"},
            ],
        }
        record = RecordResolver(schema).generate()
        assert record["x"] is None


class TestLogicalTypes:
    def test_uuid(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "id", "type": {"type": "string", "logicalType": "uuid"}},
            ],
        }
        record = RecordResolver(schema).generate()
        uuid.UUID(record["id"])  # raises if invalid

    def test_timestamp_millis(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "ts", "type": {"type": "long", "logicalType": "timestamp-millis"}},
            ],
        }
        record = RecordResolver(schema).generate()
        assert isinstance(record["ts"], int)
        assert record["ts"] > 0

    def test_iso_timestamp(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "ts", "type": {"type": "string", "logicalType": "iso-timestamp"}},
            ],
        }
        record = RecordResolver(schema).generate()
        parsed = datetime.fromisoformat(record["ts"])
        assert parsed.tzinfo is not None


class TestDefault:
    def test_default_value_used(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "currency", "type": "string", "default": "ZAR"},
            ],
        }
        record = RecordResolver(schema).generate()
        assert record["currency"] == "ZAR"


class TestOptions:
    def test_picks_from_options(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "color",
                    "type": "string",
                    "arg.properties": {
                        "options": ["red", "green", "blue"],
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            record = RecordResolver(schema).generate()
            assert record["color"] in ("red", "green", "blue")


class TestRange:
    def test_numeric_range(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "amount",
                    "type": "double",
                    "arg.properties": {
                        "range": {"min": 10.0, "max": 100.0},
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            record = RecordResolver(schema).generate()
            assert 10.0 <= record["amount"] <= 100.0

    def test_int_range(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "qty",
                    "type": "int",
                    "arg.properties": {
                        "range": {"min": 1, "max": 10},
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            record = RecordResolver(schema).generate()
            assert 1 <= record["qty"] <= 10
            assert isinstance(record["qty"], int)

    def test_timestamp_range(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "ts",
                    "type": {"type": "long", "logicalType": "timestamp-millis"},
                    "arg.properties": {"range": {"min": "-30d", "max": "now"}},
                },
            ],
        }
        record = RecordResolver(schema).generate()
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        thirty_days_ago_ms = now_ms - 30 * 86400 * 1000
        # Allow a small tolerance for test execution time
        assert thirty_days_ago_ms - 1000 <= record["ts"] <= now_ms + 1000


class TestPool:
    def test_pool_reuses_values(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "cid",
                    "type": {"type": "string", "logicalType": "uuid"},
                    "arg.properties": {"pool": 5},
                },
            ],
        }
        random.seed(42)
        resolver = RecordResolver(schema)
        values = [resolver.generate()["cid"] for _ in range(50)]
        unique = set(values)
        # Pool of 5 means at most 5 unique values
        assert len(unique) <= 5
        # But we should see reuse
        assert len(values) > len(unique)


class TestPattern:
    def test_simple_pattern(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "code",
                    "type": "string",
                    "arg.properties": {
                        "pattern": "[A-Z]{3}-[0-9]{4}",
                    },
                },
            ],
        }
        random.seed(42)
        record = RecordResolver(schema).generate()
        import re

        assert re.match(r"^[A-Z]{3}-[0-9]{4}$", record["code"])


class TestRef:
    def test_ref_copies_value(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "source",
                    "type": "string",
                    "arg.properties": {
                        "options": ["alpha", "beta"],
                    },
                },
                {
                    "name": "copy",
                    "type": "string",
                    "arg.properties": {
                        "ref": "source",
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(20):
            record = RecordResolver(schema).generate()
            assert record["copy"] == record["source"]

    def test_ref_epoch_to_iso_conversion(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "epoch",
                    "type": {"type": "long", "logicalType": "timestamp-millis"},
                    "arg.properties": {"range": {"min": "-1d", "max": "now"}},
                },
                {
                    "name": "iso",
                    "type": {"type": "string", "logicalType": "iso-timestamp"},
                    "arg.properties": {"ref": "epoch"},
                },
            ],
        }
        record = RecordResolver(schema).generate()
        # epoch is millis, iso should be an ISO string of the same instant
        dt = datetime.fromisoformat(record["iso"])
        epoch_from_iso = int(dt.timestamp() * 1000)
        assert abs(epoch_from_iso - record["epoch"]) < 1000


class TestRules:
    def test_conditional_options(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "txn_type",
                    "type": "string",
                    "arg.properties": {
                        "options": ["debit", "credit"],
                    },
                },
                {
                    "name": "merchant",
                    "type": "string",
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "txn_type", "equals": "debit"},
                                "then": {"options": ["Shop A", "Shop B"]},
                            },
                            {
                                "when": {"field": "txn_type", "equals": "credit"},
                                "then": {"options": ["Refund Corp"]},
                            },
                        ],
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            record = RecordResolver(schema).generate()
            if record["txn_type"] == "debit":
                assert record["merchant"] in ("Shop A", "Shop B")
            else:
                assert record["merchant"] == "Refund Corp"

    def test_conditional_null(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "txn_type",
                    "type": "string",
                    "arg.properties": {
                        "options": ["debit", "credit"],
                    },
                },
                {
                    "name": "reason",
                    "type": ["null", "string"],
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "txn_type", "equals": "credit"},
                                "then": {"options": ["damaged", "wrong"]},
                            },
                            {"when": {"field": "txn_type", "equals": "debit"}, "then": None},
                        ],
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            record = RecordResolver(schema).generate()
            if record["txn_type"] == "debit":
                assert record["reason"] is None
            else:
                assert record["reason"] in ("damaged", "wrong")

    def test_conditional_range(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "size",
                    "type": "string",
                    "arg.properties": {
                        "options": ["small", "large"],
                    },
                },
                {
                    "name": "amount",
                    "type": "double",
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "size", "equals": "small"},
                                "then": {"range": {"min": 1.0, "max": 10.0}},
                            },
                            {
                                "when": {"field": "size", "equals": "large"},
                                "then": {"range": {"min": 100.0, "max": 1000.0}},
                            },
                        ],
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            record = RecordResolver(schema).generate()
            if record["size"] == "small":
                assert 1.0 <= record["amount"] <= 10.0
            else:
                assert 100.0 <= record["amount"] <= 1000.0

    def test_is_null_condition(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "opt",
                    "type": ["null", "string"],
                    "arg.properties": {
                        "options": [None, "present"],
                    },
                },
                {
                    "name": "fallback",
                    "type": "string",
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "opt", "is_null": True},
                                "then": {"options": ["default_value"]},
                            },
                            {"when": {"field": "opt", "is_null": False}, "then": {"ref": "opt"}},
                        ],
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            record = RecordResolver(schema).generate()
            if record["opt"] is None:
                assert record["fallback"] == "default_value"
            else:
                assert record["fallback"] == record["opt"]

    def test_in_condition(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "cat",
                    "type": "string",
                    "arg.properties": {
                        "options": ["A", "B", "C"],
                    },
                },
                {
                    "name": "label",
                    "type": "string",
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "cat", "in": ["A", "B"]},
                                "then": {"options": ["group1"]},
                            },
                            {
                                "when": {"field": "cat", "equals": "C"},
                                "then": {"options": ["group2"]},
                            },
                        ],
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            record = RecordResolver(schema).generate()
            if record["cat"] in ("A", "B"):
                assert record["label"] == "group1"
            else:
                assert record["label"] == "group2"

    def test_template(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "first",
                    "type": "string",
                    "arg.properties": {
                        "options": ["Alice", "Bob"],
                    },
                },
                {
                    "name": "greeting",
                    "type": "string",
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "first", "equals": "Alice"},
                                "then": {"template": "Hello {first}!"},
                            },
                            {
                                "when": {"field": "first", "equals": "Bob"},
                                "then": {"template": "Hi {first}!"},
                            },
                        ],
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(20):
            record = RecordResolver(schema).generate()
            if record["first"] == "Alice":
                assert record["greeting"] == "Hello Alice!"
            else:
                assert record["greeting"] == "Hi Bob!"


class TestUnion:
    def test_nullable_field_produces_both(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "opt", "type": ["null", "string"]},
            ],
        }
        random.seed(42)
        resolver = RecordResolver(schema)
        values = [resolver.generate()["opt"] for _ in range(100)]
        nulls = [v for v in values if v is None]
        non_nulls = [v for v in values if v is not None]
        assert len(nulls) > 0, "Expected some null values"
        assert len(non_nulls) > 0, "Expected some non-null values"

    def test_null_probability_custom(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "opt",
                    "type": ["null", "string"],
                    "arg.properties": {"null_probability": 0.9},
                },
            ],
        }
        random.seed(42)
        resolver = RecordResolver(schema)
        values = [resolver.generate()["opt"] for _ in range(200)]
        null_ratio = sum(1 for v in values if v is None) / len(values)
        # With 0.9 probability, expect mostly nulls (allow some variance)
        assert null_ratio > 0.7, f"Expected mostly nulls, got {null_ratio:.0%}"

    def test_null_probability_zero_never_null(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "opt",
                    "type": ["null", "string"],
                    "arg.properties": {"null_probability": 0.0},
                },
            ],
        }
        random.seed(42)
        resolver = RecordResolver(schema)
        values = [resolver.generate()["opt"] for _ in range(100)]
        assert all(v is not None for v in values), "Expected no nulls with null_probability=0"

    def test_multi_branch_union_picks_all_types(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "val",
                    "type": ["null", "string", "int"],
                    "arg.properties": {"null_probability": 0.0},
                },
            ],
        }
        random.seed(42)
        resolver = RecordResolver(schema)
        values = [resolver.generate()["val"] for _ in range(200)]
        types_seen = {type(v) for v in values}
        assert str in types_seen, "Expected some string values"
        assert int in types_seen, "Expected some int values"

    def test_multi_branch_union_with_null(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "val",
                    "type": ["null", "string", "int"],
                },
            ],
        }
        random.seed(42)
        resolver = RecordResolver(schema)
        values = [resolver.generate()["val"] for _ in range(300)]
        types_seen = {type(v) for v in values}
        assert type(None) in types_seen, "Expected some null values"
        assert str in types_seen, "Expected some string values"
        assert int in types_seen, "Expected some int values"


class TestEnum:
    def test_enum_picks_from_symbols(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "status",
                    "type": {
                        "type": "enum",
                        "name": "Status",
                        "symbols": ["ACTIVE", "INACTIVE", "PENDING"],
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(30):
            record = RecordResolver(schema).generate()
            assert record["status"] in ("ACTIVE", "INACTIVE", "PENDING")


class TestArray:
    def test_array_of_strings(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "tags",
                    "type": {"type": "array", "items": "string"},
                    "arg.properties": {
                        "length": {"min": 2, "max": 4},
                        "items": {"options": ["a", "b", "c"]},
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(20):
            record = RecordResolver(schema).generate()
            assert 2 <= len(record["tags"]) <= 4
            assert all(t in ("a", "b", "c") for t in record["tags"])

    def test_array_of_records(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "items",
                    "type": {
                        "type": "array",
                        "items": {
                            "type": "record",
                            "name": "Item",
                            "fields": [
                                {"name": "sku", "type": "string"},
                                {
                                    "name": "qty",
                                    "type": "int",
                                    "arg.properties": {
                                        "range": {"min": 1, "max": 5},
                                    },
                                },
                            ],
                        },
                    },
                    "arg.properties": {"length": {"min": 1, "max": 3}},
                },
            ],
        }
        random.seed(42)
        record = RecordResolver(schema).generate()
        assert 1 <= len(record["items"]) <= 3
        for item in record["items"]:
            assert "sku" in item
            assert 1 <= item["qty"] <= 5


class TestNestedRecord:
    def test_nested_record(self):
        schema = {
            "type": "record",
            "name": "Outer",
            "fields": [
                {"name": "id", "type": "int"},
                {
                    "name": "inner",
                    "type": {
                        "type": "record",
                        "name": "Inner",
                        "fields": [
                            {
                                "name": "value",
                                "type": "string",
                                "arg.properties": {
                                    "options": ["x", "y"],
                                },
                            },
                        ],
                    },
                },
            ],
        }
        random.seed(42)
        record = RecordResolver(schema).generate()
        assert isinstance(record["inner"], dict)
        assert record["inner"]["value"] in ("x", "y")
