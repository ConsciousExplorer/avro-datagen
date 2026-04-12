# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-04-12

Significant feature release: 7 issues closed covering new logical types,
expanded rules engine, full regex-like pattern support, schema validation,
cross-schema references, and more.

### Added

- **Decimal logical type** (#1) — `decimal` is now generated as a string respecting `precision` and `scale`, with optional `range` hint for bounded values
- **Comparison operators in rules engine** (#7) — new condition operators: `gt`, `gte`, `lt`, `lte`, `not_equals`, `not_in`, `matches` (regex)
- **Schema validator** (#8) — new `avro_datagen.validator` module and `avro-datagen validate -s schema.avsc` CLI subcommand. Catches structural errors, bad logical type bases, decimal precision/scale issues, broken `ref` targets, rules referencing undeclared fields, and duplicate field names. Unknown hint keys and condition operators are reported as warnings.
- **Cross-schema foreign keys** (#9) — new `foreign_key` arg.property that picks values from another schema's output JSON Lines or JSON array file. Supports `--seed` for reproducibility.
- **Flexible array/map length hints** (#10) — new flat `min_length`/`max_length` and fixed integer `length: N` forms alongside the existing `length: {min, max}` dict form.
- `validate()` and `SchemaValidationError` exposed from the `avro_datagen` package.

### Changed

- **Pattern engine rewritten** (#6) — now supports shortcut classes (`\d`, `\w`, `\s`, `\D`, `\W`, `\S`), negated classes (`[^0-9]`), range quantifiers (`{n,m}`), `?`, `*`, `+`, alternation (`(foo|bar|baz)`), and escape sequences (`\.`, `\(`, `\\`). Malformed patterns raise a clear `ValueError` instead of `IndexError`.
- **Date and time logical types generate meaningful values** (#5) — `date` now produces a random day in the last ~5 years instead of a random int. `time-micros` correctly uses the full microsecond range. All date and time types now support `range` hints with ISO date strings (`"2024-01-15"`), relative offsets (`"-30d"`, `"today"`), and `HH:MM:SS` time strings.
- 64 new tests across all changes (resolver, validator, pattern engine, foreign keys).

## [0.2.7] - 2026-04-11

Internal maintenance release.

## [0.2.6] - 2026-04-11

### Fixed

- Union types now resolve all non-null branches (not just the first) and support a configurable `null_probability` hint.

## [0.2.5] - 2026-04-10

### Fixed

- Kafka producer thread no longer crashes with `AttributeError` on `st.session_state` — thread-safe `threading.Event` and shared dict replace direct session state access from background threads
- "Produce to Kafka" button now re-enables after a produce run completes — sync step moved before button rendering so the disabled state reflects the current producing flag
- Producer log messages now show red for errors and yellow for partial failures instead of always green

## [0.2.4] - 2026-04-10

### Changed

- Enriched bundled sample schema with `faker`, `pattern`, `template`, and `rules` examples

### Fixed

- Union types (e.g. `["null", {"type": "long", "logicalType": "timestamp-millis"}]`) now resolve correctly in `range` and other hints — `_get_logical_type` and `_get_base_type` look inside union branches for the non-null type

## [0.2.3] - 2026-04-10

### Changed

- Upload tab: moved filename and save button to top bar, renamed button to "Upload" for clarity
- Editor tab: moved filename and action buttons to full-width top row, matching other tabs
- Schema editor and sample preview now sit at the same level in side-by-side columns
- Consistent top-bar layout across all three schema tabs (Local, Upload, Editor)

## [0.2.1] - 2026-04-10

### Changed

- UI layout switched to wide mode with side-by-side schema and sample preview across all tabs
- Editor tab: save filename is now editable for renaming schemas on save/download
- Local schemas and upload tabs: schema JSON and sample record shown in two columns

### Fixed

- Save button now writes to `./schemas/` in the working directory, not inside the installed package
- Save creates the `schemas/` folder automatically if it doesn't exist

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

[0.2.4]: https://github.com/ConsciousExplorer/avro-datagen/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/ConsciousExplorer/avro-datagen/compare/v0.2.1...v0.2.3
[0.2.1]: https://github.com/ConsciousExplorer/avro-datagen/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/ConsciousExplorer/avro-datagen/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/ConsciousExplorer/avro-datagen/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ConsciousExplorer/avro-datagen/releases/tag/v0.1.0
