# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-10

### Added

- Schema-driven data generation from Avro `.avsc` files
- `arg.properties` hints: `options`, `range`, `pool`, `pattern`, `ref`, `template`, `rules`
- Conditional field generation via `rules` with `equals`, `is_null`, `in` operators
- Faker integration via `"faker"` hint (optional dependency)
- Deterministic output with `--seed` flag
- CLI entry point: `avro-datagen --schema <path> --count N`
- Python API: `from avro_datagen import generate`
- Kafka producer with SASL/SCRAM authentication (`confluent-kafka` optional)
- Streamlit UI for schema browsing, editing, previewing, and Kafka producing
- Interactive schema editor with live sample record preview
- Streaming generation with real-time metrics in the UI
- Support for all Avro primitives, logical types (uuid, timestamp-millis, iso-timestamp, date), records, arrays, maps, enums, unions, fixed
- MkDocs documentation site with API reference auto-generated from docstrings

[0.1.0]: https://github.com/ConsciousExplorer/avro-datagen/releases/tag/v0.1.0
