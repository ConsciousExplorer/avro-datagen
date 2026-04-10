# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-10

### Added

- `avro-datagen ui` subcommand -- launch the Streamlit web UI directly from pip install
- `avro-datagen ui --kafka` flag to enable Kafka sidebar and producer section
- `--port` and `--schema-dir` flags for the UI subcommand
- Bundled example schema and Streamlit config in the pip package
- Ruff (linting + formatting) and Pyright (type checking) in CI
- `AvroType` type alias for stricter type hints in resolver
- `py.typed` marker for PEP 561 type hint support

### Changed

- Faker is now a core dependency -- included with `pip install avro-datagen`, no extra needed
- UI works without Kafka by default; Kafka section only shows with `--kafka`
- Schemas removed from pip package; only a single example schema is bundled
- Consolidated CI, docs, and publish into a single workflow pipeline
- Publish and docs deploy now require checks to pass first
- Renamed package import from `data_generator` to `avro_datagen`
- Migrated from PDM to uv

### Fixed

- CI workflow name for PyPI trusted publisher
- Pyright type-checking errors in resolver and producer

## [0.1.1] - 2026-04-10

### Added

- `avro-datagen ui` subcommand to launch Streamlit web UI from pip install
- `avro-datagen generate` subcommand (backward compatible -- flags without subcommand still work)
- `--port`, `--schema-dir`, and `--kafka` flags for the UI subcommand
- `--kafka` flag enables Kafka sidebar and produce section; UI works without Kafka by default
- Bundled example schema and Streamlit config in the pip package
- Ruff (linting + formatting) and Pyright (type checking)
- `AvroType` type alias for stricter type hints in resolver

### Fixed

- CI workflow name for PyPI trusted publisher
- README badge URL
- Pyright type-checking errors in resolver and producer

### Changed

- Consolidated CI, docs, and publish into a single workflow pipeline
- Publish and docs deploy now require checks to pass first
- Renamed package from `data_generator` to `avro_datagen` for consistency with PyPI name
- Migrated from PDM to uv
- Tightened type hints across resolver, producer, and generator

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

[0.2.0]: https://github.com/ConsciousExplorer/avro-datagen/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/ConsciousExplorer/avro-datagen/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ConsciousExplorer/avro-datagen/releases/tag/v0.1.0
