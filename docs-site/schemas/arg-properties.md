# arg.properties Reference

`arg.properties` is an Avro-compliant custom attribute on field objects. It
controls how the generator produces values for that field.

!!! tip "Check your hints"
    The generator ignores keys it does not recognise, so a typo produces
    plausible-looking but wrong data rather than an error. Run
    `avro-datagen validate -s schema.avsc` to have unknown keys, misplaced
    keys, unknown Faker methods, malformed `range` bounds and unencodable
    `options` reported with their field paths. Add `--strict` to fail on them.

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
every record. Creates realistic cardinality. Each field gets its own pool,
and the per-record pick is driven by the process RNG, so `--seed` output
stays reproducible.

### Object form: `size`, `per`, `seed`

`pool` also accepts an object for correlated and cross-process-stable pools:

```json
{
  "name": "accountId",
  "type": { "type": "string", "logicalType": "uuid" },
  "arg.properties": { "pool": { "size": 3, "per": "customerId" } }
}
```

| Key | Meaning |
|-----|---------|
| `size` | Number of members in the pool (required) |
| `per` | Keep one pool per distinct value of this field -- each record picks from the pool belonging to its own `per` value |
| `seed` | Universe identity string -- pool members become a pure function of this string |

### Keyed pools (`per`)

With `per`, a given customer always draws from the *same small set* of
accounts, so parent/child fields stay correlated. Membership is a pure
function of the key (seeded by the field name unless `seed` is given), so
the same customer maps to the same accounts in every process -- even across
producers running with different `--seed` values, with zero coordination.

`per` must reference a field declared *before* the pooled field (the same
declaration-order constraint as `ref` and `rules`).

### Seeded pools (`seed`)

Without `seed`, pool members come from the process RNG, so differently
seeded producers generate disjoint universes. With `seed`, members are
derived only from the seed string (plus the `per` key where applicable) --
never from the process RNG, field order, or creation timing:

```json
{
  "name": "customerId",
  "type": { "type": "string", "logicalType": "uuid" },
  "arg.properties": { "pool": { "size": 50, "seed": "customers-v1" } }
},
{
  "name": "accountId",
  "type": { "type": "string", "logicalType": "uuid" },
  "arg.properties": { "pool": { "size": 3, "per": "customerId", "seed": "accounts-v1" } }
}
```

Any schema, any producer, any process seed: the same seed string yields the
identical universe. Because the seed string (not the field name) is the
universe identity, `customerId` in one schema and `userId` in another can
share a universe by pointing at the same string. Rotate the string
(`"customers-v2"`) to version the universe deliberately.

!!! tip "Cross-source referential consistency"
    Give every source schema the same seeded parent pool and the same keyed
    child pool, and independently seeded producers emit the same customers
    with the same accounts -- full referential consistency with no shared
    state and no fixture files. The per-record *choice* still follows the
    process RNG, so `--seed` reproducibility is preserved.

### Caveats

- **Temporal members are clock-anchored.** `timestamp-*` and `iso-timestamp`
  pool members are derived from the run's pinned "now" (all members
  identical), and `date` members are anchored to the current day. The
  cross-process membership guarantee therefore covers `uuid`, times,
  decimals, and primitives; for date/timestamp pools it only holds between
  runs that pin the clock the same way (the CLI does this when `--seed` is
  given).
- **One pool is cached per distinct `per` value.** Keep `per` pointed at a
  bounded-cardinality field (itself pooled, `options`, etc.) -- keying on a
  high-cardinality field grows memory without ever reusing a pool.
- **A null `per` value is a key like any other.** If the `per` field is a
  nullable union, all records where it resolves to null share one pool.

`pool` and `foreign_key` are mutually exclusive on a field -- both claim the
whole value, and combining them raises an error.

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

## foreign_key

Pick a value from another schema's output file. Useful for generating
related records across multiple runs -- e.g. orders that reference real
customer IDs from a previously generated customers file.

```json
{
  "name": "customerId",
  "type": {"type": "string", "logicalType": "uuid"},
  "arg.properties": {
    "foreign_key": {
      "file": "customers.jsonl",
      "field": "customerId"
    }
  }
}
```

### Workflow

```bash
# 1. Generate customers and save to file
avro-datagen -s customers.avsc -c 100 > customers.jsonl

# 2. Generate orders that reference those customers
avro-datagen -s orders.avsc -c 1000 > orders.jsonl
```

Every order's `customerId` field will be a real value drawn from the
`customers.jsonl` file. The file is loaded once (lazily on first use) and
cached on the resolver.

### File formats

Both **JSON Lines** (one record per line) and **JSON arrays** are supported:

```
{"customerId": "cust-1", "name": "Alice"}
{"customerId": "cust-2", "name": "Bob"}
```

```json
[
  {"customerId": "cust-1", "name": "Alice"},
  {"customerId": "cust-2", "name": "Bob"}
]
```

### Errors

- Missing file: raises `FileNotFoundError` with the offending path
- Missing `file` or `field` key: raises `ValueError`
- File has no records with the named field: raises `ValueError`

!!! tip "Reproducibility"
    `foreign_key` works with `--seed` -- which value gets picked is
    deterministic, but the source file must exist at generation time.

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
