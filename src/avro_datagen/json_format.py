"""Post-processing: render wire-form records as human-readable JSON.

The generator emits the Avro *wire* representation of logical types — a
`timestamp-millis` is an int of epoch milliseconds. That is what a
schema-registry serde expects to receive after it encodes, but Kafka UIs with a
produce form (kafbat-ui, for one) want the *human* representation and do the
conversion themselves. Pasting a generated sample into such a form therefore
means hand-converting every timestamp.

`to_human_json()` is a pure post-processing walker over an already-generated
record. It never touches the generator or the producer path, both of which stay
wire-form.

This module deliberately imports nothing from the rest of the package —
`resolver` imports `iso_utc` from here, not the other way round.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def iso_utc(dt: datetime, timespec: str = "auto") -> str:
    """Format a UTC datetime as ISO-8601 with a `Z` suffix."""
    return dt.isoformat(timespec=timespec).replace("+00:00", "Z")


def _from_millis(value: int) -> str:
    return iso_utc(_EPOCH + timedelta(milliseconds=value), "milliseconds")


def _from_micros(value: int) -> str:
    return iso_utc(_EPOCH + timedelta(microseconds=value), "microseconds")


def _from_days(value: int) -> str:
    return (date(1970, 1, 1) + timedelta(days=value)).isoformat()


def _time_from_millis(value: int) -> str:
    return (datetime.min + timedelta(milliseconds=value)).time().isoformat(timespec="milliseconds")


def _time_from_micros(value: int) -> str:
    return (datetime.min + timedelta(microseconds=value)).time().isoformat(timespec="microseconds")


# Integer timedelta arithmetic, not `fromtimestamp(v / 1000)` — float division
# loses the last digit of a microsecond timestamp, which would break the
# human -> wire round trip.
_CONVERTERS = {
    "timestamp-millis": _from_millis,
    "timestamp-micros": _from_micros,
    "date": _from_days,
    "time-millis": _time_from_millis,
    "time-micros": _time_from_micros,
}

# Logical types left untouched: `uuid` and `iso-timestamp` are already strings,
# and `decimal` is generated as a string to preserve precision.


def to_human_json(record: dict, schema: dict) -> dict:
    """Return a copy of `record` with temporal logical types in human form.

    Walks the record alongside its schema, converting `timestamp-millis`,
    `timestamp-micros`, `date`, `time-millis` and `time-micros` to ISO-8601
    strings. Every other value is passed through unchanged.

    Args:
        record: A generated record (wire form).
        schema: The Avro record schema it was generated from.

    Returns:
        A new dict — `record` is not mutated.
    """
    if not isinstance(schema, dict) or schema.get("type") != "record":
        return record
    return _convert_record(record, schema)


def _convert_record(value: Any, schema: dict) -> Any:
    if not isinstance(value, dict):
        return value
    out = dict(value)
    for field in schema.get("fields", []):
        if not isinstance(field, dict):
            continue
        name = field.get("name")
        if name in out:
            out[name] = _convert(out[name], field.get("type"))
    return out


def _convert(value: Any, avro_type: Any) -> Any:
    """Convert one value against its Avro type."""
    if value is None:
        return None

    if isinstance(avro_type, list):
        return _convert_union(value, avro_type)

    if not isinstance(avro_type, dict):
        return value

    converted = _apply_logical(value, avro_type.get("logicalType"))
    if converted is not None:
        return converted

    inner = avro_type.get("type")
    if inner == "record":
        return _convert_record(value, avro_type)
    if inner == "array" and isinstance(value, list):
        items = avro_type.get("items")
        return [_convert(v, items) for v in value]
    if inner == "map" and isinstance(value, dict):
        values = avro_type.get("values")
        return {k: _convert(v, values) for k, v in value.items()}
    return value


def _apply_logical(value: Any, logical: Any) -> Any:
    """Convert `value` for a temporal logical type, or None if not applicable.

    `bool` is a subclass of `int` and must never be treated as an epoch value.
    An out-of-range value is returned as-is rather than raising — a bad number
    should render verbatim, not break the page it appears on.
    """
    converter = _CONVERTERS.get(logical) if isinstance(logical, str) else None
    if converter is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    try:
        return converter(value)
    except (OverflowError, ValueError, OSError):
        return value


def _convert_union(value: Any, branches: list) -> Any:
    """Resolve which union branch a value came from, then convert it.

    Records are plain dicts rather than Avro-encoded union wrappers, so the
    branch has to be inferred. A nullable temporal — `["null", {"type": "long",
    "logicalType": "timestamp-millis"}]` — is the dominant case, so logical
    branches are tried first; structural branches are matched by shape.
    """
    named = [b for b in branches if b != "null"]

    for branch in named:
        if isinstance(branch, dict):
            converted = _apply_logical(value, branch.get("logicalType"))
            if converted is not None:
                return converted

    for branch in named:
        if not isinstance(branch, dict):
            continue
        inner = branch.get("type")
        if inner == "record" and isinstance(value, dict):
            return _convert_record(value, branch)
        if inner == "array" and isinstance(value, list):
            return _convert(value, branch)
        if inner == "map" and isinstance(value, dict):
            return _convert(value, branch)

    return value
