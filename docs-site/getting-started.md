# Getting Started

## Installation

=== "pip"

    ```bash
    pip install avro-datagen             # CLI + library + Faker
    ```

=== "With Streamlit UI"

    ```bash
    pip install "avro-datagen[ui]"       # + web UI
    ```

=== "With everything (UI + Kafka)"

    ```bash
    pip install "avro-datagen[app]"      # + UI + Kafka producer
    ```

## Web UI

The quickest way to explore schemas and generate data:

```bash
pip install "avro-datagen[ui]"
avro-datagen ui
```

Opens a Streamlit dashboard at `localhost:8501` where you can:

- Browse and select local `.avsc` schemas
- Upload schemas
- Edit schemas live with instant sample preview
- Generate data with streaming output

```bash
avro-datagen ui --port 3000                    # custom port
avro-datagen ui --schema-dir ./my-schemas      # custom schema directory
avro-datagen ui --kafka                        # enable Kafka producer section
```

The UI uses bundled example schemas by default. Point `--schema-dir` at your
own schemas to use them instead.

### Kafka mode (interactive testing only)

By default the UI focuses on schema editing and data generation -- no Kafka
dependency required. The `--kafka` flag enables a built-in producer for quick
interactive testing against a broker. For production pipelines, pipe the CLI
output to `kcat`, `kafka-console-producer`, or your preferred ingestion tool.

```bash
pip install "avro-datagen[app]"    # includes confluent-kafka
avro-datagen ui --kafka
```

## CLI usage

```bash
# Generate 10 transactions (default)
avro-datagen -s schemas/transaction.avsc

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

### Subcommands

| Command | Description |
|---------|-------------|
| `avro-datagen generate` | Generate data to stdout (default) |
| `avro-datagen ui` | Launch the Streamlit web UI |

Flags without a subcommand are treated as `generate` for backward
compatibility:

```bash
# These are equivalent
avro-datagen -s schema.avsc -c 10
avro-datagen generate -s schema.avsc -c 10
```

### Generate flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--schema` | `-s` | required | Path to `.avsc` file |
| `--count` | `-c` | `10` | Number of records. `0` = infinite |
| `--seed` | | random | Seed for reproducible output |
| `--rate` | `-r` | unlimited | Records per second |
| `--pretty` | `-p` | off | Pretty-print JSON |

### UI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `8501` | Port to run the UI on |
| `--schema-dir` | bundled schemas | Directory containing `.avsc` files |
| `--kafka` | off | Enable Kafka sidebar and producer section |

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
    pip install -e ".[dev,app,faker]"
    ```

```bash
make test         # run tests
make lint         # ruff check
make format       # ruff format
make typecheck    # pyright
make check        # all of the above
make app          # streamlit UI (dev mode)
make docs         # mkdocs dev server
```
