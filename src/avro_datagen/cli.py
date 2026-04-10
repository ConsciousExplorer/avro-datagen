"""CLI entry point — generate fake data to stdout as JSON lines."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from avro_datagen.generator import generate

_PKG_DIR = Path(__file__).parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="avro-datagen",
        description="Schema-driven fake data generator for Avro schemas.",
    )
    sub = parser.add_subparsers(dest="command")

    # ── generate (default) ──────────────────────────────────────
    gen = sub.add_parser("generate", help="Generate fake data as JSON lines")
    gen.add_argument(
        "--schema",
        "-s",
        required=True,
        help="Path to the .avsc schema file",
    )
    gen.add_argument(
        "--count",
        "-c",
        type=int,
        default=10,
        help="Number of records to generate (default: 10, 0 for infinite)",
    )
    gen.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible output",
    )
    gen.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        help="Pretty-print JSON (one object per block, not per line)",
    )
    gen.add_argument(
        "--rate",
        "-r",
        type=float,
        default=None,
        help="Records per second (e.g. 10 = 10 rps). No limit if omitted.",
    )

    # ── ui ──────────────────────────────────────────────────────
    ui = sub.add_parser("ui", help="Launch the Streamlit web UI")
    ui.add_argument(
        "--port",
        type=int,
        default=8501,
        help="Port to run the UI on (default: 8501)",
    )
    ui.add_argument(
        "--schema-dir",
        help="Directory containing .avsc schema files",
    )
    ui.add_argument(
        "--kafka",
        action="store_true",
        default=False,
        help="Enable Kafka producer section in the UI",
    )

    # ── Backward compat: if first arg looks like a flag, treat as generate
    # This lets `avro-datagen -s schema.avsc -c 10` still work
    gen.add_argument("--schema-dir", help=argparse.SUPPRESS)

    return parser


def _run_generate(opts: argparse.Namespace) -> None:
    """Generate records to stdout."""
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


def _run_ui(opts: argparse.Namespace) -> None:
    """Launch the Streamlit UI."""
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print(
            "Streamlit is not installed. Install with:\n"
            '  pip install "avro-datagen[app]"',
            file=sys.stderr,
        )
        sys.exit(1)

    app_path = _PKG_DIR / "app.py"
    config_dir = _PKG_DIR / ".streamlit"

    import os

    env = dict(os.environ)
    if opts.schema_dir:
        env["SCHEMA_DIR"] = opts.schema_dir
    if opts.kafka:
        env["AVRO_DATAGEN_KAFKA"] = "1"
    if config_dir.is_dir():
        env["STREAMLIT_CONFIG_DIR"] = str(config_dir)

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(opts.port),
        "--server.headless",
        "true",
    ]

    subprocess.run(cmd, env=env, check=False)


def main(args: list[str] | None = None) -> None:
    parser = build_parser()

    # If no subcommand and first arg looks like a flag, default to generate
    raw_args = args if args is not None else sys.argv[1:]
    if raw_args and raw_args[0] not in ("generate", "ui", "-h", "--help"):
        raw_args = ["generate", *raw_args]

    opts = parser.parse_args(raw_args)

    if opts.command == "ui":
        _run_ui(opts)
    elif opts.command == "generate":
        _run_generate(opts)
    else:
        parser.print_help()
