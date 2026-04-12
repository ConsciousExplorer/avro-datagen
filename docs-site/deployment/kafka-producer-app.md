# Producing to Kafka

avro-datagen is a **data generator**, not a Kafka connector. The recommended
approach for production pipelines is to pipe CLI output to a dedicated Kafka
producer tool like `kcat` or `kafka-console-producer` (see
[kafka-pipe.md](kafka-pipe.md)).

This page covers two alternatives: a custom Python producer app using the
`avro_datagen` library, and the built-in Streamlit UI producer for interactive
testing.

## Prerequisites

- Docker with a running Kafka broker (see docker-compose example below)
- The `kafka` optional extra installed: `pip install avro-datagen[kafka]`

## Architecture

```
┌──────────────────────┐         ┌──────────────────┐
│   avro_datagen     │         │                  │
│                      │         │   Kafka broker   │
│  schema ──> records ─┼── produce ──>  txn.raw.v1  │
│       (Python app)   │         │                  │
└──────────────────────┘         └──────────────────┘
```

The producer app:
1. Loads the Avro schema at startup
2. Generates records using the `avro_datagen` library
3. Serializes each record as JSON and produces it to the configured Kafka topic
4. Runs continuously (count=0) or until a target count is reached

## docker-compose setup

```yaml
services:
  kafka:
    image: confluentinc/cp-kafka:7.9.0
    hostname: kafka
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:29093
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:29093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      CLUSTER_ID: "txn-aggregator-local"

  producer:
    build:
      context: .
      dockerfile: Dockerfile
    depends_on:
      - kafka
    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
      KAFKA_TOPIC: txn.raw.v1
      SCHEMA_PATH: /app/schemas/transaction.avsc
      RECORD_COUNT: "0"        # 0 = infinite
      RATE: "10"               # records per second (requires --rate flag, see note below)
```

## Dockerfile

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY schemas/ schemas/

RUN pip install uv && uv sync --extra kafka --no-dev --frozen

CMD ["uv", "run", "python", "-c", "from avro_datagen.producer import produce; produce(...)"]
```

> **Note:** There is no standalone `produce` CLI command. The producer module
> (`avro_datagen.producer`) exists and is used by the Streamlit UI, but for
> containerised deployments you would write a small Python entrypoint script
> or use the pipe approach with `kcat`.

## Using the producer module programmatically

```python
from avro_datagen.producer import build_producer_config, produce

config = build_producer_config(
    bootstrap_servers="kafka:9092",
    acks="all",
    compression_type="snappy",
)

result = produce(
    schema_path="schemas/transaction.avsc",
    topic="txn.raw.v1",
    producer_config=config,
    count=1000,
    rate=10,
)
print(f"Produced {result['produced']}, errors: {result['errors']}")
```

## Streamlit UI producer (interactive testing)

The Streamlit UI includes a built-in Kafka producer for quick interactive
testing. This is a convenience for validating schemas against a broker, not a
production integration.

```bash
pip install "avro-datagen[app]"
avro-datagen ui --kafka
```

The UI provides:
- Sidebar configuration for bootstrap servers, topic, security protocol, SASL credentials, and producer tuning
- A **Produce to Kafka** button with live metrics (sent, errors, elapsed time)
- A **Stop** button to cancel a running produce
- Color-coded result banners: green for success, red for errors (e.g. topic not found, connection refused), yellow for partial failures

## Recommended approach for production

For production or CI pipelines, use the CLI with a dedicated Kafka tool:

```bash
avro-datagen -s schema.avsc -c 10000 --rate 100 \
  | kcat -b broker:9092 -t my-topic
```

This keeps avro-datagen focused on generation and delegates delivery to
purpose-built tools with their own retry, batching, and error handling.
