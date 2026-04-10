# Streamlit UI

A web interface for selecting schemas, editing them, previewing generated data,
and producing directly to Kafka.

## Setup

```bash
cp .env.sample .env        # edit with your Kafka connection details
pip install avro-datagen[app]
```

## Run

```bash
streamlit run app.py
# or with make
make app
```

## Features

### Schema tabs

| Tab | Description |
|-----|-------------|
| **Local schemas** | Pick from `.avsc` files in `schemas/`. Collapsible JSON view + sample record |
| **Upload** | Drop any `.avsc` or `.json` file. Collapsible JSON view + sample record |
| **Editor** | Full JSON editor. Live sample record updates as you type. Save to file or download |

### Generate (streaming)

- Set record count, rate limit, and seed
- Records stream into the table one by one
- Live metrics: count, generation rate (rec/s), elapsed time

### Kafka Produce

- Configure connection, auth, and tuning via the sidebar
- Real-time progress with Produce / Stop controls
- Live metrics: sent, errors, elapsed

## Sidebar settings

All sidebar fields can be pre-filled via environment variables:

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

## Schema editor

The editor tab lets you modify the full schema JSON. When the JSON is valid:

- A sample record is rendered below
- **Save to file** writes back to the original `.avsc` (or `schemas/` for new schemas)
- **Download** exports as a `.avsc` file
- **Reset** reverts to the originally loaded schema

The edited schema is used by both Generate and Kafka Produce sections.
