# Writing Schemas

Schemas are standard Avro `.avsc` files. The generator reads the schema and
produces records by resolving each field in declaration order.

## Minimal schema

```json
{
  "type": "record",
  "name": "Event",
  "fields": [
    { "name": "id", "type": { "type": "string", "logicalType": "uuid" } },
    { "name": "name", "type": "string" },
    { "name": "count", "type": "int" }
  ]
}
```

Without any hints, the generator uses type-based fallbacks:

| Avro type | Generated value |
|-----------|----------------|
| `string` | Random hex string |
| `int` | Random 0--10,000 |
| `long` | Random 0--1,000,000 |
| `double` / `float` | Random 0--10,000 (2 decimal places) |
| `boolean` | Random true/false |
| `null` | `null` |

## Logical types

Avro logical types produce semantically meaningful values:

| Logical type | Avro base | Generated value |
|-------------|-----------|----------------|
| `uuid` | `string` | RFC 4122 UUID |
| `timestamp-millis` | `long` | Epoch milliseconds |
| `timestamp-micros` | `long` | Epoch microseconds |
| `iso-timestamp` | `string` | ISO 8601 string |
| `date` | `int` | Days since epoch (random date in last ~5 years) |
| `time-millis` | `int` | Milliseconds after midnight |
| `time-micros` | `long` | Microseconds after midnight |

All time-based types support `range` hints -- see the
[arg.properties reference](arg-properties.md#range) for date and time-of-day
ranges.

```json
{
  "name": "createdAt",
  "type": { "type": "string", "logicalType": "iso-timestamp" }
}
```

## Field resolution order

Fields resolve **top-to-bottom** in declaration order. A field can reference
any field declared above it via `ref`, `template`, or `rules`.

```json
{
  "fields": [
    { "name": "category", "type": "string", "arg.properties": { "options": ["A", "B"] } },
    { "name": "label", "type": "string", "arg.properties": { "template": "Category: {category}" } }
  ]
}
```

`label` can reference `category` because `category` is declared first.

## Resolution priority

For each field, the resolver checks (in order):

1. **`rules`** in `arg.properties` -- conditional logic (first matching rule wins)
2. **`ref`** in `arg.properties` -- copy from another field (with type conversion)
3. **`arg.properties` hints** -- checked in this order: `template`, `faker`, `options`, `pool`, `range`, `pattern`
4. **`default`** -- Avro default value
5. **Type fallback** -- generate from Avro type / logicalType

The first match wins.

## Union types (nullable fields)

```json
{ "name": "notes", "type": ["null", "string"] }
```

For nullable unions, the generator produces `null` ~20% of the time by default.
Use `null_probability` in `arg.properties` to control this:

```json
{ "name": "notes", "type": ["null", "string"], "arg.properties": { "null_probability": 0.5 } }
```

For unions with multiple non-null branches (e.g. `["null", "string", "int"]`),
a non-null branch is chosen at random.

## Nested records

Records can contain other records:

```json
{
  "name": "address",
  "type": {
    "type": "record",
    "name": "Address",
    "fields": [
      { "name": "street", "type": "string" },
      { "name": "city", "type": "string" }
    ]
  }
}
```

## Arrays

```json
{
  "name": "tags",
  "type": { "type": "array", "items": "string" },
  "arg.properties": {
    "length": { "min": 1, "max": 3 },
    "items": { "options": ["urgent", "review", "flagged"] }
  }
}
```
