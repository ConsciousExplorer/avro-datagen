"""Kafka producer — generates records from an Avro schema and publishes to a topic."""

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from confluent_kafka import KafkaException, Producer

from avro_datagen.generator import generate


def _default_key(record: dict[str, Any]) -> str | None:
    """Extract a partition key from the record, if available."""
    for candidate in ("correlationId", "id", "key"):
        if candidate in record:
            return str(record[candidate])
    return None


def build_producer_config(
    bootstrap_servers: str,
    security_protocol: str = "",
    sasl_mechanism: str = "",
    sasl_username: str = "",
    sasl_password: str = "",
    acks: str = "all",
    linger_ms: int = 5,
    batch_size: int = 16384,
    compression_type: str = "snappy",
) -> dict[str, str | int]:
    """Build a confluent-kafka producer config dict from explicit params."""
    config: dict[str, str | int] = {
        "bootstrap.servers": bootstrap_servers,
        "acks": acks,
        "linger.ms": linger_ms,
        "batch.size": batch_size,
        "compression.type": compression_type,
    }

    if security_protocol:
        config["security.protocol"] = security_protocol
    if sasl_mechanism:
        config["sasl.mechanism"] = sasl_mechanism
    if sasl_username:
        config["sasl.username"] = sasl_username
    if sasl_password:
        config["sasl.password"] = sasl_password

    return config


def produce(
    schema_path: str | Path,
    topic: str,
    producer_config: dict[str, str | int],
    count: int = 10,
    rate: float | None = None,
    seed: int | None = None,
    key_fn: Callable[[dict[str, Any]], str | None] | None = None,
    on_delivery: Callable[[Any, Any], None] | None = None,
    on_progress: Callable[[int, dict[str, Any]], None] | None = None,
) -> dict[str, int | float]:
    """Generate records and publish them to a Kafka topic.

    Args:
        schema_path: Path to the .avsc schema file.
        topic: Kafka topic to publish to.
        producer_config: confluent-kafka Producer config dict.
        count: Number of records (0 = infinite).
        rate: Records per second limit. None = unlimited.
        seed: Random seed for reproducibility.
        key_fn: Callable to extract a message key from the record.
        on_delivery: Per-message delivery callback (err, msg).
        on_progress: Called after each record with (index, record).

    Returns:
        dict with produced, errors, elapsed_s keys.
    """
    if key_fn is None:
        key_fn = _default_key

    producer = Producer(producer_config)
    interval = 1.0 / rate if rate else 0.0

    produced = 0
    errors = 0
    start_time = time.monotonic()

    def _delivery_cb(err, msg):
        nonlocal errors
        if err is not None:
            errors += 1
        if on_delivery:
            on_delivery(err, msg)

    try:
        for i, record in enumerate(generate(schema_path, count, seed)):
            tick = time.monotonic()

            value = json.dumps(record).encode("utf-8")
            key = key_fn(record)
            key_bytes = key.encode("utf-8") if key else None

            try:
                producer.produce(
                    topic=topic,
                    value=value,
                    key=key_bytes,
                    callback=_delivery_cb,
                )
                produced += 1
            except BufferError:
                producer.flush(timeout=5)
                producer.produce(
                    topic=topic,
                    value=value,
                    key=key_bytes,
                    callback=_delivery_cb,
                )
                produced += 1
            except KafkaException:
                errors += 1

            producer.poll(0)

            if on_progress:
                on_progress(i, record)

            if interval:
                elapsed = time.monotonic() - tick
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    except KeyboardInterrupt:
        pass
    finally:
        producer.flush(timeout=30)

    return {
        "produced": produced,
        "errors": errors,
        "elapsed_s": round(time.monotonic() - start_time, 2),
    }
