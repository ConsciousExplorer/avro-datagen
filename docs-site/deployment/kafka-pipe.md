# Piping generated data to Kafka

This approach uses the `avro_datagen` CLI to generate JSON lines and pipes
them into a Kafka console producer. No Python Kafka client needed — just the
CLI and a running Kafka broker.

## Architecture

```
┌──────────────┐   stdout    ┌──────────────────────┐         ┌─────────────┐
│              │   (pipe)    │ kafka-console-        │         │             │
│avro_datagen├────────────>│ producer              ├────────>│ Kafka topic │
│              │  JSON lines │ (runs in container)   │         │             │
└──────────────┘             └──────────────────────┘         └─────────────┘
```

Each JSON line becomes one Kafka message. No serialization overhead — the
consumer deserializes JSON on the other side.

## Quick start with docker-compose

### 1. Start Kafka

```yaml
# docker-compose.yml
services:
  kafka:
    image: confluentinc/cp-kafka:7.9.0
    hostname: kafka
    ports:
      - "9092:9092"
      - "9093:9093"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:29093
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:29093,EXTERNAL://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,EXTERNAL://localhost:9093
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT,EXTERNAL:PLAINTEXT
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      CLUSTER_ID: "txn-aggregator-local"
```

```bash
docker compose up -d kafka
```

### 2. Create the topic

```bash
docker compose exec txn-kafka \
  kafka-topics --create \
    --topic txn.raw \
    --bootstrap-server kafka:9092 \
    --partitions 3 \
    --replication-factor 1
```

### 3. Generate and pipe

**From your host machine** (Kafka exposed on localhost:9093):

```bash
# Generate 100 transactions and produce to Kafka
avro_datagen -s schemas/transaction.avsc -c 100 -r 1 \
  | docker exec -i txn-kafka /opt/kafka/bin/kafka-console-producer.sh \
        --topic txn.raw \
        --bootstrap-server kafka:9092
```

**Infinite mode** (Ctrl+C to stop):

```bash
avro_datagen -s schemas/transaction.avsc -c 0 \
  | docker exec txn-kafka \
      kafka-console-producer \
        --topic txn.raw \
        --bootstrap-server kafka:9092
```

> **Important:** Use `exec -T` (no TTY) so stdin piping works correctly.

### 4. Verify messages landed

```bash
docker compose exec kafka \
  kafka-console-consumer \
    --topic txn.raw \
    --bootstrap-server kafka:9092 \
    --from-beginning \
    --max-messages 5
```

## Rate limiting with pv

The generator currently emits records as fast as it can. To throttle without
code changes, use `pv` (pipe viewer) to limit throughput:

```bash
# ~10 records/second (assuming ~300 bytes per JSON line)
avro_datagen -s schemas/transaction.avsc -c 0 \
  | pv -L 3000 \
  | docker compose exec -T kafka \
      kafka-console-producer \
        --topic txn.raw \
        --bootstrap-server kafka:9092
```

`pv -L 3000` limits the pipe to 3000 bytes/second. Adjust based on your
average record size. This is a rough workaround — a proper `--rate` CLI flag
would give precise control.

Install pv: `brew install pv` (macOS) or `apt install pv` (Linux).

## Using kcat (kafkacat) instead

`kcat` is lighter than the Kafka console producer and easier to pipe into:

```bash
# Install: brew install kcat
avro_datagen -s schemas/transaction.avsc -c 100 \
  | kcat -P -b localhost:9093 -t txn.raw
```

## Seeded data for reproducible testing

```bash
# Always produces the same 50 records
avro_datagen -s schemas/transaction.avsc -c 50 --seed 42 \
  | kcat -P -b localhost:9093 -t txn.raw
```

This is useful for integration tests where you need deterministic data in the
topic.

## Tradeoffs vs. the Python producer app

|                        | Pipe approach                | Python producer app                      |
| ---------------------- | ---------------------------- | ---------------------------------------- |
| **Dependencies**       | None (CLI + Kafka container) | `confluent-kafka`                        |
| **Rate control**       | Rough (`pv`)                 | Precise (`--rate` flag)                  |
| **Error handling**     | None — pipe breaks silently  | Delivery callbacks, retries              |
| **Idempotent produce** | No                           | Yes (`enable.idempotence=true`)          |
| **Headers**            | Not possible                 | Can set `correlationId` in Kafka headers |
| **Best for**           | Quick local testing, demos   | Continuous load simulation, staging      |

For production-like load testing, use the Python producer app approach
described in [kafka-producer-app.md](kafka-producer-app.md). The pipe approach
is ideal for quick local development and verifying the consumer works.
