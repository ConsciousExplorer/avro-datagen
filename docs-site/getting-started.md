# Getting Started

## Installation

=== "pip"

    ```bash
    pip install avro-datagen
    ```

=== "With Kafka producer"

    ```bash
    pip install avro-datagen[kafka]
    ```

=== "With Streamlit UI"

    ```bash
    pip install avro-datagen[app]
    ```

=== "With Faker support"

    ```bash
    pip install avro-datagen[faker]
    ```

## Development setup

=== "uv (recommended)"

    ```bash
    git clone https://github.com/ConsciousExplorer/avro-datagen.git
    cd avro-datagen
    uv sync --all-extras
    ```

=== "pip"

    ```bash
    git clone https://github.com/ConsciousExplorer/avro-datagen.git
    cd avro-datagen
    python3 -m venv .venv && source .venv/bin/activate
    pip install -e ".[app,dev,faker]"
    ```

## CLI usage

```bash
# Generate 10 transactions (default)
avro-datagen --schema schemas/transaction.avsc

# Set count, seed, and pretty-print
avro-datagen -s schemas/transaction.avsc -c 5 --seed 42 --pretty

# Rate-limited output
avro-datagen -s schemas/transaction.avsc -c 1000 --rate 50

# Infinite mode (Ctrl+C to stop)
avro-datagen -s schemas/transaction.avsc -c 0

# Pipe to Kafka
avro-datagen -s schemas/transaction.avsc -c 1000 \
  | kafka-console-producer --topic txn.raw --bootstrap-server localhost:29092
```

### CLI flags

| Flag       | Short | Default   | Description                       |
| ---------- | ----- | --------- | --------------------------------- |
| `--schema` | `-s`  | required  | Path to `.avsc` file              |
| `--count`  | `-c`  | `10`      | Number of records. `0` = infinite |
| `--seed`   |       | random    | Seed for reproducible output      |
| `--rate`   | `-r`  | unlimited | Records per second                |
| `--pretty` | `-p`  | off       | Pretty-print JSON                 |

## Library usage

```python
from avro_datagen import generate

# Basic iteration
for record in generate("schemas/transaction.avsc", count=100):
    print(record)

# Seeded, deterministic
records = list(generate("schemas/transaction.avsc", count=10, seed=42))

# Infinite generator
for record in generate("schemas/transaction.avsc", count=0):
    process(record)
```

## Seed behaviour

When a seed is provided:

- `random.seed()` controls all randomness
- Timestamps pin to a fixed epoch (`2026-01-01T00:00:00Z`)
- Output is fully deterministic across runs

Without a seed, timestamps use the current time and all values are random.

## Tests

```bash
make test
# or
uv run pytest -v
# or
pytest -v
```
