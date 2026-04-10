"""Tests for the core generate function."""

from pathlib import Path

import pytest

from avro_datagen.generator import generate

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"
TXN_SCHEMA = SCHEMAS_DIR / "transaction.avsc"


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
