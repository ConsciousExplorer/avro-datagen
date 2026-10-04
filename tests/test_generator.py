"""Tests for the core generate function."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from avro_datagen.generator import generate

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TXN_SCHEMA = FIXTURES_DIR / "transaction.avsc"
FAKER_SCHEMA = FIXTURES_DIR / "faker_fields.avsc"

# 2026-10-04T00:00:00Z, written out by hand so the expectations below do not
# depend on the code under test.
NOW = datetime(2026, 10, 4, tzinfo=UTC)
NOW_S = 1_791_072_000
NOW_MS = 1_791_072_000_000
NOW_DAYS = 20_730
THIRTY_DAYS_MS = 30 * 86_400 * 1000


class TestGenerate:
    def test_returns_correct_count(self):
        records = list(generate(TXN_SCHEMA, count=5))
        assert len(records) == 5

    def test_returns_zero_for_infinite_mode(self):
        """count=0 means infinite — take a few and stop."""
        gen = generate(TXN_SCHEMA, count=0)
        records = [next(gen) for _ in range(3)]
        assert len(records) == 3

    def test_seed_produces_reproducible_output(self):
        first = list(generate(TXN_SCHEMA, count=5, seed=123))
        second = list(generate(TXN_SCHEMA, count=5, seed=123))
        assert first == second

    def test_different_seeds_produce_different_output(self):
        first = list(generate(TXN_SCHEMA, count=5, seed=1))
        second = list(generate(TXN_SCHEMA, count=5, seed=2))
        assert first != second

    def test_invalid_schema_path_raises(self):
        with pytest.raises(FileNotFoundError):
            list(generate("/nonexistent/schema.avsc", count=1))

    def test_each_record_is_a_dict(self):
        for record in generate(TXN_SCHEMA, count=3):
            assert isinstance(record, dict)


class TestSeedReproducibility:
    """Verify that seeded generation is fully deterministic, including Faker fields."""

    def test_faker_fields_reproducible(self):
        """Faker-backed fields (name, email) must be identical across seeded runs."""
        first = list(generate(FAKER_SCHEMA, count=10, seed=99))
        second = list(generate(FAKER_SCHEMA, count=10, seed=99))
        assert first == second

    def test_faker_fields_differ_without_seed(self):
        """Without a seed, Faker fields should vary between runs."""
        first = list(generate(FAKER_SCHEMA, count=20))
        second = list(generate(FAKER_SCHEMA, count=20))
        # Extremely unlikely (but not impossible) for 20 names + emails to collide
        assert first != second

    def test_uuid_fields_reproducible(self):
        """UUID logicalType fields must be identical across seeded runs."""
        first = [r["userId"] for r in generate(FAKER_SCHEMA, count=10, seed=7)]
        second = [r["userId"] for r in generate(FAKER_SCHEMA, count=10, seed=7)]
        assert first == second

    def test_full_schema_field_level_reproducibility(self):
        """Every field in the transaction schema is identical across seeded runs."""
        first = list(generate(TXN_SCHEMA, count=20, seed=55))
        second = list(generate(TXN_SCHEMA, count=20, seed=55))
        for i, (a, b) in enumerate(zip(first, second, strict=True)):
            for key in a:
                assert a[key] == b[key], f"Record {i}, field {key!r}: {a[key]!r} != {b[key]!r}"


class TestTransactionSchema:
    """Integration tests: the transaction.avsc produces valid, correlated data."""

    @pytest.fixture
    def records(self):
        return list(generate(TXN_SCHEMA, count=100, seed=42))

    def test_all_fields_present(self, records):
        expected = {
            "correlationId",
            "sourceId",
            "customerId",
            "category",
            "merchantName",
            "mccCode",
            "amount",
            "currency",
            "transactionType",
            "description",
            "refundReason",
            "timestamp",
            "createdAt",
            "updatedAt",
        }
        for record in records:
            assert set(record.keys()) == expected

    def test_correlation_id_is_uuid(self, records):
        import uuid

        for record in records:
            uuid.UUID(record["correlationId"])

    def test_customer_pool_limited(self, records):
        unique_customers = {r["customerId"] for r in records}
        # Pool of 50, so at most 50 unique customers
        assert len(unique_customers) <= 50

    def test_currency_is_default(self, records):
        for record in records:
            assert record["currency"] == "ZAR"

    def test_amount_within_category_range(self, records):
        ranges = {
            "GROCERIES": (35.0, 4500.0),
            "TRANSPORT": (15.0, 2500.0),
            "DINING": (25.0, 1200.0),
            "UTILITIES": (50.0, 5000.0),
            "ENTERTAINMENT": (29.0, 1500.0),
            "HEALTHCARE": (80.0, 15000.0),
            "RETAIL": (20.0, 8000.0),
        }
        for record in records:
            low, high = ranges[record["category"]]
            assert low <= record["amount"] <= high, (
                f"Amount {record['amount']} out of range for {record['category']}"
            )

    def test_description_matches_transaction_type(self, records):
        for record in records:
            merchant = record["merchantName"]
            if record["transactionType"] == "credit":
                assert record["description"] == f"Refund from {merchant}"
            else:
                assert record["description"] == f"Purchase at {merchant}"

    def test_refund_reason_null_for_debits(self, records):
        for record in records:
            if record["transactionType"] == "debit":
                assert record["refundReason"] is None

    def test_refund_reason_present_for_credits(self, records):
        credits = [r for r in records if r["transactionType"] == "credit"]
        assert len(credits) > 0, "Expected some credit transactions"
        for record in credits:
            assert record["refundReason"] is not None

    def test_created_at_matches_timestamp(self, records):
        from datetime import datetime

        for record in records:
            dt = datetime.fromisoformat(record["createdAt"])
            epoch_from_iso = int(dt.timestamp() * 1000)
            assert abs(epoch_from_iso - record["timestamp"]) < 1000

    def test_timestamp_within_range(self, records):
        """Seeded data uses a fixed epoch (2026-01-01), timestamps are within 30 days of it."""
        from avro_datagen.generator import _FIXED_EPOCH

        anchor_ms = int(_FIXED_EPOCH * 1000)
        thirty_days_ms = 30 * 86400 * 1000
        for record in records:
            assert anchor_ms - thirty_days_ms <= record["timestamp"] <= anchor_ms + 1000


def _write_schema(tmp_path: Path, fields: list[dict]) -> Path:
    path = tmp_path / "schema.avsc"
    path.write_text(json.dumps({"type": "record", "name": "R", "fields": fields}))
    return path


class TestNowAnchor:
    """An explicit `now` anchors every relative bound, seeded or not."""

    def test_seeded_timestamps_follow_now(self):
        for record in generate(TXN_SCHEMA, count=200, seed=1, now=NOW):
            assert NOW_MS - THIRTY_DAYS_MS <= record["timestamp"] <= NOW_MS

    def test_epoch_seconds_are_accepted(self):
        for record in generate(TXN_SCHEMA, count=200, seed=1, now=float(NOW_S)):
            assert NOW_MS - THIRTY_DAYS_MS <= record["timestamp"] <= NOW_MS

    def test_unseeded_run_follows_now_instead_of_the_real_clock(self):
        for record in generate(TXN_SCHEMA, count=200, now=NOW):
            assert NOW_MS - THIRTY_DAYS_MS <= record["timestamp"] <= NOW_MS

    def test_same_seed_and_now_are_reproducible(self):
        first = list(generate(TXN_SCHEMA, count=20, seed=7, now=NOW))
        second = list(generate(TXN_SCHEMA, count=20, seed=7, now=NOW))
        assert first == second

    def test_unhinted_timestamp_defaults_to_now(self, tmp_path):
        schema = _write_schema(
            tmp_path, [{"name": "ts", "type": {"type": "long", "logicalType": "timestamp-millis"}}]
        )
        [record] = generate(schema, count=1, seed=1, now=NOW)
        assert record["ts"] == NOW_MS

    def test_date_today_follows_now(self, tmp_path):
        schema = _write_schema(
            tmp_path,
            [
                {
                    "name": "d",
                    "type": {"type": "int", "logicalType": "date"},
                    "arg.properties": {"range": {"min": "today", "max": "today"}},
                }
            ],
        )
        [record] = generate(schema, count=1, seed=1, now=NOW)
        assert record["d"] == NOW_DAYS

    def test_date_day_offsets_follow_now(self, tmp_path):
        schema = _write_schema(
            tmp_path,
            [
                {
                    "name": "d",
                    "type": {"type": "int", "logicalType": "date"},
                    "arg.properties": {"range": {"min": "-30d", "max": "+7d"}},
                }
            ],
        )
        days = [r["d"] for r in generate(schema, count=200, seed=1, now=NOW)]
        assert all(NOW_DAYS - 30 <= d <= NOW_DAYS + 7 for d in days)

    def test_naive_datetime_is_rejected(self):
        with pytest.raises(ValueError, match="timezone"):
            list(generate(TXN_SCHEMA, count=1, seed=1, now=datetime(2026, 10, 4)))

    def test_non_temporal_seeded_pool_ignores_now(self, tmp_path):
        """Seeded pool members come from the pool seed alone, not the clock."""
        schema = _write_schema(
            tmp_path,
            [
                {
                    "name": "customerId",
                    "type": {"type": "string", "logicalType": "uuid"},
                    "arg.properties": {"pool": {"size": 5, "seed": "customers-v1"}},
                }
            ],
        )
        early = {r["customerId"] for r in generate(schema, count=200, seed=1, now=NOW)}
        late = {
            r["customerId"]
            for r in generate(schema, count=200, seed=1, now=datetime(2030, 6, 1, tzinfo=UTC))
        }
        assert len(early) == 5
        assert early == late
