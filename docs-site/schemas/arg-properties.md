# arg.properties Reference

`arg.properties` is an Avro-compliant custom attribute on field objects. It
controls how the generator produces values for that field.

## options

Pick a random element from a list. Duplicates act as weighting.

```json
"arg.properties": {
  "options": ["GROCERIES", "GROCERIES", "TRANSPORT", "DINING"]
}
```

`GROCERIES` appears twice, so it's selected ~50% of the time.

## range

Generate a value within bounds. Works for numeric types and timestamps.

### Numeric

```json
"arg.properties": {
  "range": { "min": 10.0, "max": 500.0 }
}
```

Integer types produce integers; float/double types produce 2-decimal floats.

### Decimal

For fields with `logicalType: decimal`, `range` produces a decimal string that
respects the schema's `scale`:

```json
{
  "name": "price",
  "type": {
    "type": "bytes",
    "logicalType": "decimal",
    "precision": 10,
    "scale": 2
  },
  "arg.properties": { "range": { "min": 10.0, "max": 500.0 } }
}
```

Produces values like `"47.82"`, `"213.05"`, `"499.99"`. The output is a string
because JSON has no native decimal type — consumers should parse with
`Decimal(value)` (Python) or equivalent to preserve precision.

Without a `range` hint, decimals are generated across the full precision/scale
range (e.g. precision=5, scale=2 -> values between `0.00` and `999.99`).

### Timestamps

```json
"arg.properties": {
  "range": { "min": "-30d", "max": "now" }
}
```

Supported offsets:

| Offset | Meaning |
|--------|---------|
| `"now"` | Current timestamp |
| `"-30d"` | 30 days ago |
| `"-2h"` | 2 hours ago |
| `"-15m"` | 15 minutes ago |
| `"-60s"` | 60 seconds ago |
| `1704067200` | Literal epoch seconds |

### Dates

For `date` logical type fields, `range` accepts ISO date strings or relative
day offsets:

```json
{
  "name": "birthDate",
  "type": { "type": "int", "logicalType": "date" },
  "arg.properties": { "range": { "min": "1960-01-01", "max": "2005-12-31" } }
}
```

| Value | Meaning |
|-------|---------|
| `"today"` | Current day |
| `"-30d"` | 30 days ago |
| `"+7d"` | 7 days from today |
| `"2024-01-15"` | Literal ISO date |
| `19723` | Literal days since epoch |

### Times of day

For `time-millis` and `time-micros` logical type fields, `range` accepts
`HH:MM` or `HH:MM:SS` strings:

```json
{
  "name": "shiftStart",
  "type": { "type": "int", "logicalType": "time-millis" },
  "arg.properties": { "range": { "min": "09:00", "max": "17:30" } }
}
```

| Value | Meaning |
|-------|---------|
| `"09:00"` | 9:00:00.000 |
| `"17:30:45"` | 5:30:45 PM |
| `"23:59:59.999"` | One ms before midnight |
| `32400000` | Literal milliseconds after midnight |

## pool

Pre-generate N unique values and reuse them across records. Useful for
foreign-key-like fields (e.g. customer IDs).

```json
{
  "name": "customerId",
  "type": { "type": "string", "logicalType": "uuid" },
  "arg.properties": { "pool": 50 }
}
```

This generates 50 unique UUIDs once, then picks randomly from that set for
every record. Creates realistic cardinality.

## pattern

Regex-like string generation. Supports character classes and repetition.

```json
"arg.properties": {
  "pattern": "[A-Z]{3}-[0-9]{4}"
}
```

Produces strings like `ABK-3847`, `QWE-0012`.

Supported syntax:

| Pattern | Generates |
|---------|-----------|
| `[A-Z]` | One uppercase letter |
| `[a-z]` | One lowercase letter |
| `[0-9]` | One digit |
| `{N}` | Repeat previous class N times |
| Literal chars | Used as-is |

## ref

Copy a value from another field. Supports type conversion.

```json
{
  "name": "createdAt",
  "type": { "type": "string", "logicalType": "iso-timestamp" },
  "arg.properties": { "ref": "timestamp" }
}
```

If `timestamp` is epoch milliseconds and `createdAt` is `iso-timestamp`, the
value is automatically converted.

## template

String interpolation using values from previously resolved fields.

```json
"arg.properties": {
  "template": "Purchase at {merchantName}"
}
```

Uses Python's `str.format()` syntax. Any field declared above is available.

## rules

Conditional generation based on other field values.

```json
"arg.properties": {
  "rules": [
    {
      "when": { "field": "category", "equals": "GROCERIES" },
      "then": { "options": ["Pick n Pay", "Checkers", "Woolworths"] }
    },
    {
      "when": { "field": "category", "equals": "TRANSPORT" },
      "then": { "range": { "min": 15.0, "max": 2500.0 } }
    }
  ]
}
```

### Condition operators

| Operator | Example | Matches when |
|----------|---------|-------------|
| `equals` | `{ "field": "type", "equals": "credit" }` | Field value equals the given value |
| `not_equals` | `{ "field": "type", "not_equals": "credit" }` | Field value does not equal the given value |
| `is_null` | `{ "field": "notes", "is_null": true }` | Field value is / is not null |
| `in` | `{ "field": "status", "in": ["active", "pending"] }` | Field value is in the list |
| `not_in` | `{ "field": "country", "not_in": ["US", "CA"] }` | Field value is not in the list |
| `gt` | `{ "field": "amount", "gt": 1000 }` | Field value is greater than the given value |
| `gte` | `{ "field": "age", "gte": 18 }` | Field value is greater than or equal |
| `lt` | `{ "field": "score", "lt": 50 }` | Field value is less than the given value |
| `lte` | `{ "field": "age", "lte": 17 }` | Field value is less than or equal |
| `matches` | `{ "field": "code", "matches": "^[A-Z]-\\d+$" }` | Field value matches the regex |

### `then` clause

`then` accepts:

- **Any hint** -- `options`, `range`, `ref`, `template`, `faker`, `pattern`
- **`null`** -- produce a null value
- **A literal value** -- used as-is

Rules are evaluated in order. The first matching rule wins. If no rule
matches, the generator falls back to type-based generation.

## null_probability

Control how often a nullable union field produces null. Default is `0.2` (20%).

```json
{
  "name": "notes",
  "type": ["null", "string"],
  "arg.properties": { "null_probability": 0.5 }
}
```

| Value | Meaning |
|-------|---------|
| `0.0` | Never null |
| `0.2` | 20% null (default) |
| `0.5` | 50/50 |
| `1.0` | Always null |

Only applies to union types that include `"null"`. For unions with multiple
non-null branches (e.g. `["null", "string", "int"]`), a non-null branch is
chosen at random when the value is not null.

## length (arrays and maps)

Control the size of generated arrays and maps. Three forms are accepted:

### Flat min/max (preferred)

```json
{
  "name": "tags",
  "type": { "type": "array", "items": "string" },
  "arg.properties": { "min_length": 2, "max_length": 5 }
}
```

Either bound is optional — omitted bounds default to `1` and `5`.

### Nested length dict

```json
"arg.properties": { "length": { "min": 2, "max": 5 } }
```

### Fixed length

```json
"arg.properties": { "length": 3 }
```

Produces arrays with exactly 3 elements every time.

The same hints work for map types.

## faker

Delegate value generation to a [Faker](https://faker.readthedocs.io/) provider.
See [Faker Integration](faker.md) for full details.

```json
"arg.properties": { "faker": "name" }
```
