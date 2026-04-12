# How It Works

avro-datagen reads an Avro `.avsc` schema and generates realistic fake records.
This page explains exactly what happens for each field.

## The big picture

```
.avsc file
    |
    v
load_schema()          parse JSON
    |
    v
RecordResolver(schema) index named types, init pools
    |
    v
resolver.generate()    for each field, top to bottom:
    |                    resolve_field(field, record_so_far)
    v
{ record dict }        one complete record
```

Fields are resolved **in declaration order**. This matters because later fields
can reference earlier ones via `ref`, `template`, and `rules`.

## Field resolution priority

For each field, the resolver checks these in order. **First match wins.**

```
_resolve_field(field)
    |
    +-- 1. rules?        evaluate conditions, first match wins
    |
    +-- 2. ref?          copy from another field (with type conversion)
    |
    +-- 3. hints?        arg.properties (see sub-order below)
    |
    +-- 4. default?      Avro default value
    |
    +-- 5. type          generate from Avro type / logicalType
```

### Hint sub-order (priority 3)

When `arg.properties` is present but doesn't contain `rules` or `ref`:

| Order | Hint | What it does |
|-------|------|-------------|
| 3a | `ref` | Copy from another field |
| 3b | `template` | String interpolation: `"Purchase at {merchantName}"` |
| 3c | `faker` | Faker provider: `"name"`, `"email"`, `{"method": "bothify", "args": ["##-??"]}` |
| 3d | `options` | Random choice from list (duplicates = weighting) |
| 3e | `pool` | Pick from N pre-generated unique values |
| 3f | `range` | Numeric or timestamp bounds |
| 3g | `pattern` | Regex-like: `"[A-Z]{3}-[0-9]{4}"` |

## Type resolution

When no hints match, the resolver generates based on the Avro type:

```
_resolve_type(avro_type)
    |
    +-- union list?     ["null", "string"]
    |     null_probability (default 0.2), then pick a non-null branch
    |
    +-- complex dict?
    |     +-- record    recursive (new resolver, shared pools)
    |     +-- array     length hint or default 1-5
    |     +-- map       key_0, key_1, ...
    |     +-- enum      random choice from symbols
    |     +-- fixed     random bytes (hex)
    |     +-- logical   uuid, timestamp-millis, etc.
    |     +-- primitive string, int, long, etc.
    |
    +-- primitive str?  generate default value for type
```

## Walkthrough: Transaction schema

Given this schema (simplified):

```json
{
  "fields": [
    { "name": "correlationId", "type": {"logicalType": "uuid"} },
    { "name": "customerId",    "type": {"logicalType": "uuid"}, "arg.properties": {"pool": 50} },
    { "name": "category",      "arg.properties": {"options": ["GROCERIES", "TRANSPORT"]} },
    { "name": "merchantName",  "arg.properties": {"rules": [
        {"when": {"field": "category", "equals": "GROCERIES"}, "then": {"options": ["Pick n Pay"]}}
    ]}},
    { "name": "amount",        "arg.properties": {"rules": [
        {"when": {"field": "category", "equals": "GROCERIES"}, "then": {"range": {"min": 35, "max": 4500}}}
    ]}},
    { "name": "description",   "arg.properties": {"template": "Purchase at {merchantName}"} },
    { "name": "timestamp",     "type": {"logicalType": "timestamp-millis"}, "arg.properties": {"range": {"min": "-30d", "max": "now"}} },
    { "name": "createdAt",     "type": {"logicalType": "iso-timestamp"}, "arg.properties": {"ref": "timestamp"} }
  ]
}
```

Here's how each field resolves:

| # | Field | Path taken | Result |
|---|-------|-----------|--------|
| 1 | `correlationId` | no hints, no default -> type -> logicalType `uuid` | `"a1b2c3d4-..."` |
| 2 | `customerId` | hint: `pool: 50` -> generate 50 UUIDs once, pick one | `"f8e7d6c5-..."` |
| 3 | `category` | hint: `options` -> random choice | `"GROCERIES"` |
| 4 | `merchantName` | `rules` -> check `category == "GROCERIES"` -> match -> `options` | `"Pick n Pay"` |
| 5 | `amount` | `rules` -> check `category == "GROCERIES"` -> match -> `range` | `1247.50` |
| 6 | `description` | hint: `template` -> interpolate `{merchantName}` from record | `"Purchase at Pick n Pay"` |
| 7 | `timestamp` | hint: `range` with time offsets -> random epoch ms in last 30 days | `1744123456000` |
| 8 | `createdAt` | `ref: "timestamp"` -> copy + convert epoch ms to ISO string | `"2025-04-08T..."` |

Notice how fields 4-6 depend on fields 3 and earlier. This is why declaration
order matters.

## Shared state

These are shared across all records in a single `generate()` run:

| State | Purpose | Scope |
|-------|---------|-------|
| **Pools** | Pre-generated unique values (e.g. 50 customer IDs) | Shared with nested records |
| **Named types** | Index of record types for nested resolution | Shared with nested records |
| **now_ts** | Timestamp reference (current time or fixed epoch) | Shared with nested records |
| **Locale Fakers** | Cached per-locale Faker instances | Per resolver |

## Nested records

When a field's type is a record:

1. A new `RecordResolver` is created for the nested schema
2. It shares `pools`, `named_types`, and `now_ts` with the parent
3. The nested record's fields are resolved independently
4. The result is a nested dict in the parent record

## Seed behaviour

| With seed | Without seed |
|-----------|-------------|
| `random.seed(seed)` — all randomness controlled | Random each run |
| `_faker.seed_instance(seed)` — Faker output controlled | Faker random each run |
| `now_ts` pinned to 2026-01-01 | `now_ts` = current time |
| Fully deterministic output | Different every time |
