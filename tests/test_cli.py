"""Tests for the CLI entry point."""

import json
import time
from pathlib import Path

import pytest

from avro_datagen.cli import main

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TXN_SCHEMA = str(FIXTURES_DIR / "transaction.avsc")


class TestCLI:
    def test_count_flag(self, capsys):
        main(["--schema", TXN_SCHEMA, "--count", "3"])
        output = capsys.readouterr().out.strip()
        lines = output.split("\n")
        assert len(lines) == 3

    def test_default_outputs_ten_records(self, capsys):
        main(["--schema", TXN_SCHEMA])
        output = capsys.readouterr().out.strip()
        lines = output.split("\n")
        assert len(lines) == 10

    def test_output_is_valid_json_lines(self, capsys):
        main(["--schema", TXN_SCHEMA, "--count", "5"])
        output = capsys.readouterr().out.strip()
        for line in output.split("\n"):
            record = json.loads(line)
            assert isinstance(record, dict)
            assert "correlationId" in record

    def test_seed_produces_reproducible_output(self, capsys):
        main(["--schema", TXN_SCHEMA, "--count", "3", "--seed", "42"])
        first = capsys.readouterr().out

        main(["--schema", TXN_SCHEMA, "--count", "3", "--seed", "42"])
        second = capsys.readouterr().out

        assert first == second

    def test_pretty_flag(self, capsys):
        main(["--schema", TXN_SCHEMA, "--count", "1", "--pretty"])
        output = capsys.readouterr().out
        record = json.loads(output)
        assert isinstance(record, dict)
        assert "\n" in output

    def test_rate_flag_throttles_output(self, capsys):
        """--rate 20 means 20 records/sec, so 5 records should take ~0.2s."""
        start = time.monotonic()
        main(["--schema", TXN_SCHEMA, "--count", "5", "--rate", "20"])
        elapsed = time.monotonic() - start

        output = capsys.readouterr().out.strip()
        assert len(output.split("\n")) == 5
        assert elapsed >= 0.15, f"Expected >= 0.15s at 20 rps, got {elapsed:.3f}s"

    def test_no_rate_flag_runs_fast(self, capsys):
        """Without --rate, output should be near-instant."""
        start = time.monotonic()
        main(["--schema", TXN_SCHEMA, "--count", "50"])
        elapsed = time.monotonic() - start

        assert elapsed < 0.5, f"Expected < 0.5s without rate limit, got {elapsed:.3f}s"

    def test_schema_required(self):
        with pytest.raises(SystemExit):
            main(["generate"])
