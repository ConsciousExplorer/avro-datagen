"""Core generator — loads an Avro schema and yields fake records."""

import random
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from avro_datagen.resolver import RecordResolver, _faker, load_schema

# Fixed epoch used when a seed is provided, so output is fully deterministic.
_FIXED_EPOCH = datetime(2026, 1, 1, tzinfo=UTC).timestamp()


def _to_epoch(now: datetime | float) -> float:
    """Convert a `now` argument to epoch seconds, rejecting naive datetimes."""
    if isinstance(now, datetime):
        if now.utcoffset() is None:
            raise ValueError(
                f"now must be a timezone-aware datetime, got naive {now.isoformat()!r}"
            )
        return now.timestamp()
    return float(now)


def generate(
    schema_path: str | Path,
    count: int,
    seed: int | None = None,
    now: datetime | float | None = None,
) -> Iterator[dict]:
    """Generate `count` fake records from an Avro schema file.

    Args:
        schema_path: Path to a .avsc file.
        count: Number of records to generate. 0 means infinite.
        seed: Optional seed for reproducible output.
        now: Optional clock anchor for relative bounds ("now", "-30d",
            "today", ...) and un-hinted timestamp/date fields. A timezone-aware
            datetime or epoch seconds. Defaults to 2026-01-01T00:00:00Z when
            seeded and the real clock otherwise, so reproducible output is a
            function of the pair (seed, now).

    Yields:
        dict — one record per iteration.
    """
    if seed is not None:
        random.seed(seed)
        _faker.seed_instance(seed)

    schema = load_schema(schema_path)
    resolver = RecordResolver(schema, seed=seed)

    # An explicit anchor wins; otherwise pin the clock when seeded so
    # timestamps are reproducible
    if now is not None:
        resolver.now_ts = _to_epoch(now)
    elif seed is not None:
        resolver.now_ts = _FIXED_EPOCH

    if count == 0:
        while True:
            yield resolver.generate()
    else:
        for _ in range(count):
            yield resolver.generate()
