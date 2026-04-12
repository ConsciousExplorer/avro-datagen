"""Tests for the field resolver engine."""

import random
import uuid
from datetime import UTC, datetime

import pytest

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

    def test_date_no_hint_is_realistic(self):
        """Date without hints produces a realistic value within the last ~5 years."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "d", "type": {"type": "int", "logicalType": "date"}},
            ],
        }
        random.seed(42)
        resolver = RecordResolver(schema)
        today_days = int(resolver.now_ts // 86400)
        for _ in range(50):
            value = resolver.generate()["d"]
            assert isinstance(value, int)
            assert today_days - 1825 <= value <= today_days

    def test_date_with_range(self):
        """Date range accepts ISO dates."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "d",
                    "type": {"type": "int", "logicalType": "date"},
                    "arg.properties": {"range": {"min": "2024-01-01", "max": "2024-12-31"}},
                },
            ],
        }
        random.seed(42)
        start = int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() // 86400)
        end = int(datetime(2024, 12, 31, tzinfo=UTC).timestamp() // 86400)
        for _ in range(50):
            value = RecordResolver(schema).generate()["d"]
            assert start <= value <= end

    def test_date_with_relative_range(self):
        """Date range accepts -Nd offsets and 'today'."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "d",
                    "type": {"type": "int", "logicalType": "date"},
                    "arg.properties": {"range": {"min": "-30d", "max": "today"}},
                },
            ],
        }
        random.seed(42)
        resolver = RecordResolver(schema)
        today = int(resolver.now_ts // 86400)
        for _ in range(50):
            value = resolver.generate()["d"]
            assert today - 30 <= value <= today

    def test_time_millis_no_hint(self):
        """time-millis produces ms within a day."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "t", "type": {"type": "int", "logicalType": "time-millis"}},
            ],
        }
        random.seed(42)
        for _ in range(50):
            value = RecordResolver(schema).generate()["t"]
            assert 0 <= value < 86_400_000

    def test_time_micros_no_hint(self):
        """time-micros produces us within a day."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {"name": "t", "type": {"type": "long", "logicalType": "time-micros"}},
            ],
        }
        random.seed(42)
        for _ in range(50):
            value = RecordResolver(schema).generate()["t"]
            assert 0 <= value < 86_400_000_000

    def test_time_millis_with_range(self):
        """time-millis range accepts HH:MM strings (business hours)."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "t",
                    "type": {"type": "int", "logicalType": "time-millis"},
                    "arg.properties": {"range": {"min": "09:00", "max": "17:00"}},
                },
            ],
        }
        random.seed(42)
        nine_am_ms = 9 * 3_600_000
        five_pm_ms = 17 * 3_600_000
        for _ in range(50):
            value = RecordResolver(schema).generate()["t"]
            assert nine_am_ms <= value <= five_pm_ms

    def test_decimal_respects_scale(self):
        """Decimal with scale=2 produces values with exactly 2 digits after the point."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "amount",
                    "type": {
                        "type": "bytes",
                        "logicalType": "decimal",
                        "precision": 10,
                        "scale": 2,
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            value = RecordResolver(schema).generate()["amount"]
            assert isinstance(value, str)
            from decimal import Decimal

            d = Decimal(value)
            _, frac = value.split(".")
            assert len(frac) == 2
            digits = value.replace(".", "").lstrip("0") or "0"
            assert len(digits) <= 10
            assert d >= 0

    def test_decimal_respects_precision(self):
        """Decimal respects precision — integer part <= (precision - scale) digits."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "amount",
                    "type": {
                        "type": "bytes",
                        "logicalType": "decimal",
                        "precision": 5,
                        "scale": 2,
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            value = RecordResolver(schema).generate()["amount"]
            int_part, _ = value.split(".")
            assert len(int_part) <= 3

    def test_decimal_zero_scale(self):
        """Decimal with scale=0 produces integer strings (no decimal point)."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "count",
                    "type": {
                        "type": "bytes",
                        "logicalType": "decimal",
                        "precision": 8,
                        "scale": 0,
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            value = RecordResolver(schema).generate()["count"]
            assert "." not in value
            assert value.isdigit()

    def test_decimal_with_range(self):
        """Decimal range produces values within bounds and respects scale."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "price",
                    "type": {
                        "type": "bytes",
                        "logicalType": "decimal",
                        "precision": 10,
                        "scale": 2,
                    },
                    "arg.properties": {"range": {"min": 10.0, "max": 500.0}},
                },
            ],
        }
        random.seed(42)
        from decimal import Decimal

        for _ in range(50):
            value = RecordResolver(schema).generate()["price"]
            d = Decimal(value)
            assert Decimal("10") <= d <= Decimal("500")
            assert len(value.split(".")[1]) == 2


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


class TestForeignKey:
    def test_foreign_key_from_jsonl_file(self, tmp_path):
        """foreign_key picks values from a JSON Lines file."""
        source = tmp_path / "customers.jsonl"
        source.write_text(
            '{"customerId": "cust-1", "name": "Alice"}\n'
            '{"customerId": "cust-2", "name": "Bob"}\n'
            '{"customerId": "cust-3", "name": "Carol"}\n'
        )
        schema = {
            "type": "record",
            "name": "Order",
            "fields": [
                {
                    "name": "customerId",
                    "type": "string",
                    "arg.properties": {"foreign_key": {"file": str(source), "field": "customerId"}},
                },
            ],
        }
        random.seed(42)
        resolver = RecordResolver(schema)
        values = {resolver.generate()["customerId"] for _ in range(50)}
        assert values.issubset({"cust-1", "cust-2", "cust-3"})
        # With 50 draws we should see at least 2 distinct values
        assert len(values) >= 2

    def test_foreign_key_from_json_array(self, tmp_path):
        """foreign_key also reads JSON arrays."""
        source = tmp_path / "customers.json"
        source.write_text('[{"id": "a"}, {"id": "b"}, {"id": "c"}]')
        schema = {
            "type": "record",
            "name": "Order",
            "fields": [
                {
                    "name": "ref",
                    "type": "string",
                    "arg.properties": {"foreign_key": {"file": str(source), "field": "id"}},
                },
            ],
        }
        random.seed(42)
        resolver = RecordResolver(schema)
        values = {resolver.generate()["ref"] for _ in range(30)}
        assert values.issubset({"a", "b", "c"})

    def test_foreign_key_file_loaded_once(self, tmp_path):
        """File is cached after first read (side effect: we can delete the file)."""
        source = tmp_path / "customers.jsonl"
        source.write_text('{"id": "x"}\n{"id": "y"}\n')
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "ref",
                    "type": "string",
                    "arg.properties": {"foreign_key": {"file": str(source), "field": "id"}},
                },
            ],
        }
        random.seed(42)
        resolver = RecordResolver(schema)
        # First generation loads the file
        first = resolver.generate()["ref"]
        assert first in ("x", "y")
        # Delete the file; subsequent generations should still work from cache
        source.unlink()
        for _ in range(20):
            assert resolver.generate()["ref"] in ("x", "y")

    def test_foreign_key_missing_file_raises(self, tmp_path):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "ref",
                    "type": "string",
                    "arg.properties": {
                        "foreign_key": {
                            "file": str(tmp_path / "nonexistent.jsonl"),
                            "field": "id",
                        }
                    },
                },
            ],
        }
        with pytest.raises(FileNotFoundError):
            RecordResolver(schema).generate()

    def test_foreign_key_missing_field_raises(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "ref",
                    "type": "string",
                    "arg.properties": {"foreign_key": {"file": "some.jsonl"}},
                },
            ],
        }
        with pytest.raises(ValueError, match="both 'file' and 'field'"):
            RecordResolver(schema).generate()

    def test_foreign_key_empty_file_raises(self, tmp_path):
        source = tmp_path / "empty.jsonl"
        source.write_text('{"other": "value"}\n')  # no matching field
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "ref",
                    "type": "string",
                    "arg.properties": {
                        "foreign_key": {"file": str(source), "field": "missing_field"}
                    },
                },
            ],
        }
        with pytest.raises(ValueError, match="no values"):
            RecordResolver(schema).generate()


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
    def _pattern_schema(self, pattern):
        return {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "code",
                    "type": "string",
                    "arg.properties": {"pattern": pattern},
                },
            ],
        }

    def test_simple_pattern(self):
        random.seed(42)
        record = RecordResolver(self._pattern_schema("[A-Z]{3}-[0-9]{4}")).generate()
        import re

        assert re.match(r"^[A-Z]{3}-[0-9]{4}$", record["code"])

    def test_literal_prefix(self):
        """Prefix literals mix with character classes."""
        random.seed(42)
        for _ in range(20):
            record = RecordResolver(self._pattern_schema("exist-[A-Z]{3}")).generate()
            assert record["code"].startswith("exist-")
            assert len(record["code"]) == len("exist-") + 3

    def test_shortcut_classes(self):
        """\\d, \\w, \\s shortcuts work."""
        import re

        random.seed(42)
        for _ in range(20):
            record = RecordResolver(self._pattern_schema(r"\d{3}-\w{4}")).generate()
            assert re.match(r"^[0-9]{3}-\w{4}$", record["code"])

    def test_range_quantifier(self):
        """{n,m} produces variable length."""
        random.seed(42)
        seen_lengths = set()
        for _ in range(50):
            record = RecordResolver(self._pattern_schema("[a-z]{3,6}")).generate()
            seen_lengths.add(len(record["code"]))
            assert 3 <= len(record["code"]) <= 6
        assert len(seen_lengths) > 1, "Expected varied lengths"

    def test_optional_quantifier(self):
        """? produces 0 or 1 occurrences."""
        random.seed(42)
        values = set()
        for _ in range(50):
            record = RecordResolver(self._pattern_schema("pre[0-9]?")).generate()
            values.add(record["code"])
        # Should see both "pre" and "pre<digit>"
        assert any(len(v) == 3 for v in values), "Expected some bare 'pre'"
        assert any(len(v) == 4 for v in values), "Expected some pre + digit"

    def test_plus_quantifier(self):
        """+ produces 1 or more (capped at 5)."""
        random.seed(42)
        for _ in range(50):
            record = RecordResolver(self._pattern_schema("[a-z]+")).generate()
            assert 1 <= len(record["code"]) <= 5

    def test_star_quantifier(self):
        """* produces 0 or more (capped at 5)."""
        random.seed(42)
        lengths = set()
        for _ in range(100):
            record = RecordResolver(self._pattern_schema("[a-z]*")).generate()
            lengths.add(len(record["code"]))
            assert 0 <= len(record["code"]) <= 5
        assert 0 in lengths, "Expected some empty strings"

    def test_alternation(self):
        """(a|b|c) picks one alternative."""
        random.seed(42)
        values = set()
        for _ in range(50):
            record = RecordResolver(self._pattern_schema("(cat|dog|bird)")).generate()
            values.add(record["code"])
        assert values == {"cat", "dog", "bird"}

    def test_alternation_with_quantifier(self):
        """Groups can have quantifiers."""
        random.seed(42)
        for _ in range(30):
            record = RecordResolver(self._pattern_schema("(foo|bar)-[0-9]{3}")).generate()
            assert record["code"].startswith(("foo-", "bar-"))
            assert len(record["code"]) == 7

    def test_negated_class(self):
        """[^0-9] excludes digits."""
        random.seed(42)
        for _ in range(30):
            record = RecordResolver(self._pattern_schema("[^0-9]{5}")).generate()
            assert not any(c.isdigit() for c in record["code"])

    def test_escape_literal(self):
        """\\. produces a literal dot, \\( a literal paren."""
        random.seed(42)
        for _ in range(10):
            record = RecordResolver(self._pattern_schema(r"[a-z]{3}\.[a-z]{3}")).generate()
            assert "." in record["code"]
            assert record["code"].count(".") == 1

    def test_unmatched_bracket_raises(self):
        """Malformed patterns raise ValueError, not IndexError."""
        random.seed(42)
        with pytest.raises(ValueError, match="Invalid pattern"):
            RecordResolver(self._pattern_schema("[A-Z")).generate()

    def test_unmatched_paren_raises(self):
        random.seed(42)
        with pytest.raises(ValueError, match="Invalid pattern"):
            RecordResolver(self._pattern_schema("(foo|bar")).generate()

    def test_empty_class_raises(self):
        random.seed(42)
        with pytest.raises(ValueError, match="Invalid pattern"):
            RecordResolver(self._pattern_schema("[]")).generate()

    def test_trailing_backslash_raises(self):
        random.seed(42)
        with pytest.raises(ValueError, match="Invalid pattern"):
            RecordResolver(self._pattern_schema("abc\\")).generate()


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

    def test_gt_condition(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "amount",
                    "type": "int",
                    "arg.properties": {"range": {"min": 0, "max": 2000}},
                },
                {
                    "name": "tier",
                    "type": "string",
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "amount", "gt": 1000},
                                "then": {"options": ["premium"]},
                            },
                            {
                                "when": {"field": "amount", "lte": 1000},
                                "then": {"options": ["standard"]},
                            },
                        ],
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(100):
            record = RecordResolver(schema).generate()
            if record["amount"] > 1000:
                assert record["tier"] == "premium"
            else:
                assert record["tier"] == "standard"

    def test_gte_lt_conditions(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "age",
                    "type": "int",
                    "arg.properties": {"range": {"min": 0, "max": 100}},
                },
                {
                    "name": "category",
                    "type": "string",
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "age", "lt": 18},
                                "then": {"options": ["minor"]},
                            },
                            {
                                "when": {"field": "age", "gte": 18},
                                "then": {"options": ["adult"]},
                            },
                        ],
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(100):
            record = RecordResolver(schema).generate()
            if record["age"] < 18:
                assert record["category"] == "minor"
            else:
                assert record["category"] == "adult"

    def test_not_equals_condition(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "status",
                    "type": "string",
                    "arg.properties": {"options": ["active", "inactive", "pending"]},
                },
                {
                    "name": "label",
                    "type": "string",
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "status", "not_equals": "active"},
                                "then": {"options": ["dormant"]},
                            },
                            {
                                "when": {"field": "status", "equals": "active"},
                                "then": {"options": ["live"]},
                            },
                        ],
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            record = RecordResolver(schema).generate()
            if record["status"] == "active":
                assert record["label"] == "live"
            else:
                assert record["label"] == "dormant"

    def test_not_in_condition(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "country",
                    "type": "string",
                    "arg.properties": {"options": ["US", "CA", "MX", "UK", "DE"]},
                },
                {
                    "name": "region",
                    "type": "string",
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "country", "not_in": ["US", "CA", "MX"]},
                                "then": {"options": ["EU"]},
                            },
                            {
                                "when": {"field": "country", "in": ["US", "CA", "MX"]},
                                "then": {"options": ["NA"]},
                            },
                        ],
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            record = RecordResolver(schema).generate()
            if record["country"] in ("US", "CA", "MX"):
                assert record["region"] == "NA"
            else:
                assert record["region"] == "EU"

    def test_matches_condition(self):
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "code",
                    "type": "string",
                    "arg.properties": {"options": ["A-123", "B-456", "XYZ", "C-789"]},
                },
                {
                    "name": "kind",
                    "type": "string",
                    "arg.properties": {
                        "rules": [
                            {
                                "when": {"field": "code", "matches": r"^[A-Z]-\d+$"},
                                "then": {"options": ["structured"]},
                            },
                        ],
                    },
                },
            ],
        }
        random.seed(42)
        for _ in range(50):
            record = RecordResolver(schema).generate()
            if record["code"] in ("A-123", "B-456", "C-789"):
                assert record["kind"] == "structured"


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

    def test_array_min_max_length_flat(self):
        """min_length/max_length work as a flat alternative to length dict."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "tags",
                    "type": {"type": "array", "items": "string"},
                    "arg.properties": {"min_length": 3, "max_length": 6},
                },
            ],
        }
        random.seed(42)
        for _ in range(30):
            record = RecordResolver(schema).generate()
            assert 3 <= len(record["tags"]) <= 6

    def test_array_fixed_length_int(self):
        """length: N (int) produces arrays of exactly N elements."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "tags",
                    "type": {"type": "array", "items": "string"},
                    "arg.properties": {"length": 3},
                },
            ],
        }
        random.seed(42)
        for _ in range(30):
            record = RecordResolver(schema).generate()
            assert len(record["tags"]) == 3

    def test_array_only_max_length(self):
        """max_length alone uses default min (1)."""
        schema = {
            "type": "record",
            "name": "T",
            "fields": [
                {
                    "name": "tags",
                    "type": {"type": "array", "items": "string"},
                    "arg.properties": {"max_length": 2},
                },
            ],
        }
        random.seed(42)
        for _ in range(30):
            record = RecordResolver(schema).generate()
            assert 1 <= len(record["tags"]) <= 2

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
