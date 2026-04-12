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

Regex-like string generation. Supports character classes, shortcuts,
quantifiers, alternation, and escape sequences.

```json
"arg.properties": {
  "pattern": "[A-Z]{3}-[0-9]{4}"
}
```

Produces strings like `ABK-3847`, `QWE-0012`.

### Supported syntax

| Pattern | Generates |
|---------|-----------|
| `[A-Z]`, `[a-z]`, `[0-9]` | Character classes |
| `[^0-9]` | Negated class (any char except digits) |
| `\d`, `\w`, `\s` | Digit, word char, whitespace shortcuts |
| `\D`, `\W`, `\S` | Negated shortcuts |
| `{n}` | Exact repetition |
| `{n,m}` | Variable repetition (n to m) |
| `?` | Optional (0 or 1) |
| `*` | Zero or more (capped at 5) |
| `+` | One or more (capped at 5) |
| `(foo\|bar\|baz)` | Alternation — picks one alternative |
| `\.`, `\(`, `\\` | Escaped literals |
| Literal chars | Used as-is |

### Examples

| Pattern | Example output |
|---------|---------------|
| `[A-Z]{3}-[0-9]{4}` | `ABK-3847` |
| `exist-[A-Z]{3}` | `exist-QWE` |
| `\d{3}-\w{4}` | `847-ab_3` |
| `[a-z]{3,6}` | `foobar` or `xy` or `abcdef` |
| `(foo\|bar)-\d+` | `foo-123`, `bar-4` |
| `user_[a-z]{6}@example\.com` | `user_abcdef@example.com` |

### Not supported

- Anchors (`^`, `$`)
- Lookaheads / lookbehinds
- Backreferences
- Nested groups

Malformed patterns raise a clear `ValueError`. For more complex generation
needs, use the `faker` hint with a provider like `bothify` or `pystr_format`.

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
| `is_null` | `{ "field": "notes", "is_null": true }` | Field value is / is not null |
| `in` | `{ "field": "status", "in": ["active", "pending"] }` | Field value is in the list |

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

## faker

Delegate value generation to a [Faker](https://faker.readthedocs.io/) provider.
See [Faker Integration](faker.md) for full details.

```json
"arg.properties": { "faker": "name" }
```
