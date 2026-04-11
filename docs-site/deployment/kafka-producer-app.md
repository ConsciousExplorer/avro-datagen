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

CMD ["uv", "run", "python", "-m", "avro_datagen.produce"]
```

> **Note:** The `produce` command does not exist yet. It will be a new module
> that uses `confluent-kafka` to produce generated records to a Kafka topic.
> The `confluent-kafka` dependency is already declared as an optional extra.

## What the produce command would do

```python
# Pseudocode — not yet implemented
from confluent_kafka import Producer
from avro_datagen import generate

producer = Producer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"]})
topic = os.environ["KAFKA_TOPIC"]

for record in generate(schema_path, count=0):
    producer.produce(topic, json.dumps(record).encode())
    producer.poll(0)
    time.sleep(1 / rate)  # throttle to target rate
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
