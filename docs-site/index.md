# 📝 avro-datagen

Schema-driven fake data generator for Avro schemas. Reads `.avsc` files
with `arg.properties` hints and produces realistic records -- no code changes
needed for new data shapes.

## Features

- **Web UI** -- browse schemas, edit live, preview data, optionally produce to Kafka
- **Schema-driven** -- define data shape and generation hints in a single `.avsc` file
- **Faker included** -- use any [Faker](https://faker.readthedocs.io/) provider via `arg.properties` out of the box
- **Deterministic** -- seed for fully reproducible output
- **Conditional fields** -- rules engine for field dependencies
- **Multiple outputs** -- Web UI, CLI (JSON lines), Python library, Kafka producer

## Quick start

```bash
# Install with the web UI
pip install "avro-datagen[ui]"

# Launch the UI
avro-datagen ui

# With Kafka producer
avro-datagen ui --kafka

# Or generate from the command line
avro-datagen -s schemas/transaction.avsc -c 5 --pretty

# Or use as a library
python -c "
from avro_datagen import generate
for r in generate('schemas/transaction.avsc', count=3):
    print(r)
"
```

## Architecture

```
src/avro_datagen/
  resolver.py             core engine: walks Avro schema, resolves fields
  generator.py            public API: generate(schema_path, count, seed)
  cli.py                  CLI + UI entry point (generate, ui subcommands)
  producer.py             Kafka producer (confluent-kafka)
  app.py                  Streamlit web UI (bundled in package)
  schemas/                example .avsc files (bundled in package)
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
