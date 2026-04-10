# avro-datagen

Schema-driven fake data generator for Kafka topics. Reads Avro `.avsc` schemas
with `arg.properties` hints and produces realistic records -- no code changes
needed for new data shapes.

## Features

- **Schema-driven** -- define data shape and generation hints in a single `.avsc` file
- **Zero runtime dependencies** -- stdlib `random`, `json`, `uuid`, `datetime` only
- **Deterministic** -- seed for fully reproducible output
- **Faker integration** -- use any [Faker](https://faker.readthedocs.io/) provider via `arg.properties`
- **Conditional fields** -- rules engine for field dependencies
- **Multiple outputs** -- CLI (JSON lines), Python library, Kafka producer, Streamlit UI

## Quick start

```bash
# Install
pip install avro-datagen

# Generate 10 transactions
avro-datagen --schema schemas/transaction.avsc

# Pretty-print 5 seeded records
avro-datagen -s schemas/transaction.avsc -c 5 --seed 42 --pretty

# As a library
python -c "
from avro_datagen import generate
for r in generate('schemas/transaction.avsc', count=3):
    print(r)
"
```

## Architecture

```
schemas/                  .avsc files (the only thing you edit for new data shapes)
src/avro_datagen/
  resolver.py             core engine: walks Avro schema, resolves fields
  generator.py            public API: generate(schema_path, count, seed)
  cli.py                  CLI entry point
  producer.py             Kafka producer (confluent-kafka)
```

## How it works

The `RecordResolver` walks fields top-to-bottom. For each field, it checks
(in priority order):

1. **`rules`** -- conditional logic evaluated against earlier fields
2. **`ref`** -- copy value from another field (with type conversion)
3. **`faker`** -- delegate to a Faker provider method
4. **`arg.properties`** hints -- `options`, `range`, `pool`, `pattern`, `template`
5. **`default`** -- Avro default value
6. **Type fallback** -- generate from Avro type / logicalType
