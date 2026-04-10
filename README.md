# avro-datagen

[![CI](https://github.com/ConsciousExplorer/avro-datagen/actions/workflows/publish.yml/badge.svg)](https://github.com/ConsciousExplorer/avro-datagen/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/avro-datagen)](https://pypi.org/project/avro-datagen/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![Docs](https://img.shields.io/badge/docs-mkdocs-teal)](https://consciousexplorer.github.io/avro-datagen/)

Schema-driven fake data generator for Avro schemas. Reads `.avsc` files with
`arg.properties` hints and produces realistic records -- zero runtime
dependencies (stdlib only).

## Install

```bash
pip install avro-datagen
```

With optional extras:

```bash
pip install avro-datagen[kafka]   # Kafka producer support
pip install avro-datagen[faker]   # Faker-powered generation
pip install avro-datagen[app]     # Streamlit UI + Kafka + Faker
```

## CLI

```bash
# Generate 10 records (JSON lines)
avro-datagen --schema schemas/transaction.avsc

# 1000 records, seeded for reproducibility
avro-datagen -s schemas/transaction.avsc -c 1000 --seed 42

# Pretty-print 5 records
avro-datagen -s schemas/transaction.avsc -c 5 --pretty
```

## Library

```python
from avro_datagen import generate

for record in generate("schemas/transaction.avsc", count=100):
    print(record)

# Deterministic output
records = list(generate("schemas/transaction.avsc", count=10, seed=42))
```

## Development

```bash
git clone https://github.com/ConsciousExplorer/avro-datagen.git
cd avro-datagen
```

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv sync --all-extras

make test       # run tests
make app        # streamlit UI
make docs       # mkdocs dev server
```

With pip:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip3 install -e ".[dev,faker]"
make test
```

## Documentation

Full documentation: [consciousexplorer.github.io/avro-datagen](https://consciousexplorer.github.io/avro-datagen/)

## License

MIT
