# Avro Schema-Driven Data Generation

## TL;DR

Avro's specification explicitly permits custom attributes on fields — they are
preserved by parsers but ignored by serializers. You can use standard logical
types (`uuid`, `timestamp-millis`, `decimal`) for type-aware generation and
namespaced custom properties (e.g. `arg.properties`) for generation hints like
ranges, option lists, and pools. This makes the `.avsc` file a single source of
truth for both the data contract and realistic fake data generation.

## Decision layers

| Layer | Approach | Best for | Weakness |
|-------|----------|----------|----------|
| Avro logical types | `logicalType` on the type object | Standard types: UUID, timestamps, decimals | Limited set — only 10 built-in types |
| Custom field properties | Extra JSON keys on the field object | Generation hints: ranges, enums, pools | No standard — you define the convention |
| External overlay file | Separate `.hints.json` per schema | Clean separation of contract vs generation | Two files to maintain, can drift |
| Code-defined schemas | Python/Java classes with Faker logic | Maximum flexibility | Schema and contract are separate definitions |

## Avro standard logical types

These are part of the Avro 1.11.1 specification and understood by all compliant
parsers and serializers.

| Logical type | Underlying type | Extra attributes | Generator maps to |
|---|---|---|---|
| `uuid` | `string` | — | `fake.uuid4()` |
| `date` | `int` | — | days since epoch |
| `time-millis` | `int` | — | ms after midnight |
| `time-micros` | `long` | — | μs after midnight |
| `timestamp-millis` | `long` | — | ms since epoch UTC |
| `timestamp-micros` | `long` | — | μs since epoch UTC |
| `local-timestamp-millis` | `long` | — | ms, no timezone |
| `local-timestamp-micros` | `long` | — | μs, no timezone |
| `decimal` | `bytes` or `fixed` | `precision` (req), `scale` (opt, default 0) | `fake.pydecimal()` |
| `duration` | `fixed` (12 bytes) | — | 3 unsigned ints: months, days, ms |

### Syntax

Logical types are set on the **type object**, not on the field:

```json
{
  "name": "correlationId",
  "type": {"type": "string", "logicalType": "uuid"}
}
```

```json
{
  "name": "timestamp",
  "type": {"type": "long", "logicalType": "timestamp-millis"}
}
```

```json
{
  "name": "amount",
  "type": {"type": "bytes", "logicalType": "decimal", "precision": 18, "scale": 4}
}
```

## Custom field properties for generation hints

### What the spec says

> "Attributes not defined in this document are permitted as metadata, but must
> not affect the format of serialized data."

> Extension attributes "MUST be made accessible by Apache Avro implementations
> for reading and writing."

Custom properties are **spec-compliant**, **preserved by parsers**, and
**ignored by serializers**. They do not break any Avro tooling.

### Naming convention

The spec recommends prefixing user-defined attributes to avoid collisions with
future Avro spec additions. Common conventions:

| Convention | Example | Used by |
|---|---|---|
| `org_attr` | `myorg_range` | Avro spec recommendation |
| `x-attr` | `x-faker` | OpenAPI extension convention |
| `arg.properties` | `arg.properties: {range: ...}` | Confluent ksql-datagen, Kafka Connect datagen |

**Recommendation for this project:** Use `arg.properties` — it's the convention
established by Confluent's own data generation tooling, which is directly
relevant to our Kafka-based stack.

### Syntax

Custom properties go on the **field object** (sibling to `name` and `type`):

```json
{
  "name": "amount",
  "type": "double",
  "arg.properties": {
    "range": {"min": 15.0, "max": 15000.0}
  }
}
```

```json
{
  "name": "merchantName",
  "type": "string",
  "arg.properties": {
    "options": ["Pick n Pay", "Checkers", "Spar", "Woolworths Food"]
  }
}
```

```json
{
  "name": "transactionType",
  "type": "string",
  "arg.properties": {
    "options": ["debit", "debit", "debit", "debit", "credit"]
  }
}
```

```json
{
  "name": "customerId",
  "type": {"type": "string", "logicalType": "uuid"},
  "arg.properties": {
    "pool": 50
  }
}
```

### `arg.properties` vocabulary

| Key | Value type | Meaning |
|-----|-----------|---------|
| `options` | `any[]` | Pick a random element (duplicates = weighting) |
| `range` | `{min, max}` | Numeric or timestamp range |
| `pool` | `int` | Pre-generate N unique values, reuse across records |
| `pattern` | `string` | Regex-like string generation |
| `faker` | `string \| dict` | Faker provider — string for simple, dict for `{method, args, kwargs, locale}` |
| `ref` | `string` | Copy value from another field (with type conversion) |
| `template` | `string` | String interpolation using `{fieldName}` syntax |
| `rules` | `list` | Conditional generation based on other field values |
| `null_probability` | `float` | Null frequency for union types (default 0.2) |

## Complete schema example

```json
{
  "type": "record",
  "name": "Transaction",
  "namespace": "txn.raw.v1",
  "fields": [
    {
      "name": "correlationId",
      "type": {"type": "string", "logicalType": "uuid"}
    },
    {
      "name": "sourceId",
      "type": "string",
      "arg.properties": {
        "options": ["bank-api", "card-processor", "mobile-app"]
      }
    },
    {
      "name": "customerId",
      "type": {"type": "string", "logicalType": "uuid"},
      "arg.properties": {"pool": 50}
    },
    {
      "name": "amount",
      "type": {"type": "bytes", "logicalType": "decimal", "precision": 18, "scale": 2},
      "arg.properties": {"range": {"min": 15.0, "max": 15000.0}}
    },
    {
      "name": "currency",
      "type": "string",
      "default": "ZAR"
    },
    {
      "name": "merchantName",
      "type": "string",
      "arg.properties": {
        "options": ["Pick n Pay", "Checkers", "Woolworths Food", "Spar"]
      }
    },
    {
      "name": "mccCode",
      "type": "string",
      "arg.properties": {
        "options": ["5411", "5422", "5812", "5813", "4011"]
      }
    },
    {
      "name": "transactionType",
      "type": "string",
      "arg.properties": {
        "options": ["debit", "debit", "debit", "debit", "credit"]
      }
    },
    {
      "name": "timestamp",
      "type": {"type": "long", "logicalType": "timestamp-millis"},
      "arg.properties": {
        "range": {"min": "-30d", "max": "now"}
      }
    }
  ]
}
```

## Industry best practice

Confluent's `kafka-connect-datagen` and `ksql-datagen` both use exactly this
pattern — Avro schemas with `arg.properties` to drive data generation. This is
the de facto standard in the Kafka ecosystem for schema-driven fake data.

The alternative (code-defined schemas with a registry pattern) is common in
unit testing libraries (e.g. factory_boy, Hypothesis) but creates a second
source of truth for the data shape. In a Kafka system where the Avro schema
is already the canonical contract, deriving generation from that same file
eliminates drift.

## Recommendation for this project

- Use `.avsc` files with standard logical types + `arg.properties` for hints
- The generator reads the `.avsc`, resolves each field's type and hints, and
  calls the appropriate Faker method
- The same `.avsc` file is used by the Kafka producer for Avro serialization
  and by the consumer for deserialization — one contract, three uses
- For correlated fields (merchant ↔ MCC ↔ amount range), use a `"groups"`
  property at the record level that links fields into co-generated sets
- Python library: load `.avsc` as JSON (`json.load`), no need for fastavro
  just to parse the schema — it's just JSON. Use fastavro only for
  serialization when producing to Kafka.

## References

- [Apache Avro 1.11.1 Specification](https://avro.apache.org/docs/1.11.1/specification/)
- [Confluent ksql-datagen](https://docs.confluent.io/platform/current/ksqldb/tutorials/generate-custom-test-data.html)
- [fastavro documentation](https://fastavro.readthedocs.io/en/latest/)
- [Formal Avro Schema Spec (Gist)](https://gist.github.com/clemensv/498c481965c425b218ee156b38b49333)
