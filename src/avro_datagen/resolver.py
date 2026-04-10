"""Field resolver — maps Avro types + arg.properties to generated values.

This is the core engine. It walks an Avro schema top-to-bottom, resolving each
field's value based on its type, logical type, and arg.properties hints. Fields
are resolved in declaration order so that later fields can reference earlier ones
via `ref` and `rules`.
"""

import json
import random
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from faker import Faker

# Avro type can be a primitive string ("string", "int"), a complex dict
# ({"type": "string", "logicalType": "uuid"}), or a union list (["null", "string"]).
type AvroType = str | dict[str, Any] | list[Any]

_faker = Faker()


def load_schema(path: str | Path) -> dict:
    """Load an .avsc file and return the parsed JSON."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class RecordResolver:
    """Resolves a single Avro record schema into generated dicts.

    Maintains pools (for `pool` hints) across multiple generate() calls so that
    pooled values are reused across records.
    """

    def __init__(self, schema: dict[str, Any]):
        self.schema = schema
        self.fields: list[dict[str, Any]] = schema["fields"]
        # Pools: field_name -> list of pre-generated values
        self.pools: dict[str, list[Any]] = {}
        # Capture "now" once so timestamps are reproducible with a seed
        self.now_ts: float = datetime.now(UTC).timestamp()
        # Named record types encountered during resolution (for recursive records)
        self.named_types: dict[str, dict[str, Any]] = {}
        self._indexnamed_types(schema)

    def _indexnamed_types(self, schema: dict) -> None:
        """Walk the schema and index all named record types for reference."""
        if isinstance(schema, dict) and schema.get("type") == "record":
            name = schema.get("name", "")
            if name:
                self.named_types[name] = schema
            for field in schema.get("fields", []):
                self._indexnamed_types(field.get("type", {}))
        elif isinstance(schema, dict) and schema.get("type") == "array":
            self._indexnamed_types(schema.get("items", {}))
        elif isinstance(schema, list):
            for branch in schema:
                self._indexnamed_types(branch)

    def generate(self) -> dict:
        """Generate one record. Fields resolved top-to-bottom."""
        record: dict[str, Any] = {}
        for field in self.fields:
            name = field["name"]
            record[name] = self._resolve_field(field, record)
        return record

    def _resolve_field(self, field: dict, record: dict) -> Any:
        """Resolve a single field's value."""
        props = field.get("arg.properties", {})
        avro_type = field["type"]

        # --- Priority 1: conditional rules ---
        if "rules" in props:
            return self._resolve_rules(props["rules"], avro_type, record)

        # --- Priority 2: ref (copy from another field) ---
        if "ref" in props:
            return self._resolve_ref(props["ref"], avro_type, record)

        # --- Priority 3: arg.properties hints ---
        if props:
            return self._resolve_with_hints(avro_type, props, record)

        # --- Priority 4: default value ---
        if "default" in field:
            return field["default"]

        # --- Priority 5: type-based generation ---
        return self._resolve_type(avro_type, {}, record)

    def _resolve_rules(self, rules: list[dict], avro_type: AvroType, record: dict) -> Any:
        """Evaluate conditional rules against the current record."""
        for rule in rules:
            condition = rule["when"]
            if self._evaluate_condition(condition, record):
                then = rule["then"]
                if then is None:
                    return None
                if isinstance(then, dict):
                    # `then` contains arg.properties-style hints
                    return self._resolve_with_hints(avro_type, then, record)
                # Literal value
                return then
        # No rule matched — fall back to type-based generation
        return self._resolve_type(avro_type, {}, record)

    def _evaluate_condition(self, condition: dict, record: dict) -> bool:
        """Evaluate a single condition against the current record."""
        field_name = condition["field"]
        field_value = record.get(field_name)

        if "equals" in condition:
            return field_value == condition["equals"]
        if "is_null" in condition:
            if condition["is_null"]:
                return field_value is None
            return field_value is not None
        if "in" in condition:
            return field_value in condition["in"]
        return False

    def _resolve_ref(self, ref_name: str, avro_type: AvroType, record: dict) -> Any:
        """Copy a value from another field, with type conversion if needed."""
        source_value = record.get(ref_name)
        if source_value is None:
            return None

        # Handle type conversion: e.g. epoch millis -> ISO string
        target_logical = self._get_logical_type(avro_type)
        if target_logical == "iso-timestamp" and isinstance(source_value, int):
            dt = datetime.fromtimestamp(source_value / 1000, tz=UTC)
            return dt.isoformat().replace("+00:00", "Z")

        return source_value

    def _resolve_faker(self, spec: str | dict) -> Any:
        """Call a Faker provider method.

        spec can be:
          - a string:  "name", "email", "address", "credit_card_number", ...
          - a dict:    {"method": "bothify", "args": ["###-???"]}
                       {"method": "random_int", "kwargs": {"min": 1, "max": 100}}
                       {"method": "name", "locale": "ja_JP"}
        """
        if isinstance(spec, str):
            method_name = spec
            args = []
            kwargs = {}
            locale = None
        else:
            method_name = spec["method"]
            args = spec.get("args", [])
            kwargs = spec.get("kwargs", {})
            locale = spec.get("locale")

        provider = Faker(locale) if locale else _faker

        method = getattr(provider, method_name, None)
        if method is None:
            raise ValueError(f"Unknown Faker method: {method_name!r}")

        return method(*args, **kwargs)

    def _resolve_with_hints(self, avro_type: AvroType, props: dict, record: dict) -> Any:
        """Resolve a field using arg.properties hints."""

        # ref: copy from another field (with type conversion)
        if "ref" in props:
            return self._resolve_ref(props["ref"], avro_type, record)

        # template: string interpolation from other fields
        if "template" in props:
            return props["template"].format(**record)

        # faker: delegate to a Faker provider method
        if "faker" in props:
            return self._resolve_faker(props["faker"])

        # options: pick a random element
        if "options" in props:
            return random.choice(props["options"])

        # pool: pick from a pre-generated pool of unique values
        if "pool" in props:
            return self._resolve_pool(avro_type, props)

        # range: generate within bounds
        if "range" in props:
            return self._resolve_range(avro_type, props["range"])

        # pattern: regex-based string generation
        if "pattern" in props:
            return self._resolve_pattern(props["pattern"])

        # length hint for arrays is handled in _resolve_type
        return self._resolve_type(avro_type, props, record)

    def _resolve_pool(self, avro_type: AvroType, props: dict) -> Any:
        """Return a value from a pre-generated pool, creating it if needed."""
        # Use a stable key based on the logical type
        logical = self._get_logical_type(avro_type) or "string"
        pool_size = props["pool"]
        pool_key = f"{logical}:{pool_size}"

        if pool_key not in self.pools:
            self.pools[pool_key] = [self._generate_for_logical(logical) for _ in range(pool_size)]
        return random.choice(self.pools[pool_key])

    def _resolve_range(self, avro_type: AvroType, range_spec: dict) -> Any:
        """Generate a value within a range."""
        logical = self._get_logical_type(avro_type)

        # Timestamp range: supports relative strings like "-30d", "now"
        if logical in ("timestamp-millis", "timestamp-micros", "iso-timestamp"):
            start = self._parse_time_offset(range_spec["min"])
            end = self._parse_time_offset(range_spec["max"])
            ts = start + random.random() * (end - start)
            epoch_ms = int(ts * 1000)
            if logical == "iso-timestamp":
                return datetime.fromtimestamp(ts, tz=UTC).isoformat().replace("+00:00", "Z")
            if logical == "timestamp-micros":
                return int(ts * 1_000_000)
            return epoch_ms

        # Numeric range
        low = range_spec["min"]
        high = range_spec["max"]
        base_type = self._get_base_type(avro_type)
        if base_type in ("int", "long"):
            return random.randint(int(low), int(high))
        return round(random.uniform(low, high), 2)

    def _resolve_pattern(self, pattern: str) -> str:
        """Generate a string from a simple regex-like pattern.

        Supports: [A-Z], [a-z], [0-9], {n} repetition, and literal chars.
        Not a full regex engine — covers common data generation patterns.
        """
        result = []
        i = 0
        while i < len(pattern):
            if pattern[i] == "[":
                # Character class
                end = pattern.index("]", i)
                char_class = pattern[i + 1 : end]
                i = end + 1
                # Check for repetition {n}
                count = 1
                if i < len(pattern) and pattern[i] == "{":
                    rep_end = pattern.index("}", i)
                    count = int(pattern[i + 1 : rep_end])
                    i = rep_end + 1
                chars = self._expand_char_class(char_class)
                for _ in range(count):
                    result.append(random.choice(chars))
            else:
                result.append(pattern[i])
                i += 1
        return "".join(result)

    def _expand_char_class(self, char_class: str) -> list[str]:
        """Expand a character class like 'A-Z' or '0-9' to a list of chars."""
        chars = []
        i = 0
        while i < len(char_class):
            if i + 2 < len(char_class) and char_class[i + 1] == "-":
                start = ord(char_class[i])
                end = ord(char_class[i + 2])
                chars.extend(chr(c) for c in range(start, end + 1))
                i += 3
            else:
                chars.append(char_class[i])
                i += 1
        return chars

    def _resolve_type(self, avro_type: AvroType, props: dict, record: dict) -> Any:
        """Generate a value based purely on the Avro type."""

        # Union type: ["null", "string"] etc.
        if isinstance(avro_type, list):
            return self._resolve_union(avro_type, props, record)

        # Complex type object: {"type": "string", "logicalType": "uuid"}
        if isinstance(avro_type, dict):
            inner_type = avro_type.get("type")
            logical = avro_type.get("logicalType")

            if inner_type == "record":
                return self._resolve_record(avro_type)
            if inner_type == "array":
                return self._resolve_array(avro_type, props, record)
            if inner_type == "map":
                return self._resolve_map(avro_type, props, record)
            if inner_type == "enum":
                return random.choice(avro_type["symbols"])
            if logical:
                return self._generate_for_logical(logical)
            # Fixed type
            if inner_type == "fixed":
                size = avro_type.get("size", 1)
                return random.randbytes(size).hex()
            # Fall through to primitive
            if isinstance(inner_type, str):
                return self._generate_primitive(inner_type)
            return None

        # Primitive type string: "string", "int", "long", etc.
        if isinstance(avro_type, str):
            return self._generate_primitive(avro_type)

        return None

    def _resolve_union(self, branches: list, props: dict, record: dict) -> Any:
        """Resolve a union type. If no hints, pick a non-null branch 80% of the time."""
        non_null = [b for b in branches if b != "null"]
        has_null = "null" in branches

        if has_null and non_null:
            # 20% chance of null by default
            if random.random() < 0.2:
                return None
            return self._resolve_type(non_null[0], props, record)

        return self._resolve_type(random.choice(branches), props, record)

    def _resolve_record(self, schema: dict) -> dict:
        """Recursively resolve a nested record type."""
        nested = RecordResolver(schema)
        # Share state with the parent so pooled IDs and timestamps stay consistent
        nested.pools = self.pools
        nested.named_types = self.named_types
        nested.now_ts = self.now_ts
        return nested.generate()

    def _resolve_array(self, schema: dict, props: dict, record: dict) -> list:
        """Resolve an array type."""
        items_type = schema["items"]
        length_spec = props.get("length", {"min": 1, "max": 5})
        length = random.randint(length_spec["min"], length_spec["max"])

        items_props = props.get("items", {})
        result = []
        for _ in range(length):
            if items_props:
                result.append(self._resolve_with_hints(items_type, items_props, record))
            else:
                result.append(self._resolve_type(items_type, {}, record))
        return result

    def _resolve_map(self, schema: dict, props: dict, record: dict) -> dict:
        """Resolve a map type."""
        values_type = schema["values"]
        length_spec = props.get("length", {"min": 1, "max": 5})
        length = random.randint(length_spec["min"], length_spec["max"])

        result = {}
        for i in range(length):
            key = f"key_{i}"
            result[key] = self._resolve_type(values_type, {}, record)
        return result

    def _generate_for_logical(self, logical: str) -> Any:
        """Generate a value for a known logical type."""
        if logical == "uuid":
            # Use random module so uuid generation is seed-controlled
            return (
                f"{random.getrandbits(32):08x}-{random.getrandbits(16):04x}-"
                f"{0x4000 | random.getrandbits(12):04x}-"
                f"{0x8000 | random.getrandbits(14):04x}-"
                f"{random.getrandbits(48):012x}"
            )
        if logical == "timestamp-millis":
            return int(self.now_ts * 1000)
        if logical == "timestamp-micros":
            return int(self.now_ts * 1_000_000)
        if logical == "iso-timestamp":
            return datetime.fromtimestamp(self.now_ts, tz=UTC).isoformat().replace("+00:00", "Z")
        if logical == "date":
            return random.randint(0, 20000)
        if logical in ("time-millis", "time-micros"):
            return random.randint(0, 86_400_000)
        # Unknown logical type — fall back to nothing useful
        return None

    def _generate_primitive(self, type_name: str) -> Any:
        """Generate a value for a primitive Avro type."""
        if type_name == "null":
            return None
        if type_name == "boolean":
            return random.choice([True, False])
        if type_name == "int":
            return random.randint(0, 10000)
        if type_name == "long":
            return random.randint(0, 1_000_000)
        if type_name == "float" or type_name == "double":
            return round(random.uniform(0, 10000), 2)
        if type_name == "string":
            return f"{random.getrandbits(48):012x}"
        if type_name == "bytes":
            return random.randbytes(16).hex()
        return None

    def _get_logical_type(self, avro_type: AvroType) -> str | None:
        """Extract the logicalType from a type object, if present."""
        if isinstance(avro_type, dict):
            return avro_type.get("logicalType")
        if isinstance(avro_type, list):
            for branch in avro_type:
                if isinstance(branch, dict) and "logicalType" in branch:
                    return branch["logicalType"]
        return None

    def _get_base_type(self, avro_type: AvroType) -> str | None:
        """Extract the base primitive type name."""
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

    def _parse_time_offset(self, value: str | int | float) -> float:
        """Parse a time offset string like '-30d', 'now', or a numeric epoch."""
        if isinstance(value, (int, float)):
            return float(value)
        if value == "now":
            return self.now_ts
        # Parse relative offsets: -30d, -2h, -15m
        match = re.match(r"^(-?\d+)([dhms])$", value)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            delta = {"d": 86400, "h": 3600, "m": 60, "s": 1}[unit]
            return self.now_ts + amount * delta
        raise ValueError(f"Unrecognized time offset: {value!r}")
