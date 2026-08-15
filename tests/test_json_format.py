"""Tests for the human-readable JSON post-processing walker."""

from datetime import UTC, datetime

from avro_datagen.json_format import to_human_json


def _schema(*fields):
    return {"type": "record", "name": "T", "fields": list(fields)}


def _field(name, avro_type):
    return {"name": name, "type": avro_type}


TS_MILLIS = {"type": "long", "logicalType": "timestamp-millis"}
TS_MICROS = {"type": "long", "logicalType": "timestamp-micros"}
DATE = {"type": "int", "logicalType": "date"}
TIME_MILLIS = {"type": "int", "logicalType": "time-millis"}
TIME_MICROS = {"type": "long", "logicalType": "time-micros"}


class TestTemporalConversion:
    def test_timestamp_millis_matches_issue_example(self):
        """The exact value and rendering named in issue #16."""
        schema = _schema(_field("timestamp", TS_MILLIS))
        result = to_human_json({"timestamp": 1785691423392}, schema)
        assert result["timestamp"] == "2026-08-02T17:23:43.392Z"

    def test_timestamp_micros(self):
        schema = _schema(_field("ts", TS_MICROS))
        result = to_human_json({"ts": 1785691423392392}, schema)
        assert result["ts"] == "2026-08-02T17:23:43.392392Z"

    def test_date_renders_as_iso_date(self):
        schema = _schema(_field("d", DATE))
        assert to_human_json({"d": 20500}, schema)["d"] == "2026-02-16"
        assert to_human_json({"d": 0}, schema)["d"] == "1970-01-01"

    def test_time_millis(self):
        schema = _schema(_field("t", TIME_MILLIS))
        assert to_human_json({"t": 45296789}, schema)["t"] == "12:34:56.789"

    def test_time_micros(self):
        schema = _schema(_field("t", TIME_MICROS))
        assert to_human_json({"t": 45296789123}, schema)["t"] == "12:34:56.789123"


class TestRoundTrip:
    def test_millis_round_trips_exactly(self):
        schema = _schema(_field("ts", TS_MILLIS))
        for wire in (0, 1, 1785691423392, 1_000_000_000_000):
            human = to_human_json({"ts": wire}, schema)["ts"]
            parsed = datetime.fromisoformat(human.replace("Z", "+00:00"))
            assert round(parsed.timestamp() * 1000) == wire

    def test_micros_round_trips_exactly(self):
        """Float division would lose the last digit here — integer math must not."""
        schema = _schema(_field("ts", TS_MICROS))
        for wire in (1785691423392392, 1785691423999999, 1):
            human = to_human_json({"ts": wire}, schema)["ts"]
            parsed = datetime.fromisoformat(human.replace("Z", "+00:00"))
            delta = parsed - datetime(1970, 1, 1, tzinfo=UTC)
            assert delta // (delta.resolution) == wire


class TestPassThrough:
    def test_non_temporal_logical_types_unchanged(self):
        schema = _schema(
            _field("id", {"type": "string", "logicalType": "uuid"}),
            _field("amount", {"type": "bytes", "logicalType": "decimal", "precision": 10}),
            _field("when", {"type": "string", "logicalType": "iso-timestamp"}),
        )
        record = {
            "id": "0d5a1f2e-1111-4222-8333-444455556666",
            "amount": "123.45",
            "when": "2026-01-01T00:00:00Z",
        }
        assert to_human_json(record, schema) == record

    def test_primitives_unchanged(self):
        schema = _schema(
            _field("s", "string"),
            _field("i", "int"),
            _field("f", "double"),
            _field("n", "null"),
        )
        record = {"s": "x", "i": 7, "f": 1.5, "n": None}
        assert to_human_json(record, schema) == record

    def test_boolean_is_not_treated_as_epoch(self):
        """bool subclasses int — it must never hit a temporal converter."""
        schema = _schema(_field("flag", {"type": "boolean", "logicalType": "date"}))
        assert to_human_json({"flag": True}, schema)["flag"] is True

    def test_out_of_range_value_passes_through(self):
        schema = _schema(_field("ts", TS_MILLIS))
        huge = 10**25
        assert to_human_json({"ts": huge}, schema)["ts"] == huge

    def test_record_is_not_mutated(self):
        schema = _schema(_field("ts", TS_MILLIS))
        record = {"ts": 1785691423392}
        to_human_json(record, schema)
        assert record["ts"] == 1785691423392

    def test_field_absent_from_record_is_ignored(self):
        schema = _schema(_field("ts", TS_MILLIS), _field("missing", DATE))
        assert to_human_json({"ts": 0}, schema) == {"ts": "1970-01-01T00:00:00.000Z"}

    def test_non_record_schema_returns_input(self):
        record = {"a": 1}
        assert to_human_json(record, {"type": "string"}) is record


class TestUnions:
    def test_nullable_temporal_converts(self):
        schema = _schema(_field("ts", ["null", TS_MILLIS]))
        assert to_human_json({"ts": 1785691423392}, schema)["ts"] == "2026-08-02T17:23:43.392Z"

    def test_null_stays_null(self):
        schema = _schema(_field("ts", ["null", TS_MILLIS]))
        assert to_human_json({"ts": None}, schema)["ts"] is None

    def test_non_temporal_union_unchanged(self):
        schema = _schema(_field("v", ["null", "string"]))
        assert to_human_json({"v": "hello"}, schema)["v"] == "hello"

    def test_nullable_record_branch_recurses(self):
        inner = {
            "type": "record",
            "name": "Inner",
            "fields": [_field("ts", TS_MILLIS)],
        }
        schema = _schema(_field("nested", ["null", inner]))
        result = to_human_json({"nested": {"ts": 0}}, schema)
        assert result["nested"]["ts"] == "1970-01-01T00:00:00.000Z"


class TestNestedStructures:
    def test_nested_record(self):
        inner = {
            "type": "record",
            "name": "Inner",
            "fields": [_field("ts", TS_MILLIS), _field("name", "string")],
        }
        schema = _schema(_field("inner", inner))
        result = to_human_json({"inner": {"ts": 0, "name": "x"}}, schema)
        assert result["inner"] == {"ts": "1970-01-01T00:00:00.000Z", "name": "x"}

    def test_array_of_timestamps(self):
        schema = _schema(_field("stamps", {"type": "array", "items": TS_MILLIS}))
        result = to_human_json({"stamps": [0, 1000]}, schema)
        assert result["stamps"] == ["1970-01-01T00:00:00.000Z", "1970-01-01T00:00:01.000Z"]

    def test_array_of_records(self):
        inner = {"type": "record", "name": "I", "fields": [_field("d", DATE)]}
        schema = _schema(_field("items", {"type": "array", "items": inner}))
        result = to_human_json({"items": [{"d": 0}, {"d": 1}]}, schema)
        assert result["items"] == [{"d": "1970-01-01"}, {"d": "1970-01-02"}]

    def test_map_of_timestamps(self):
        schema = _schema(_field("m", {"type": "map", "values": TS_MILLIS}))
        result = to_human_json({"m": {"a": 0}}, schema)
        assert result["m"] == {"a": "1970-01-01T00:00:00.000Z"}


class TestGeneratedRecords:
    def test_round_trip_over_a_generated_record(self):
        """End-to-end: generate wire form, humanize, parse back."""
        from pathlib import Path

        from avro_datagen.generator import generate
        from avro_datagen.resolver import load_schema

        path = Path(__file__).resolve().parent / "fixtures" / "transaction.avsc"
        schema = load_schema(path)
        record = next(iter(generate(str(path), count=1, seed=42)))
        human = to_human_json(record, schema)

        checked = 0
        for field in schema["fields"]:
            logical = field["type"].get("logicalType") if isinstance(field["type"], dict) else None
            if logical == "timestamp-millis":
                parsed = datetime.fromisoformat(human[field["name"]].replace("Z", "+00:00"))
                assert round(parsed.timestamp() * 1000) == record[field["name"]]
                checked += 1
        assert checked, "fixture has no timestamp-millis field — test would be vacuous"
