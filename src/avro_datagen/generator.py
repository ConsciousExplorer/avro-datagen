"""Core generator — loads an Avro schema and yields fake records."""

import random
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from avro_datagen.resolver import RecordResolver, load_schema

# Fixed epoch used when a seed is provided, so output is fully deterministic.
_FIXED_EPOCH = datetime(2026, 1, 1, tzinfo=UTC).timestamp()


def generate(
    schema_path: str | Path,
    count: int,
    seed: int | None = None,
) -> Iterator[dict]:
    """Generate `count` fake records from an Avro schema file.

    Args:
        schema_path: Path to a .avsc file.
        count: Number of records to generate. 0 means infinite.
        seed: Optional seed for reproducible output.

    Yields:
        dict — one record per iteration.
    """
    if seed is not None:
        random.seed(seed)

    schema = load_schema(schema_path)
    resolver = RecordResolver(schema)

    # Pin the clock when seeded so timestamps are reproducible
    if seed is not None:
        resolver.now_ts = _FIXED_EPOCH

    if count == 0:
        while True:
            yield resolver.generate()
    else:
        for _ in range(count):
            yield resolver.generate()
