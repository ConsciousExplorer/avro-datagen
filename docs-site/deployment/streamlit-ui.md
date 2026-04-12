# Streamlit UI

A web interface for selecting schemas, editing them, previewing generated data,
and producing directly to Kafka.

## Quick start

```bash
pip install "avro-datagen[ui]"
avro-datagen ui
```

Opens at `http://localhost:8501`. No clone needed -- the app, example schema,
and theme are bundled in the pip package.

## Options

```bash
avro-datagen ui                              # default port 8501
avro-datagen ui --port 3000                  # custom port
avro-datagen ui --schema-dir ./my-schemas    # use your own schemas
avro-datagen ui --kafka                      # enable Kafka producer section
```

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `8501` | Port to run the UI on |
| `--schema-dir` | bundled schemas | Directory containing `.avsc` files |
| `--kafka` | off | Enable Kafka sidebar and producer section |

### With Kafka

By default the UI has no Kafka dependency. To enable the Kafka connection
sidebar and produce section:

```bash
pip install "avro-datagen[app]"    # includes confluent-kafka
avro-datagen ui --kafka
```

### Schema resolution

The UI looks for schemas in this order:

1. `--schema-dir` flag (if provided)
2. `SCHEMA_DIR` environment variable (if set)
3. `./schemas/` in the current directory (if it exists)
4. Bundled example schemas from the package

## Features

### Schema tabs

| Tab | Description |
|-----|-------------|
| **Local schemas** | Pick from `.avsc` files. Collapsible JSON view + sample record |
| **Upload** | Drop any `.avsc` or `.json` file. Collapsible JSON view + sample record |
| **Editor** | Full JSON editor. Live sample record updates as you type. Save to file or download |

### Generate

- Set record count and seed
- Records generated in one batch, displayed as a table
- Metrics: count, generation rate (rec/s), elapsed time
- Expandable "How fields are resolved" section explains the resolution path for each field

### Kafka Produce

- Configure connection, auth, and tuning via the sidebar
- Real-time progress with Produce / Stop controls
- Live metrics: sent, errors, elapsed

## Environment variables

All sidebar fields can be pre-filled via environment variables or a `.env` file:

| Field | Environment variable | Default |
|-------|---------------------|---------|
| Bootstrap servers | `KAFKA_BOOTSTRAP_SERVERS` | `localhost:29092` |
| Topic | `KAFKA_TOPIC` | `transactions` |
| Security protocol | `KAFKA_SECURITY_PROTOCOL` | (none) |
| SASL mechanism | `KAFKA_SASL_MECHANISM` | (none) |
| Username | `KAFKA_SASL_USERNAME` | (none) |
| Password | `KAFKA_SASL_PASSWORD` | (none) |
| Linger (ms) | `KAFKA_LINGER_MS` | `5` |
| Batch size | `KAFKA_BATCH_SIZE` | `16384` |
| Schema directory | `SCHEMA_DIR` | (bundled) |

## Schema editor

The editor tab lets you modify the full schema JSON. When the JSON is valid:

- A sample record is rendered below
- **Save to file** writes back to the original `.avsc` (or `schemas/` for new schemas)
- **Download** exports as a `.avsc` file
- **Reset** reverts to the originally loaded schema

The edited schema is used by both Generate and Kafka Produce sections.
