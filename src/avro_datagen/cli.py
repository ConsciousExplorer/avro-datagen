"""CLI entry point — generate fake data to stdout as JSON lines."""

import argparse
import json
import sys
import time

from avro_datagen.generator import generate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="avro_datagen",
        description="Generate fake data from an Avro schema as JSON lines.",
    )
    parser.add_argument(
        "--schema",
        "-s",
        required=True,
        help="Path to the .avsc schema file",
    )
    parser.add_argument(
        "--count",
        "-c",
        type=int,
        default=10,
        help="Number of records to generate (default: 10, 0 for infinite)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible output",
    )
    parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        help="Pretty-print JSON (one object per block, not per line)",
    )
    parser.add_argument(
        "--rate",
        "-r",
        type=float,
        default=None,
        help="Records per second (e.g. 10 = 10 rps). No limit if omitted.",
    )
    return parser


def main(args: list[str] | None = None) -> None:
    parser = build_parser()
    opts = parser.parse_args(args)

    indent = 2 if opts.pretty else None
    interval = 1.0 / opts.rate if opts.rate else 0.0

    try:
        for record in generate(opts.schema, opts.count, opts.seed):
            start = time.monotonic()
            print(json.dumps(record, indent=indent))
            if interval:
                elapsed = time.monotonic() - start
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
    except KeyboardInterrupt:
        sys.exit(0)
